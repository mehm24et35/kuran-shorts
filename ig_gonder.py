"""ig_bekleyen/ altındaki videoları sadece Instagram'a gönderir (YouTube'a yüklemez), başarılı olanı siler."""
import os
from pathlib import Path

from instagram_yukle import reels
from youtube_yukle import ACIKLAMA, IG_NEREDEN, KOK, okuyanlar, sira

okuyan = okuyanlar()
for f in sorted(Path(KOK / "ig_bekleyen").glob("*.mp4"), key=lambda f: sira(f.stem)):
    sure, ayetler = f.stem.split("_", 1)
    ack = ACIKLAMA.format(sure=sure, ayetler=ayetler, okuyan=okuyan.get(f.stem, ""), etiket=sure.lower() + "suresi", nereden=IG_NEREDEN)
    print("instagram:", f.name, reels(os.environ["VIDEO_URL_TABANI"] + f.relative_to(KOK).as_posix(), ack), flush=True)
    f.unlink()
