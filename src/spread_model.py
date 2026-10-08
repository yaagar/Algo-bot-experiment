"""Estimated spread for bars where the broker recorded none (spec §8, v1.2).

The broker's bars carry spread = 0 before 2025-12-17. For those bars (and the
rare later bar with spread 0) we use the 75th-percentile real spread for the
same London hour of day, measured on 2026 data. Every bar gets:
  spread_used       spread in points that the backtester charges
  spread_estimated  True where spread_used came from this table

Run after src.process_prices:  .venv/Scripts/python -m src.spread_model
"""
import json

import pandas as pd

from src.config import PROJECT_ROOT, load_settings
from src.timeutils import LONDON

PROCESSED = PROJECT_ROOT / "data" / "processed"
MODEL_FROM = pd.Timestamp("2026-01-01", tz="UTC")   # "2026 data"
PERCENTILE = 0.75


def london_hour(time_utc):
    return time_utc.dt.tz_convert(LONDON).dt.hour


def build_table(m1):
    """75th-percentile real spread (points) per London hour, from 2026 M1 bars."""
    real = m1[(m1.time_utc >= MODEL_FROM) & (m1.spread > 0)]
    table = real.groupby(london_hour(real.time_utc)).spread.quantile(PERCENTILE)
    counts = real.groupby(london_hour(real.time_utc)).size()
    if len(table) != 24:
        raise ValueError(f"spread table has {len(table)} hours, expected 24")
    return table.round().astype(int), counts


def apply_table(bars, table, real_from):
    """Add spread_used / spread_estimated columns."""
    estimated = (bars.time_utc < real_from) | (bars.spread <= 0)
    bars = bars.copy()
    bars["spread_estimated"] = estimated
    bars["spread_used"] = bars.spread.where(~estimated, london_hour(bars.time_utc).map(table)).astype(int)
    return bars


def main():
    symbol = load_settings()["mt5"]["symbol"]
    m1 = pd.read_parquet(PROCESSED / f"{symbol}_M1.parquet")
    real_from = m1.loc[m1.spread > 0, "time_utc"].iloc[0].normalize()   # first day with real spreads
    table, counts = build_table(m1)

    for tf in ("M1", "M15", "H1"):
        path = PROCESSED / f"{symbol}_{tf}.parquet"
        bars = apply_table(pd.read_parquet(path), table, real_from)
        bars.to_parquet(path, index=False)
        print(f"{tf:4} estimated spread on {bars.spread_estimated.mean():6.1%} of bars")

    model = {
        "method": f"{int(PERCENTILE * 100)}th percentile of real M1 bar spread per London hour, 2026 data",
        "real_spreads_from_utc": str(real_from),
        "model_data_from_utc": str(MODEL_FROM),
        "points_by_london_hour": {int(h): int(v) for h, v in table.items()},
        "m1_bars_per_hour": {int(h): int(v) for h, v in counts.items()},
    }
    (PROCESSED / "spread_model_p75.json").write_text(json.dumps(model, indent=2), encoding="utf-8")
    print("\nLondon hour -> spread (points, x0.001 = $)")
    print("  " + "  ".join(f"{h:02d}:{v}" for h, v in table.items()))


if __name__ == "__main__":
    main()
