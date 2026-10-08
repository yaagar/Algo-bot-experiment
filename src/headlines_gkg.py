"""Headlines from GDELT 2.0 raw 15-minute GKG files (primary source for Bot B).

GDELT publishes one GKG file every 15 minutes and keeps them permanently
(unlike the DOC API, which only searches ~3 months). Each row is one article
with its page title in the Extras field. We stream each file, keep rows whose
TITLE matches a spec §8 topic, and throw the rest away.

"Available at" time = the file's 15-minute timestamp (when GDELT first saw
the article). Files are English-language sources (translated sources are in
separate *.translation.gkg files, which we don't use).

Output: data/raw/gdelt_gkg/YYYYMMDD.jsonl, one file per complete UTC day,
so the download can stop and resume. Missing upstream files are logged.

Run:  .venv/Scripts/python -m src.headlines_gkg
"""
import csv
import html
import io
import json
import re
import zipfile
from datetime import datetime, timedelta, timezone

import requests

from src.config import PROJECT_ROOT

BASE_URL = "https://data.gdeltproject.org/gdeltv2/{stamp}.gkg.csv.zip"
OUT_DIR = PROJECT_ROOT / "data" / "raw" / "gdelt_gkg"
START = datetime(2026, 7, 1, tzinfo=timezone.utc)

# spec §8 topics; multi-word topics as exact phrases (approved by Yash)
TOPICS = {
    "gold": r"\bgold\b",
    "federal_reserve": r"\bfederal reserve\b",
    "us_dollar": r"\bus dollar\b",
    "inflation": r"\binflation\b",
    "geopolitical_conflict": r"\bgeopolitical conflict\b",
}
TOPIC_RES = {k: re.compile(p, re.IGNORECASE) for k, p in TOPICS.items()}
TITLE_RE = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>")

# GKG 2.1 column positions
COL_DATE, COL_SOURCE, COL_URL, COL_EXTRAS = 1, 3, 4, 26

csv.field_size_limit(2**31 - 1)
session = requests.Session()


def log(message):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z  {message}"
    print(line, flush=True)
    with open(OUT_DIR / "_progress.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def matching_rows(zip_bytes):
    """Yield (topics, row) for each article whose title mentions a topic."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        with z.open(z.namelist()[0]) as f:
            reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"),
                                delimiter="\t", quoting=csv.QUOTE_NONE)
            for row in reader:
                if len(row) <= COL_EXTRAS:
                    continue
                m = TITLE_RE.search(row[COL_EXTRAS])
                if not m:
                    continue
                title = html.unescape(m.group(1)).strip()
                topics = [k for k, rx in TOPIC_RES.items() if rx.search(title)]
                if topics:
                    yield topics, title, row


def fetch(stamp):
    """Download one 15-min file. Returns bytes, or None if GDELT has no file for that slot."""
    for attempt in range(4):
        try:
            r = session.get(BASE_URL.format(stamp=stamp), timeout=120)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            log(f"  {stamp}: {type(e).__name__}, retry {attempt + 1}")
    raise RuntimeError(f"could not download {stamp}")


def pull_day(day):
    path = OUT_DIR / f"{day:%Y%m%d}.jsonl"
    if path.exists():
        return
    records, missing, seen_urls = [], [], set()
    for i in range(96):
        slot = day + timedelta(minutes=15 * i)
        stamp = f"{slot:%Y%m%d%H%M%S}"
        content = fetch(stamp)
        if content is None:
            missing.append(stamp)
            continue
        for topics, title, row in matching_rows(content):
            url = row[COL_URL]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            records.append({
                "available_at_utc": slot.isoformat(),   # GDELT first-seen batch time
                "gkg_date": row[COL_DATE],
                "source": row[COL_SOURCE],
                "url": url,
                "title": title,
                "topics": topics,
            })
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps({"_meta": {"day_utc": f"{day:%Y-%m-%d}", "missing_slots": missing,
                                      "pulled_at_utc": datetime.now(timezone.utc).isoformat()}}) + "\n")
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tmp.replace(path)
    log(f"{day:%Y-%m-%d}  {len(records):5} headlines  ({len(missing)} missing 15-min files)")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    day = START
    while day < today:              # complete UTC days only
        pull_day(day)
        day += timedelta(days=1)
    log("done (complete UTC days only)")


if __name__ == "__main__":
    main()
