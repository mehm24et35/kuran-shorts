"""Instagram'daki tüm reels'lerin izlenme/izlenme süresi/paylaşım verisini ig_istatistik.csv'ye yazar (paylaşım yapmaz).
Ortam değişkenleri: IG_USER_ID, IG_TOKEN. Token'da instagram_business_manage_insights izni olmalı."""
import csv, os, re
import requests

from instagram_yukle import API, kontrol

METRIK = "views,reach,saved,shares,likes,comments,ig_reels_avg_watch_time"
uid, tok = os.environ["IG_USER_ID"], os.environ["IG_TOKEN"]

medya, url = [], f"{API}/{uid}/media"
par = {"fields": "id,caption,timestamp,permalink,media_product_type", "limit": 100, "access_token": tok}
while url:
    r = requests.get(url, params=par, timeout=60)
    kontrol(r)
    d = r.json()
    medya += d["data"]
    url, par = d.get("paging", {}).get("next"), None  # next adresi parametreleri zaten içeriyor

with open("ig_istatistik.csv", "w", newline="", encoding="utf-8") as f:
    y = csv.writer(f)
    y.writerow(["tarih", "baslik", *METRIK.split(","), "link"])
    for m in medya:
        r = requests.get(f"{API}/{m['id']}/insights", params={"metric": METRIK, "access_token": tok}, timeout=60)
        kontrol(r)
        deger = {i["name"]: i["values"][0]["value"] for i in r.json()["data"]}
        baslik = re.sub(r"\s+", " ", (m.get("caption") or "").split("\n")[0])[:80]
        # tarih: UTC tarih+saat (paylaşım saati karşılaştırması için)
        y.writerow([m["timestamp"][:16], baslik, *(deger.get(k, "") for k in METRIK.split(",")), m["permalink"]])
print(len(medya), "gönderi yazıldı")
