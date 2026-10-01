"""Bir videoyu Instagram Reels olarak paylaşır (Instagram API with Instagram Login).
Ortam değişkenleri: IG_USER_ID, IG_TOKEN, VIDEO_URL_TABANI (videonun herkese açık adresinin başı)."""
import os, time
import requests

API = "https://graph.instagram.com/v21.0"


def reels(video_url, aciklama):
    uid, tok = os.environ["IG_USER_ID"], os.environ["IG_TOKEN"]
    r = requests.post(f"{API}/{uid}/media", data={
        "media_type": "REELS", "video_url": video_url, "caption": aciklama, "access_token": tok}, timeout=60)
    r.raise_for_status()
    kap = r.json()["id"]
    for _ in range(60):  # video işlenene kadar bekle (en fazla ~10 dk)
        d = requests.get(f"{API}/{kap}", params={"fields": "status_code", "access_token": tok}, timeout=60).json()
        if d.get("status_code") == "FINISHED":
            break
        if d.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram video işleme hatası: {d}")
        time.sleep(10)
    else:
        raise TimeoutError("Instagram video işlemesi zaman aşımına uğradı")
    p = requests.post(f"{API}/{uid}/media_publish", data={"creation_id": kap, "access_token": tok}, timeout=60)
    p.raise_for_status()
    return p.json()["id"]
