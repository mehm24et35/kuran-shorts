"""cikti/ altındaki paylaşılmamış videoları ayet sırasıyla YouTube Shorts'a yükler.

Kullanım:
  python youtube_yukle.py --giris         # sadece Google girişi (ilk seferde, tarayıcı açılır)
  python youtube_yukle.py --adet 3        # 3 video yükle (günlük kota ~6 video)
  python youtube_yukle.py --adet 1 --kuru # yüklemeden ne yükleneceğini göster
Paylaşılanlar paylasilan.csv'ye yazılır, bir daha yüklenmez.
"""
import argparse, csv, datetime, re
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

KOK = Path(__file__).parent
CIKTI, KAYIT, PAYLASILAN = KOK / "cikti", KOK / "kayit.csv", KOK / "paylasilan.csv"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
ACIKLAMA = """{sure} Suresi {ayetler}. Ayet | {okuyan}

📖 Kur'an-ı Kerim tilaveti ve Türkçe meal
Abone olmayı unutmayın.

#kuran #kuranıkerim #tilavet #{etiket} #shorts"""


def giris():
    token = KOK / "token.json"
    cred = Credentials.from_authorized_user_file(token, SCOPES) if token.exists() else None
    if not cred or not cred.valid:
        if cred and cred.expired and cred.refresh_token:
            cred.refresh(Request())
        else:
            cred = InstalledAppFlow.from_client_secrets_file(KOK / "client_secret.json", SCOPES).run_local_server(port=0)
        token.write_text(cred.to_json())
    return build("youtube", "v3", credentials=cred)


def sira(ad):  # "Bakara_103-105" -> ("Bakara", 103)
    sure, ayet = ad.split("_", 1)
    return sure, int(re.match(r"\d+", ayet).group())


def okuyanlar():
    if not KAYIT.exists():
        return {}
    with KAYIT.open(encoding="utf-8") as f:
        return {r["dosya"]: r["okuyan"] for r in csv.DictReader(f)}


def paylasilanlar():
    if not PAYLASILAN.exists():
        return set()
    with PAYLASILAN.open(encoding="utf-8") as f:
        return {r["dosya"] for r in csv.DictReader(f)}


def bekleyenler():
    yapilan = paylasilanlar()
    dosyalar = [f for f in CIKTI.rglob("*.mp4") if not f.name.endswith(".yarim.mp4") and f.stem not in yapilan]
    return sorted(dosyalar, key=lambda f: sira(f.stem))


def yukle(yt, f, okuyan, gizlilik):
    sure, ayetler = f.stem.split("_", 1)
    govde = {
        "snippet": {
            "title": f"{sure} Suresi {ayetler}. Ayet | {okuyan} #shorts"[:100],
            "description": ACIKLAMA.format(sure=sure, ayetler=ayetler, okuyan=okuyan, etiket=sure.lower() + "suresi"),
            "categoryId": "22",
        },
        "status": {"privacyStatus": gizlilik, "selfDeclaredMadeForKids": False},
    }
    istek = yt.videos().insert(part="snippet,status", body=govde, media_body=MediaFileUpload(str(f), resumable=True))
    yanit = None
    while yanit is None:
        _, yanit = istek.next_chunk()
    return yanit["id"]


if __name__ == "__main__":
    assert sira("Bakara_103-105") == ("Bakara", 103) and sira("Bakara_102") == ("Bakara", 102)
    a = argparse.ArgumentParser()
    a.add_argument("--giris", action="store_true")
    a.add_argument("--adet", type=int, default=1)
    a.add_argument("--kuru", action="store_true")
    a.add_argument("--gizlilik", default="public", choices=["public", "unlisted", "private"])
    arg = a.parse_args()

    if arg.giris:
        giris()
        print("Giriş tamam, token.json kaydedildi.")
        raise SystemExit
    secilen = bekleyenler()[:arg.adet]
    if not secilen:
        raise SystemExit("Paylaşılacak video kalmadı.")
    yt = None if arg.kuru else giris()
    okuyan = okuyanlar()
    for f in secilen:
        if arg.kuru:
            print("yüklenecek:", f.name)
            continue
        vid = yukle(yt, f, okuyan.get(f.stem, ""), arg.gizlilik)
        yeni = not PAYLASILAN.exists()
        with PAYLASILAN.open("a", newline="", encoding="utf-8") as g:
            w = csv.writer(g)
            if yeni:
                w.writerow(["tarih", "dosya", "youtube_id"])
            w.writerow([datetime.date.today(), f.stem, vid])
        print("yüklendi:", f.name, "https://youtube.com/shorts/" + vid)
