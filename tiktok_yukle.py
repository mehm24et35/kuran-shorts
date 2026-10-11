"""Bir videoyu TikTok'a paylaşır (Content Posting API, Direct Post, FILE_UPLOAD).
Ortam değişkenleri: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN,
TIKTOK_GIZLILIK (varsayılan SELF_ONLY; TikTok denetimi geçince PUBLIC_TO_EVERYONE).

İlk giriş (bir kez, tarayıcı açılır): python tiktok_yukle.py --giris
"""
import os, subprocess, sys, time, webbrowser
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests

API = "https://open.tiktokapis.com/v2"
DONUS = "https://mehm24et35.github.io/kuran-shorts/tiktok_donus.html"  # TikTok app'indeki redirect URI ile aynı olmalı
KOK = Path(__file__).parent
KAPAK_MS = 1500  # videolar 0. karede siyahtan açılıyor (instagram_yukle.py'deki gibi)
MAX_PARCA = 64 * 1024 * 1024  # tek parça yükleme sınırı; kısa videolar bunun çok altında


def kontrol(r):
    if not r.ok:
        raise RuntimeError(f"{r.status_code} {r.url} -> {r.text[:500]}")
    d = r.json()
    hata = d.get("error")  # içerik API'sinde {"code": "ok"|...}, OAuth'ta düz metin
    if hata and (hata != {} and (isinstance(hata, str) or hata.get("code", "ok") != "ok")):
        raise RuntimeError(f"{r.url} -> {d}")
    return d


def token_al(**form):
    return kontrol(requests.post(f"{API}/oauth/token/", data={
        "client_key": os.environ["TIKTOK_CLIENT_KEY"], "client_secret": os.environ["TIKTOK_CLIENT_SECRET"], **form}, timeout=60))


def erisim_tokeni():
    d = token_al(grant_type="refresh_token", refresh_token=os.environ["TIKTOK_REFRESH_TOKEN"])
    if d.get("refresh_token") != os.environ["TIKTOK_REFRESH_TOKEN"]:  # ponytail: TikTok bazen yenisini verir; secret'ı elle güncelle, gerekirse PAT ile otomatikleştir
        print("TIKTOK UYARISI: refresh token değişti, TIKTOK_REFRESH_TOKEN secret'ını güncelle:", d["refresh_token"][:6] + "…")
        (KOK / "tiktok.token").write_text(d["refresh_token"])
    return d["access_token"]


def govde(boyut, baslik, gizlilik):
    assert boyut <= MAX_PARCA, "video tek parça için çok büyük"
    return {
        "post_info": {"title": baslik[:2200], "privacy_level": gizlilik, "video_cover_timestamp_ms": KAPAK_MS},
        "source_info": {"source": "FILE_UPLOAD", "video_size": boyut, "chunk_size": boyut, "total_chunk_count": 1},
    }


def video(dosya, baslik):
    gizlilik = os.environ.get("TIKTOK_GIZLILIK") or "SELF_ONLY"  # workflow'da tanımsız değişken boş metin gelir
    baslik_h = {"Authorization": f"Bearer {erisim_tokeni()}", "Content-Type": "application/json; charset=UTF-8"}
    secenekler = kontrol(requests.post(f"{API}/post/publish/creator_info/query/", headers=baslik_h, timeout=60))["data"]["privacy_level_options"]
    if gizlilik not in secenekler:
        raise RuntimeError(f"TikTok bu hesap için {gizlilik} izin vermiyor, seçenekler: {secenekler}")
    veri = Path(dosya).read_bytes()
    d = kontrol(requests.post(f"{API}/post/publish/video/init/", headers=baslik_h, json=govde(len(veri), baslik, gizlilik), timeout=60))["data"]
    kontrol(requests.put(d["upload_url"], data=veri, timeout=600, headers={
        "Content-Type": "video/mp4", "Content-Length": str(len(veri)), "Content-Range": f"bytes 0-{len(veri) - 1}/{len(veri)}"}))
    for _ in range(60):  # TikTok işleyene kadar bekle (en fazla ~10 dk)
        s = kontrol(requests.post(f"{API}/post/publish/status/fetch/", headers=baslik_h, json={"publish_id": d["publish_id"]}, timeout=60))["data"]
        if s["status"] in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            return d["publish_id"]
        if s["status"] == "FAILED":
            raise RuntimeError(f"TikTok paylaşım hatası: {s}")
        time.sleep(10)
    raise TimeoutError("TikTok işlemesi zaman aşımına uğradı")


def giris():
    anahtar = input("TikTok client_key: ").strip()
    gizli = input("TikTok client_secret (yapıştırın): ").strip()  # getpass Windows konsolunda yapıştırmayı kabul etmiyor
    os.environ["TIKTOK_CLIENT_KEY"], os.environ["TIKTOK_CLIENT_SECRET"] = anahtar, gizli
    adres = (f"https://www.tiktok.com/v2/auth/authorize/?client_key={anahtar}&scope=user.info.basic,video.publish"
             f"&response_type=code&redirect_uri={quote(DONUS, safe='')}&state=kuran")
    print("Tarayıcıda TikTok'a girip izin verin; açılan sayfadaki kodu buraya yapıştırın.")
    webbrowser.open(adres)
    kod = input("Kod (ya da sayfanın tam adresi): ").strip()
    kod = unquote(parse_qs(urlparse(kod).query)["code"][0] if kod.startswith("http") else kod)
    d = token_al(grant_type="authorization_code", code=kod, redirect_uri=DONUS)
    (KOK / "tiktok.token").write_text(d["refresh_token"])  # git'e girmez (.gitignore: *.token)
    for ad, deger in (("TIKTOK_CLIENT_KEY", anahtar), ("TIKTOK_CLIENT_SECRET", gizli), ("TIKTOK_REFRESH_TOKEN", d["refresh_token"])):
        subprocess.run(["gh", "secret", "set", ad], input=deger, text=True, check=True, cwd=KOK)  # değer stdin'den gider, komut satırında görünmez
    print("Tamam: üç TikTok secret'ı GitHub'a yazıldı.")


if __name__ == "__main__":
    g = govde(1234, "x" * 3000, "SELF_ONLY")  # ağ gerektirmeyen kontrol
    assert g["source_info"]["chunk_size"] == 1234 and len(g["post_info"]["title"]) == 2200
    if "--giris" in sys.argv:
        giris()
