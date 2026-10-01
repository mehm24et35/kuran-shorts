"""Quran Caption dışa aktarımından ayet aralıklarına göre dikey short üretir.

Kullanım:  python kuran_shorts.py liste.txt
liste.txt:
    proje: Ahzab                        (Quran Caption'daki proje adının bir parçası)
    video: C:\\...\\ahzab_export.mp4    (dikey, siyah arka planlı dışa aktarım)
    35
    41-44
    56 yildizlar                        (klasör adı yazılırsa arka plan o klasörden)
"""
import csv, json, os, random, re, subprocess, sys, datetime
from pathlib import Path

import imageio_ffmpeg

KOK = Path(__file__).parent
ARKAPLAN, CIKTI, KAYIT = KOK / "arkaplan", KOK / "cikti", KOK / "kayit.csv"
EXPORT = Path.home() / "Desktop" / "dikey sureler"  # Quran Caption dışa aktarımları buraya
PROJELER = Path(os.environ["APPDATA"]) / "com.qurancaption" / "projects"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

KULLANICI = "@miskatulfurkan"
FILIGRAN_Y = 1470         # üstten piksel; alt kısımda, platform açıklama alanının üstü
ARKAPLAN_KARARTMA = 0.45  # 1 = orijinal parlaklık, küçüldükçe koyulaşır
BAS_PAY, SON_PAY = 300, 1000  # ms; ayet öncesi/sonrası nefes payı (sessizlik kadarını aşmaz)
ACIKLAMA_YAZ = False  # True: her videonun yanına sablon.txt'den açıklama dosyası yazar (otomatik paylaşım için)
W, H, FPS = 1080, 1920, 30

SURELER = ("Fatiha Bakara Al-i_Imran Nisa Maide Enam Araf Enfal Tevbe Yunus Hud Yusuf Rad Ibrahim Hicr "
           "Nahl Isra Kehf Meryem Taha Enbiya Hac Muminun Nur Furkan Suara Neml Kasas Ankebut Rum Lokman "
           "Secde Ahzab Sebe Fatir Yasin Saffat Sad Zumer Mumin Fussilet Sura Zuhruf Duhan Casiye Ahkaf "
           "Muhammed Fetih Hucurat Kaf Zariyat Tur Necm Kamer Rahman Vakia Hadid Mucadele Hasr Mumtehine "
           "Saf Cuma Munafikun Tegabun Talak Tahrim Mulk Kalem Hakka Mearic Nuh Cin Muzzemmil Muddessir "
           "Kiyame Insan Murselat Nebe Naziat Abese Tekvir Infitar Mutaffifin Insikak Buruc Tarik Ala "
           "Gasiye Fecr Beled Sems Leyl Duha Insirah Tin Alak Kadir Beyyine Zilzal Adiyat Karia Tekasur "
           "Asr Humeze Fil Kureys Maun Kevser Kafirun Nasr Tebbet Ihlas Felak Nas").split()
assert len(SURELER) == 114

# mealde geçen kelime köküne göre arka plan klasörü; hiçbiri yoksa "huzur"
RUH_HALI = {
    "firtina": "azab azap cehennem ateş kıyamet helâk helak gazab gazap zalim felaket sayha şiddetli azgın",
    "gundogumu": "cennet rahmet merhamet müjde mağfiret bağışla nur hidayet lütuf mükâfat",
    "yagmur": "yağmur bitki ekin dirilt bulut rüzgâr rüzgar toprak",
    "deniz": "deniz gemi dalga",
    "yildizlar": "yıldız gece gök güneş",
    "dag": "dağ yeryüzü sarsıl",
    "nehir": "ırmak nehir pınar kaynak",
    "col": "çöl kum",
    "sokak": "şehir şehr kasaba memleket yurt ülke",
}
KARISIK = "karisik"  # meal hiçbir konuya uymazsa: fırtına dışındaki tüm klasörler


def kucult(s):
    return s.replace("I", "ı").replace("İ", "i").lower()


def proje_bul(ad):
    adaylar = []
    for f in PROJELER.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if kucult(ad) in kucult(d["detail"]["name"]):
            adaylar.append((d["detail"]["updatedAt"], d))
    if not adaylar:
        sys.exit(f"'{ad}' adında Quran Caption projesi bulunamadı.")
    return max(adaylar, key=lambda x: x[0])[1]


