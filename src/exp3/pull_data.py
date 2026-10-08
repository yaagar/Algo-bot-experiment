"""Phase E3-1: find the broker symbols, download D1 and H1 bars from 2022-01-01, record costs.

For each spec §3 market the broker offers:
  1. download D1 and H1 bars (server time) from 2022-01-01 to now -> data/raw/exp3/
  2. convert to UTC (server clock = New York + 7 h, verified in Experiment 1)
  3. spreads (spec §4): the broker recorded 0 before real spreads began; those bars get the
     75th percentile of real spreads at the daily-bar open hour (first H1 bar of each broker day),
     flagged spread_estimated. Each D1 bar carries its open hour's spread (fills happen at the open).
  4. record contract details, swap and commission -> results/exp3/market_specs.json

Never reads anything before 2022-01-01 (checked by src/data_access.py). Read-only: no trading calls.

Run:  .venv/Scripts/python -m src.exp3.pull_data
"""
import json
from datetime import datetime, timezone

import MetaTrader5 as mt5
import pandas as pd

from src import data_mt5
from src.config import load_settings
from src.data_access import check_window
from src.exp3.markets import MARKETS, PROCESSED, RAW, RESULTS, SPECS_PATH, find_symbol
from src.timeutils import server_to_utc

START = datetime(2022, 1, 1, tzinfo=timezone.utc)
SPREAD_PERCENTILE = 0.75
MT5_DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
PROVISIONAL_TRIPLE = "Wednesday"      # Experiment 2 clarification 3 (field read 7 = invalid on gold)


def triple_swap_day(mt5_value):
    """MT5 swap_rollover3days (0 = Sunday ... 6 = Saturday) -> (day name, from_broker)."""
    if 0 <= mt5_value <= 6:
        return MT5_DAYS[mt5_value], True
    return PROVISIONAL_TRIPLE, False


def to_utc(raw):
    bars = raw.copy()
    bars.insert(0, "time_utc", server_to_utc(bars.time_server))
    return bars[bars.time_utc.notna()].reset_index(drop=True)


def add_spreads(h1, d1):
    """spread_used / spread_estimated on H1 and D1 bars, and the estimate itself (points)."""
    real = h1.spread > 0
    real_from = h1.time_utc[real].min() if real.any() else None
    h1 = h1.assign(server_date=h1.time_server.dt.date)
    open_hour = h1.groupby("server_date").head(1)               # first H1 bar of each broker day
    real_open = open_hour[(open_hour.time_utc >= real_from) & (open_hour.spread > 0)] if real_from is not None \
        else open_hour.iloc[:0]
    estimate = float(round(real_open.spread.quantile(SPREAD_PERCENTILE))) if len(real_open) else None

    def apply(bars, spread):
        est = (bars.time_utc < real_from) | (spread <= 0) if real_from is not None else pd.Series(True, bars.index)
        bars = bars.copy()
        bars["spread_estimated"] = est.to_numpy()
        bars["spread_used"] = spread.where(~est, estimate).astype("int64").to_numpy()   # points, as for gold
        return bars

    h1 = apply(h1, h1.spread)
    first_h1 = h1.groupby("server_date").head(1).set_index("server_date")
    d1_date = d1.time_server.dt.date
    d1 = d1.copy()
    d1["spread"] = d1_date.map(first_h1.spread).fillna(0).to_numpy()   # open-hour spread of that day
    d1 = apply(d1, d1.spread)
    stats = {"real_spreads_from_utc": str(real_from) if real_from is not None else None,
             "open_hour_p75_points": estimate, "open_hour_days_measured": len(real_open),
             "d1_bars_estimated_pct": round(100 * d1.spread_estimated.mean(), 1)}
    return h1.drop(columns="server_date"), d1, stats


def symbol_record(market, symbol, h1, d1, spread_stats):
    i = mt5.symbol_info(symbol)
    triple, from_broker = triple_swap_day(i.swap_rollover3days)
    return {
        "market": market.name, "symbol": symbol, "asset_class": market.asset_class, "description": i.description,
        "currency_base": i.currency_base, "currency_profit": i.currency_profit,
        "contract_size": i.trade_contract_size, "volume_min": i.volume_min, "volume_step": i.volume_step,
        "volume_max": i.volume_max, "digits": i.digits, "point": i.point,
        "tick_size": i.trade_tick_size, "tick_value_now": i.trade_tick_value, "trade_calc_mode": i.trade_calc_mode,
        "commission_pct_per_side": market.commission_pct,
        "commission_per_lot_usd_per_side": market.commission_per_lot_usd,
        "swap_mode": i.swap_mode, "swap_long_pct_per_year": i.swap_long, "swap_short_pct_per_year": i.swap_short,
        "swap_rollover3days_field": i.swap_rollover3days, "triple_swap_day": triple,
        "triple_swap_day_from_broker": from_broker,
        "d1_bars": len(d1), "h1_bars": len(h1),
        "first_d1_utc": str(d1.time_utc.iloc[0]), "last_d1_utc": str(d1.time_utc.iloc[-1]),
        "first_h1_utc": str(h1.time_utc.iloc[0]), "last_h1_utc": str(h1.time_utc.iloc[-1]),
        **spread_stats,
    }


def main():
    check_window(START, None, "Experiment 3 MT5 download")       # 2022+ only
    cfg = load_settings()["mt5"]
    account = data_mt5.connect(cfg["terminal_path"], cfg["connect_timeout_ms"])
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    out = {"broker": account.company, "server": account.server, "pulled_at_utc": now.isoformat(),
           "markets": [], "not_available": []}
    try:
        names = [s.name for s in mt5.symbols_get() or []]
        for market in MARKETS:
            symbol = find_symbol(market, names)
            if symbol is None:
                out["not_available"].append(market.name)
                print(f"{market.name:14} not offered by the broker - skipped")
                continue
            mt5.symbol_select(symbol, True)
            raw = {tf: data_mt5.pull_rates(symbol, tf, START, now) for tf in ("D1", "H1")}
            for tf, bars in raw.items():
                bars.to_parquet(RAW / f"{symbol}_{tf}.parquet", index=False)
            h1, d1, stats = add_spreads(to_utc(raw["H1"]), to_utc(raw["D1"]))
            h1.to_parquet(PROCESSED / f"{symbol}_H1.parquet", index=False)
            d1.to_parquet(PROCESSED / f"{symbol}_D1.parquet", index=False)
            rec = symbol_record(market, symbol, h1, d1, stats)
            out["markets"].append(rec)
            print(f"{market.name:14} {symbol:12} D1 {len(d1):5}  H1 {len(h1):6}  from {rec['first_d1_utc'][:10]}")
    finally:
        data_mt5.disconnect()
    SPECS_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
