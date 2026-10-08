"""Phase E4-1: download US500 M1 bars from 2022-01-01 (gold M1 already exists).

US500 needs M1 bars for two things (spec §3 + Change Log v1.1): its H1 bars are built from M1
starting at :30 New York, and the engine checks stops on M1 bars. Steps:
  1. download M1 (server time) from 2022-01-01 to now -> data/raw/exp4/
  2. convert to UTC (server clock = New York + 7 h)
  3. spreads (spec §6): the broker recorded 0 before real spreads began; those bars get the
     75th-percentile real spread for the same London hour, measured on 2026 data (same method
     as gold, src/spread_model.py), flagged spread_estimated -> data/processed/exp4/

Never reads anything before 2022-01-01 (checked by src/data_access.py). Read-only: no trading calls.

Run:  .venv/Scripts/python -m src.exp4.pull_data
"""
from datetime import datetime, timezone

import pandas as pd

from src import data_mt5
from src.config import PROJECT_ROOT, load_settings
from src.data_access import check_window
from src.exp3.pull_data import to_utc
from src.spread_model import MODEL_FROM, apply_table, build_table

START = datetime(2022, 1, 1, tzinfo=timezone.utc)
SYMBOL = "US500.sim"
RAW = PROJECT_ROOT / "data" / "raw" / "exp4"
PROCESSED = PROJECT_ROOT / "data" / "processed" / "exp4"


def main():
    check_window(START, None, "Experiment 4 US500 M1 download")       # 2022+ only
    cfg = load_settings()["mt5"]
    data_mt5.connect(cfg["terminal_path"], cfg["connect_timeout_ms"])
    try:
        raw = data_mt5.pull_rates(SYMBOL, "M1", START, datetime.now(timezone.utc))
    finally:
        data_mt5.disconnect()
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(RAW / f"{SYMBOL}_M1.parquet", index=False)
    m1 = to_utc(raw)
    real = m1.spread > 0
    real_from = m1.time_utc[real & (m1.time_utc >= pd.Timestamp("2025-01-01", tz="UTC"))].min()
    table, _ = build_table(m1)
    m1 = apply_table(m1, table, real_from)
    m1.to_parquet(PROCESSED / f"{SYMBOL}_M1.parquet", index=False)
    print(f"{SYMBOL} M1: {len(m1):,} bars {m1.time_utc.iloc[0]} -> {m1.time_utc.iloc[-1]} UTC; "
          f"real spreads from {real_from}; estimated on {m1.spread_estimated.mean():.1%} of bars")
    print("London hour -> p75 spread (points):", dict(table))


if __name__ == "__main__":
    main()
