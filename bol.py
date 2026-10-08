"""Quran Caption projesini ayet sınırlarından shortlara böler, liste.txt satırlarını yazdırır.
Kullanım:  python bol.py "Ali İmran Suresi Muhammad"      (Maide ortalaması ~50 sn, en çok ~85 sn)"""
import sys
from kuran_shorts import proje_bul, aralik_bul

HEDEF, TAVAN = 50, 85  # sn; tek ayet TAVAN'dan uzunsa tek başına kalır


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


if __name__ == "__main__":
    s = bol(proje_bul(sys.argv[1]))
    for b, e, d in s:
        print(f"{b}-{e}" if e > b else b)
    print(f"# {len(s)} short, ort {sum(d for *_, d in s) / len(s):.0f} sn, min {min(d for *_, d in s):.0f}, "
          f"max {max(d for *_, d in s):.0f}", file=sys.stderr)
