"""cikti/ içindeki yeni videoları 14'erli gruplar halinde GitHub'a gönderir (kullanıcı onayıyla, herkese açık depo),
sonra bilgisayardan siler. Gönderim geçici, hafif bir klondan yapılır; bu klasörün .git'i video tutmaz
(cikti/ burada sparse-checkout ile dışarıda, depo blob:limit=1m filtreli kısmi klon)."""
import os, re, shutil, stat, subprocess, tempfile
from pathlib import Path


def cikar(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, check=True).stdout.strip()


kimlik = ["-c", "user.name=" + cikar("config", "user.name"), "-c", "user.email=" + cikar("config", "user.email")]
fs = [f for f in Path("cikti").rglob("*.mp4") if not f.name.endswith(".yarim.mp4")]
fs.sort(key=lambda f: int(re.search(r"_(\d+)", f.stem).group(1)))
t = tempfile.mkdtemp()
try:
    subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:limit=1m", "--sparse",
                    cikar("remote", "get-url", "origin"), t], check=True)
    gruplar, g, mb = [], [], 0  # 14 video ya da ~150 MB; büyük tek push bağlantı dalgalıyken GitHub'da 408 zaman aşımı veriyor
    for f in fs:
        boyut = f.stat().st_size / 1e6
        if g and (len(g) == 14 or mb + boyut > 150):
            gruplar.append(g)
            g, mb = [], 0
        g.append(f)
        mb += boyut
    gruplar.append(g)
    i = 0
    for grup in gruplar:
        for f in grup:
            (Path(t) / f.parent).mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, Path(t) / f)
        subprocess.run(["git", "-C", t, "add", "--sparse", *(f.as_posix() for f in grup)], check=True)
        subprocess.run(["git", "-C", t, *kimlik, "commit", "-q", "-m", f"videolar {i + 1}-{i + len(grup)}"], check=True)
        for deneme in range(3):  # ağ kesilirse aynı commit yeniden denenir
            if not subprocess.run(["git", "-C", t, "push", "-q", "origin", "main"]).returncode:
                break
        else:
            raise SystemExit("push 3 denemede de başarısız")
        for f in grup:
            f.unlink()  # GitHub'da, bilgisayarda tutmaya gerek yok
        i += len(grup)
        print("gönderildi:", i, "/", len(fs), flush=True)
finally:  # git nesneleri salt okunur, Windows'ta silmek için yazılabilir yap
    shutil.rmtree(t, onerror=lambda fn, p, _: (os.chmod(p, stat.S_IWRITE), fn(p)))
subprocess.run(["git", "pull", "-q"], check=True)
print("BITTI")