def aralik_bul(klipler, bas, son):
    """Ayet bas..son için (başlangıç_ms, bitiş_ms, parçalar). Okuyucu sonradan ayet tekrarlarsa ilk geçişi alır."""
    i = next((i for i, k in enumerate(klipler) if k.get("verse") == bas), None)
    if i is None:
        sys.exit(f"{bas}. ayet projede yok.")
    parcalar, j = [], i
    while j < len(klipler):
        k = klipler[j]
        if k["type"] == "Subtitle":
            if not bas <= k["verse"] <= son:
                break
            parcalar.append(k)
        j += 1
    if parcalar[-1]["verse"] != son:
        sys.exit(f"{son}. ayete ulaşılamadı (son bulunan: {parcalar[-1]['verse']}).")
    son_idx = klipler.index(parcalar[-1])
    once = klipler[i - 1] if i > 0 and klipler[i - 1]["type"] == "Silence" else None
    sonra = klipler[son_idx + 1] if son_idx + 1 < len(klipler) and klipler[son_idx + 1]["type"] == "Silence" else None
    t0 = parcalar[0]["startTime"] - min(BAS_PAY, once["duration"] if once else 0)
    t1 = parcalar[-1]["endTime"] + min(SON_PAY, sonra["duration"] if sonra else 0)
    return max(t0, 0), t1, parcalar


def meal(parcalar):
    metinler = []
    for k in parcalar:
        for t in (k.get("translations") or {}).values():
            if not isinstance(t, dict):  # meal eklenmemiş klipler
                continue
            m = (t.get("text") or "").strip()
            if m and m not in metinler:
                metinler.append(m)
            break  # ilk meal yeterli
    return "\n".join(metinler)


def ruh_hali(metin):
    metin = kucult(metin)
    puan = {k: sum(len(re.findall(r"(?<!\w)" + re.escape(kok), metin)) for kok in v.split())
            for k, v in RUH_HALI.items()}
    en = max(puan, key=puan.get)
    return en if puan[en] else KARISIK


def kullanim_sayilari():
    if not KAYIT.exists():
        return {}
    say = {}
    with KAYIT.open(encoding="utf-8") as f:
        for satir in csv.DictReader(f):
            for k in satir["arkaplan"].split("|"):
                say[k] = say.get(k, 0) + 1
    return say


def sure_ol(f):
    out = subprocess.run([FFMPEG, "-i", str(f)], capture_output=True, text=True, errors="ignore").stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def arkaplan_sec(klasor, sure):
    """En az kullanılmış klipleri (eşitlikte rastgele) sure dolana kadar sırala."""
    say = kullanim_sayilari()
    if klasor == KARISIK:
        klipler = [f for f in ARKAPLAN.glob("*/*.mp4") if f.parent.name != "firtina"]
    else:
        klipler = list((ARKAPLAN / klasor).glob("*.mp4"))
    if not klipler:
        sys.exit(f"arkaplan/{klasor}/ boş.")
    random.shuffle(klipler)
    klipler.sort(key=lambda f: say.get(f.name, 0))
    secilen, toplam = [], 0.0
    while toplam < sure:  # arşiv yetmezse baştan tekrar eder
        for f in klipler:
            secilen.append(f)
            toplam += sure_ol(f)
            if toplam >= sure:
                break
    return secilen


def render(video, t0, t1, klipler, cikis):
    sure = (t1 - t0) / 1000
    girdiler, filtre = [], []
    for i, f in enumerate(klipler):
        girdiler += ["-i", str(f)]
        filtre.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                      f"fps={FPS},setsar=1,format=yuv420p[b{i}]")
    n = len(klipler)
    filtre.append("".join(f"[b{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,trim=0:{sure:.3f},"
                  f"setpts=PTS-STARTPTS,format=gbrp,colorchannelmixer="
                  f"rr={ARKAPLAN_KARARTMA}:gg={ARKAPLAN_KARARTMA}:bb={ARKAPLAN_KARARTMA}[bg]")
    filtre.append(f"[{n}:v]scale={W}:{H},fps={FPS},format=gbrp[yazi]")
    font = "C\\:/Windows/Fonts/arialbd.ttf"
    filtre.append(f"[bg][yazi]blend=all_mode=screen,format=yuv420p,"
                  f"drawtext=fontfile='{font}':text='{KULLANICI}':fontsize=38:fontcolor=white@0.6:"
                  f"x=(w-text_w)/2:y={FILIGRAN_Y},"
                  f"fade=t=in:d=0.3,fade=t=out:st={sure - 0.6:.3f}:d=0.6[v]")
    filtre.append(f"[{n}:a]afade=t=in:d=0.15,afade=t=out:st={sure - 0.6:.3f}:d=0.6[a]")
    girdiler += ["-ss", f"{t0 / 1000:.3f}", "-t", f"{sure:.3f}", "-i", str(video)]
    ortak = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *girdiler,
             "-filter_complex", ";".join(filtre), "-map", "[v]", "-map", "[a]", "-t", f"{sure:.3f}",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    nvenc = ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "26", "-b:v", "0", str(cikis)]
    x264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "23", str(cikis)]
    if subprocess.run(ortak + nvenc).returncode:  # ekran kartı kodlayıcı yoksa işlemciyle
        subprocess.run(ortak + x264, check=True)


