"""Phase 2: convert raw MT5 bars (server time) to UTC and save to data/processed/.

Run:  .venv/Scripts/python -m src.process_prices
"""
import json

import pandas as pd

from src.config import PROJECT_ROOT, load_settings
from src.timeutils import server_offset_hours, server_to_utc

RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUT_DIR = PROJECT_ROOT / "data" / "processed"


def process(symbol, tf):
    raw = pd.read_parquet(RAW_DIR / f"{symbol}_{tf}.parquet")
    bars = raw.copy()
    bars.insert(0, "time_utc", server_to_utc(bars.time_server))   # tz-aware UTC
    bars.insert(1, "server_offset_h", server_offset_hours(bars.time_server).values)
    unconvertible = bars.time_utc.isna()
    bars = bars[~unconvertible].reset_index(drop=True)
    bars.to_parquet(OUT_DIR / f"{symbol}_{tf}.parquet", index=False)
    return {
        "bars": len(bars),
        "dropped_unconvertible": int(unconvertible.sum()),   # DST-switch hour, market closed
        "first_utc": str(bars.time_utc.iloc[0]),
        "last_utc": str(bars.time_utc.iloc[-1]),
        "offsets_seen_h": sorted(bars.server_offset_h.unique().tolist()),
        "first_bar_with_spread_utc": str(bars.loc[bars.spread > 0, "time_utc"].iloc[0]),
    }


def main():
    symbol = load_settings()["mt5"]["symbol"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {tf: process(symbol, tf) for tf in ("H1", "M15", "M1")}
    (OUT_DIR / f"{symbol}_coverage.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
