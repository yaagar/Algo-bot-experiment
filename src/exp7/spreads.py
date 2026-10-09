"""Exp 7 spread model (spec v0.10 §3): the 75th percentile of tick spread per broker-server hour as a
FRACTION OF PRICE, from all 2026 gold ticks. Cost of a fill = that fraction x the bar's price.

    .venv/Scripts/python -m src.exp7.spreads      (MT5 terminal must be running; read-only)
"""
import json
from datetime import datetime, timezone

import numpy as np

from src import data_mt5
from src.config import PROJECT_ROOT, load_settings
from src.data_access import check_window

TICKS_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)      # 2026 ticks only feed the cost model
BIN = 1e-6                                                  # histogram bin: one millionth of price
OUT = PROJECT_ROOT / "results" / "exp7" / "e7_tick_spread_frac.json"


def p75_bin(row):
    n = row.sum()
    return int(np.searchsorted(np.cumsum(row), 0.75 * n)) if n else None


def build(symbol="XAUUSD.sim"):
    check_window(TICKS_FROM, None, "Experiment 7 gold tick spreads (fraction of price)")
    cfg = load_settings()["mt5"]
    data_mt5.connect(cfg["terminal_path"], cfg["connect_timeout_ms"])
    now = datetime.now(timezone.utc)
    try:
        hist, months = data_mt5.tick_spread_histograms(symbol, TICKS_FROM, now, BIN, of_price=True)
    finally:
        data_mt5.disconnect()
    p75 = [p75_bin(hist[h]) for h in range(24)]
    out = {"method": "75th percentile of tick (ask - bid) / bid per broker-server hour of day, 2026 ticks",
           "symbol": symbol, "pulled_at_utc": now.isoformat(), "months": months, "ticks": int(hist.sum()),
           "ticks_by_server_hour": [int(x) for x in hist.sum(axis=1)],
           "p75_frac_by_server_hour": [None if v is None else v * BIN for v in p75]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"{symbol}: {out['ticks']:,} ticks {months[0]}..{months[-1]}")


if __name__ == "__main__":
    build()