def main(liste):
    ayar, satirlar = {}, []
    for s in Path(liste).read_text(encoding="utf-8").splitlines():
        s = s.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"(\w+)\s*:\s*(.+)", s)
        if m and not s[0].isdigit():
            ayar[m[1].lower()] = m[2].strip().strip('"')
        else:
            satirlar.append(s)

    proje = proje_bul(ayar["proje"])
    if "video" in ayar:
        video = Path(ayar["video"])
    else:  # export/ içinde adı projeye uyan, yoksa en yeni video
        videolar = sorted(EXPORT.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
        uyan = [f for f in videolar if kucult(ayar["proje"]) in kucult(f.stem)]
        if not videolar:
            sys.exit(f"Klasörde video yok: {EXPORT}")
        video = (uyan or videolar)[0]
        print(f"Video: {video.name}")
    if not video.exists():
        sys.exit(f"Video bulunamadı: {video}")
    klipler = next(t for t in proje["content"]["timeline"]["tracks"] if t["type"] == "Subtitle")["clips"]
    okuyan = proje["detail"]["reciter"]
    sablon = (KOK / "sablon.txt").read_text(encoding="utf-8")
    CIKTI.mkdir(exist_ok=True)
    yapilan = set()  # bilgisayardan silinmiş olsa da bir kez üretilen tekrar üretilmesin
    if KAYIT.exists():
        with KAYIT.open(encoding="utf-8") as f:
            yapilan = {r["dosya"] for r in csv.DictReader(f)}

    for s in satirlar:
        m = re.match(r"(\d+)(?:\s*-\s*(\d+))?\s*(\w+)?$", s)
        if not m:
            print(f"Anlaşılamadı, atlanıyor: {s}")
            continue
        bas, son = int(m[1]), int(m[2] or m[1])
        t0, t1, parcalar = aralik_bul(klipler, bas, son)
        sure_no = parcalar[0]["surah"]
        sure_adi = SURELER[sure_no - 1].replace("_", " ")
        ayetler = f"{bas}-{son}" if son != bas else str(bas)
        metin = meal(parcalar)
        klasor = m[3] or ruh_hali(metin)
        secilen = arkaplan_sec(klasor, (t1 - t0) / 1000)
        ad = f"{sure_adi.replace(' ', '')}_{ayetler}"
        if ad in yapilan or (CIKTI / f"{ad}.mp4").exists():  # yarıda kesilen çalışmayı kaldığı yerden sürdürür
            print(f"{sure_adi} {ayetler}: zaten var, atlandı")
            continue
        print(f"{sure_adi} {ayetler}: {(t1 - t0) / 1000:.1f} sn, arka plan: {klasor}")

        gecici = CIKTI / f"{ad}.yarim.mp4"
        render(video, t0, t1, secilen, gecici)
        gecici.replace(CIKTI / f"{ad}.mp4")
        if ACIKLAMA_YAZ:
            (CIKTI / f"{ad}.txt").write_text(sablon.format(
                sure=sure_adi, sure_no=sure_no, ayetler=ayetler, ayet_sayisi=son - bas + 1,
                okuyan=okuyan, meal=metin, kullanici=KULLANICI,
                sure_etiket=re.sub(r"\W", "", kucult(sure_adi)) + "suresi",
                okuyan_etiket=re.sub(r"\W", "", kucult(okuyan)),
            ), encoding="utf-8")

        yeni = not KAYIT.exists()
        with KAYIT.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if yeni:
                w.writerow(["tarih", "dosya", "okuyan", "klasor", "arkaplan"])
            w.writerow([datetime.date.today(), ad, okuyan, klasor, "|".join(f.name for f in secilen)])
    print(f"Bitti. Dosyalar: {CIKTI}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else KOK / "liste.txt")
