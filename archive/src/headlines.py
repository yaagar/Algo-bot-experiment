"""Download news headlines from the GDELT 2.0 DOC API (spec §8, needed for Bot B).

The DOC API only searches roughly the last 3 months, so this pulls the OLDEST
days first (from 2026-07-01) before they age out. One saved JSON file per
query per UTC day, so the download can stop and resume without losing work.

GDELT's 'seendate' (first time GDELT saw the article, UTC) is the time we later
treat as "available at" for Claude.

Run:  .venv/Scripts/python -m src.headlines
"""
import json
import time
from datetime import datetime, timedelta, timezone

import requests

from src.config import PROJECT_ROOT

API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
OUT_DIR = PROJECT_ROOT / "data" / "raw" / "gdelt"
START_DATE = datetime(2026, 7, 1, tzinfo=timezone.utc)

# spec §8 queries. Multi-word topics are quoted as phrases; English sources only.
QUERIES = {
    "gold": 'gold',
    "federal_reserve": '"Federal Reserve"',
    "us_dollar": '"US dollar"',
    "inflation": 'inflation',
    "geopolitical_conflict": '"geopolitical conflict"',
}
LANGUAGE_FILTER = "sourcelang:english"

MAX_RECORDS = 250                 # GDELT's per-request cap
MIN_WINDOW = timedelta(hours=1)   # stop splitting below this
SECONDS_BETWEEN_REQUESTS = 6      # GDELT asks for <= 1 request / 5 s
BACKOFF_START, BACKOFF_MAX = 60, 900


def gdelt_time(dt):
    return dt.strftime("%Y%m%d%H%M%S")


def log(message):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z  {message}"
    print(line, flush=True)
    with open(OUT_DIR / "_progress.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def request_window(query, start, end):
    """One API call. Retries politely on rate limits / bad responses."""
    params = {
        "query": f"{query} {LANGUAGE_FILTER}",
        "mode": "ArtList",
        "format": "json",
        "maxrecords": MAX_RECORDS,
        "sort": "DateAsc",
        "startdatetime": gdelt_time(start),
        "enddatetime": gdelt_time(end),
    }
    wait = BACKOFF_START
    while True:
        time.sleep(SECONDS_BETWEEN_REQUESTS)
        try:
            r = requests.get(API_URL, params=params, timeout=60,
                             headers={"User-Agent": "gold-experiment research (low volume)"})
            if r.status_code == 200:
                text = r.text.strip()
                if not text or text == "{}":
                    return []
                return json.loads(text).get("articles", [])
            reason = f"HTTP {r.status_code}"
        except (requests.RequestException, json.JSONDecodeError) as e:
            reason = type(e).__name__
        log(f"  {reason} — waiting {wait}s")
        time.sleep(wait)
        wait = min(wait * 2, BACKOFF_MAX)


def fetch_range(query, start, end, calls):
    """Fetch [start, end). If GDELT hits its 250 cap, split the window in half."""
    articles = request_window(query, start, end)
    truncated = len(articles) >= MAX_RECORDS
    if truncated and end - start > MIN_WINDOW:
        mid = start + (end - start) / 2
        return fetch_range(query, start, mid, calls) + fetch_range(query, mid, end, calls)
    calls.append({"start": start.isoformat(), "end": end.isoformat(),
                  "n": len(articles), "truncated": truncated})
    return articles


def pull_day(key, query, day_start):
    path = OUT_DIR / key / f"{day_start:%Y%m%d}.json"
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    calls = []
    articles = fetch_range(query, day_start, day_start + timedelta(days=1), calls)
    record = {
        "query_key": key,
        "query": f"{query} {LANGUAGE_FILTER}",
        "day_utc": f"{day_start:%Y-%m-%d}",
        "pulled_at_utc": datetime.now(timezone.utc).isoformat(),
        "calls": calls,
        "articles": articles,   # raw GDELT records; 'seendate' = first-seen UTC
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    capped = sum(c["truncated"] for c in calls)
    log(f"{key:22} {day_start:%Y-%m-%d}  {len(articles):5} articles  {len(calls)} calls"
        + (f"  ({capped} window(s) still capped at 250)" if capped else ""))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    day = START_DATE
    while day < today:                      # oldest first: they age out first
        for key, query in QUERIES.items():
            pull_day(key, query, day)
        day += timedelta(days=1)
    log("done (complete UTC days only; today is pulled on a later run)")


if __name__ == "__main__":
    main()
