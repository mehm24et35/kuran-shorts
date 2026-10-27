"""Shortları anlamına (meal, 1-10) ve süresine göre puanlar; zayıfları eler.
Okuyuş ölçümü (perde genişliği) denendi, 71 reels'te izlenmeyle ilişkisi çıkmadı (ρ≈0), kaldırıldı.

Kullanım:
  python sec.py --kuyruk      # GitHub'da bekleyen videoları puanlar -> kuyruk_puan.csv + inceleme.html (izleyerek kontrol)
  python sec.py --sil         # kuyruk_puan.csv'de eşik altında kalanları GitHub'dan siler
  python sec.py Bakara_45-46 Nisa_1-3 ...   # verilen parçaları puanlar (stdout)
Anlam puanları anlam.csv'de birikir; olmayanlar ANTHROPIC_API_KEY varsa Claude'a sorulur."""
import csv, functools, re, subprocess, sys

from kuran_shorts import KOK, aralik_bul, meal, proje_bul

PROJE = {"Bakara": "Bakara", "Nisa": "Nisa", "Maide": "Maide", "Al-iImran": "Ali İmran", "Enam": "en am"}  # cikti klasörü -> Quran Caption adı
ANLAM = KOK / "anlam.csv"
ESIK = 7  # anlam puanı bunun altındaki parça paylaşılmaz
UZUN = 80  # sn; bundan uzun videolar tabanın altında kalıyor (ig_istatistik, 2026-10)

OLCUT = """Sen Instagram/YouTube Shorts için Kur'an tilaveti videosu seçen bir editörsün. Her parçanın Türkçe mealini oku,
tek soruya göre 1-10 puan ver: "Bu mana insanın kalbine dokunur mu, onu durdurup sonuna kadar dinletir mi?"
Yüksek (8-10): izleyiciye doğrudan hitap eden öğüt/teselli ("sabır ve namazla yardım dileyin"), dua ("Rabbimiz..."),
ölüm/ahiret/hesap, cennet-cehennem tasviri, sert uyarı ("Allah'ı nasıl inkâr edersiniz?"), Allah'ın sıfatları,
ve etkileyici kıssa anları: Firavun'un zulmü ve boğuluşu, Mûsâ'nın denizi yarması, Âdem ile şeytan, Yûsuf, Meryem,
Nûh'un tufanı, İbrâhim'in ateşe atılması gibi - hikâyenin dramatik, insanı etkileyen anı.
Orta (5-7): genel iman/inkâr anlatımı; kıssanın bağlam isteyen ama yine de anlaşılır bölümü.
Düşük (1-4): ahkâm ayrıntısı (miras payları, evlilik/boşanma hükümleri, hac/oruç/kurban usulü, savaş kuralları, borç,
av cezası), bağlam bilinmeden anlaşılmayan ara ayrıntı, isim/soy listeleri.
Sadece manayı puanla; video süresi ayrıca değerlendiriliyor."""


@functools.cache
def klipler(sure):
    p = proje_bul(PROJE[sure])
    return next(t for t in p["content"]["timeline"]["tracks"] if t["type"] == "Subtitle")["clips"]


def parca(ad):  # "Nisa_103-105" -> (süre_sn, meal)
    sure, ayet = ad.split("_", 1)
    bas, _, son = ayet.partition("-")
    t0, t1, p = aralik_bul(klipler(sure), int(bas), int(son or bas))
    return (t1 - t0) / 1000, meal(p).replace("\n", " ")


def anlamlar():
    if not ANLAM.exists():
        return {}
    with ANLAM.open(encoding="utf-8") as f:
        return {r["dosya"]: int(r["puan"]) for r in csv.DictReader(f)}


def claude_puanla(parcalar):  # {ad: meal} -> {ad: puan}; anlam.csv'ye de ekler
    import anthropic
    sonuc = {}
    adlar = list(parcalar)
    for i in range(0, len(adlar), 40):
        grup = adlar[i:i + 40]
        metin = "\n\n".join(f"[{a}] {parcalar[a]}" for a in grup)
        r = anthropic.Anthropic().beta.messages.create(
            model="claude-opus-5-5", max_tokens=16000, system=OLCUT,
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            messages=[{"role": "user", "content": metin + "\n\nHer parça için tek satır yaz: ad;puan"}])
        cevap = "".join(b.text for b in r.content if b.type == "text")
        sonuc |= {a: int(p) for a, p in re.findall(r"\[?([\w-]+_\d+(?:-\d+)?)\]?\s*;\s*(\d+)", cevap) if a in grup}
    yeni = not ANLAM.exists()
    with ANLAM.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if yeni:
            w.writerow(["dosya", "puan"])
        w.writerows(sonuc.items())
    return sonuc


def puan(anlam, sure_sn):
    return anlam - (1 if sure_sn > UZUN and anlam < 9 else 0)  # çok etkileyici olan uzun da olsa kalır


