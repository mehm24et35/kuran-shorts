"""Quran Caption projesini ayet sınırlarından shortlara böler, anlamı zayıf olanları eler (sec.py),
kalan liste.txt satırlarını yazdırır.
Kullanım:  python bol.py "Ali İmran Suresi Muhammad"
           python bol.py "Ali İmran Suresi Muhammad" --hepsi   (eleme yapmadan)"""
import sys
from kuran_shorts import SURELER, meal, proje_bul, aralik_bul
import sec

HEDEF, TAVAN = 30, 60  # sn; kısa videolar daha çok izleniyor (ig_istatistik); tek ayet TAVAN'dan uzunsa tek başına kalır


def bol(proje):
    klipler = next(t for t in proje["content"]["timeline"]["tracks"] if t["type"] == "Subtitle")["clips"]
    ayetler = sorted({k["verse"] for k in klipler if k["type"] == "Subtitle"})
    n = len(ayetler)
    sure = {}

    def uzun(i, j):  # ayetler[i..j] süresi (sn)
        if (i, j) not in sure:
            t0, t1, _ = aralik_bul(klipler, ayetler[i], ayetler[j])
            sure[i, j] = (t1 - t0) / 1000
        return sure[i, j]

    en = [(0, None)] + [(float("inf"), None)] * n  # en[j]: ilk j ayeti bölmenin en az maliyeti
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            d = uzun(i, j - 1)
            if d > TAVAN and i < j - 1:
                break  # daha geriye gitmek süreyi büyütür
            m = en[i][0] + (d - HEDEF) ** 2
            if m < en[j][0]:
                en[j] = (m, i)
    satir, j = [], n
    while j:
        i = en[j][1]
        satir.append((ayetler[i], ayetler[j - 1], uzun(i, j - 1)))
        j = i
    return satir[::-1]


def ele(proje, satir):  # anlam puanı sec.ESIK altındakileri çıkarır
    klipler = next(t for t in proje["content"]["timeline"]["tracks"] if t["type"] == "Subtitle")["clips"]
    sure = SURELER[next(k["surah"] for k in klipler if k["type"] == "Subtitle") - 1].replace("_", "")
    ad = {f"{sure}_{b}-{e}" if e > b else f"{sure}_{b}": (b, e, d) for b, e, d in satir}
    a = sec.anlamlar()
    eksik = {k: meal(aralik_bul(klipler, b, e)[2]).replace("\n", " ") for k, (b, e, _) in ad.items() if k not in a}
    if eksik:
        a |= sec.claude_puanla(eksik)
    return [v for k, v in ad.items() if sec.puan(a[k], v[2]) >= sec.ESIK]


if __name__ == "__main__":
    p = proje_bul(sys.argv[1])
    s = bol(p)
    if "--hepsi" not in sys.argv:
        s = ele(p, s)
    for b, e, d in s:
        print(f"{b}-{e}" if e > b else b)
    print(f"# {len(s)} short, ort {sum(d for *_, d in s) / len(s):.0f} sn, min {min(d for *_, d in s):.0f}, "
          f"max {max(d for *_, d in s):.0f}", file=sys.stderr)