def sil():
    """kuyruk_puan.csv'de eşiğin altında kalanları GitHub'dan siler. Video indirmeyen hafif klonla (videolari_gonder gibi)."""
    import os, shutil, stat, tempfile
    with (KOK / "kuyruk_puan.csv").open(encoding="utf-8") as f:
        zayif = [r["dosya"] for r in csv.DictReader(f) if float(r["puan"]) < ESIK]
    yol = [f"cikti/{a.split('_')[0]}/{a}.mp4" for a in zayif]
    t = tempfile.mkdtemp()
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse", url, t], check=True)
        subprocess.run(["git", "-C", t, "rm", "-q", "--sparse", "--ignore-unmatch", *yol], check=True)
        kimlik = []  # geçici klonda kimlik yok; bu deponunkini kullan
        for k in ("name", "email"):
            kimlik += ["-c", f"user.{k}=" + subprocess.run(["git", "config", f"user.{k}"], capture_output=True, text=True).stdout.strip()]
        subprocess.run(["git", "-C", t, *kimlik, "commit", "-q", "-m", f"anlamı zayıf {len(yol)} video kuyruktan çıkarıldı (sec.py)"], check=True)
        subprocess.run(["git", "-C", t, "push", "-q", "origin", "main"], check=True)
    finally:  # git nesneleri salt okunur, Windows'ta silmek için yazılabilir yap
        shutil.rmtree(t, onerror=lambda fn, p, _: (os.chmod(p, stat.S_IWRITE), fn(p)))
    print(len(yol), "video silindi", file=sys.stderr)


def inceleme(satirlar):  # kuyruktaki videoları puanı ve mealiyle izlemek için inceleme.html
    import html
    url = "https://raw.githubusercontent.com/mehm24et35/kuran-shorts/main/cikti"
    kart = "".join(
        f'<div class="k {"tut" if p >= ESIK else "sil"}{" sinir" if ESIK <= p < ESIK + 1 else ""}"><video controls preload="none" '
        f'src="{url}/{a.split("_")[0]}/{a}.mp4"></video><b>{a.replace("_", " ")}</b> · {s} sn · anlam {n} · '
        f'<span onclick="d(this)" data-ad="{a}">{"kalıyor" if p >= ESIK else "siliniyor"}</span><p>{html.escape(m)}</p></div>'
        for a, s, n, p, m in satirlar)
    (KOK / "inceleme.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>Kuyruk inceleme</title>
<style>body{{font:14px system-ui;margin:16px;background:#111;color:#eee}}#g{{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}}
.k{{background:#1d1d1d;border-radius:8px;padding:8px}}video{{width:100%;aspect-ratio:9/16;background:#000;border-radius:6px}}
span{{cursor:pointer;text-decoration:underline dotted}}.tut span{{color:#6c6}}.sil span{{color:#e66}}.degisti{{outline:2px solid #fc3}}p{{color:#aaa;max-height:7em;overflow:auto}}button{{margin-right:6px}}</style>
<p>{sum(r[3] >= ESIK for r in satirlar)} kalıyor / {len(satirlar)} · eşik {ESIK} ·
<button onclick="f('')">Hepsi</button><button onclick="f('tut')">Kalanlar</button><button onclick="f('sil')">Silinenler</button><button onclick="f('sinir')">Sınırdakiler (en düşük kalanlar)</button> · kararı değiştirmek için "kalıyor/siliniyor" yazısına tıkla ·
<button onclick="kopyala(this)">Değişiklikleri kopyala</button></p>
<div id="g">{kart}</div><script>
function f(c){{for(const k of document.querySelectorAll('.k'))k.hidden=c&&!k.classList.contains(c)}}
function d(s){{const k=s.parentElement,t=k.classList.toggle('tut');k.classList.toggle('sil',!t);k.classList.toggle('degisti');s.textContent=t?'kalıyor':'siliniyor'}}
function kopyala(b){{const m=[...document.querySelectorAll('.degisti')].map(k=>(k.classList.contains('tut')?'tut ':'sil ')+k.querySelector('span').dataset.ad).join('\\n');
navigator.clipboard.writeText(m||'değişiklik yok').then(()=>b.textContent='Kopyalandı ('+document.querySelectorAll('.degisti').length+')')}}</script>""",
                                          encoding="utf-8")


def kuyruk():  # GitHub'da paylaşılmayı bekleyen videolar
    subprocess.run(["git", "fetch", "-q", "origin", "main"], check=True)
    yollar = subprocess.run(["git", "ls-tree", "-r", "--name-only", "origin/main", "cikti"],
                            capture_output=True, text=True, check=True).stdout.split()
    return [y.split("/")[-1][:-4] for y in yollar if y.endswith(".mp4")]


if __name__ == "__main__":
    assert puan(8, 40) > puan(7, 40) and puan(7, 40) > puan(7, 90) and puan(9, 120) == 9
    sys.stdout.reconfigure(encoding="utf-8", newline="")  # Windows konsolu cp1254 yazıyordu
    sys.stderr.reconfigure(encoding="utf-8")
    if sys.argv[1:] == ["--sil"]:
        raise SystemExit(sil())
    adlar = kuyruk() if sys.argv[1:] == ["--kuyruk"] else sys.argv[1:]
    bilgi = {a: parca(a) for a in adlar}
    a = anlamlar()
    eksik = {k: m for k, (_, m) in bilgi.items() if k not in a}
    if eksik:
        a |= claude_puanla(eksik)
    satirlar = sorted(([k, f"{s:.0f}", a[k], puan(a[k], s), m] for k, (s, m) in bilgi.items() if k in a),
                      key=lambda r: -r[3])
    cikis = open(KOK / "kuyruk_puan.csv", "w", newline="", encoding="utf-8") if sys.argv[1:] == ["--kuyruk"] else sys.stdout
    w = csv.writer(cikis)
    w.writerow(["dosya", "sure_sn", "anlam", "puan", "meal"])
    w.writerows(satirlar)
    if sys.argv[1:] == ["--kuyruk"]:
        inceleme(satirlar)
    print(f"{len(satirlar)} parça, eşik ({ESIK}) üstü: {sum(r[3] >= ESIK for r in satirlar)}", file=sys.stderr)
