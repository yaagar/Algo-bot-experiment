"""Phase E6-0: inventory every symbol on the FTMO MT5 account and download D1 + H1 bars from 2022.

Plain English (spec §3, §10): ask MT5 for every symbol (symbols_get), record its contract details,
swap, margin and current spread, then download daily and hourly bars from 2022-01-01 to now for every
non-crypto symbol, convert to UTC (server clock = New York + 7 h) and save them. No returns, no signals.

Read-only (no order or margin calls: tests/test_phase1.py bans them). MT5's Python package has no
trading-session call, so sessions are described from the hours that have H1 bars in 2026.
Never reads anything before 2022-01-01 (checked by src/data_access.py).

Run:  .venv/Scripts/python -m src.exp6.pull_data                 (FTMO terminal: inventory + bars)
      .venv/Scripts/python -m src.exp6.pull_data --ticks         (FTMO terminal: tick-spread table, v1.2)
      .venv/Scripts/python -m src.exp6.pull_data --metaquotes    (FX prices, MetaQuotes-Demo terminal)

Change Log v1.1 (a): FX PRICES for 2022+ come from MetaQuotes-Demo (the FTMO account's FX history only
starts 2025-05-19); FX COSTS stay FTMO's. MetaQuotes' server clock follows European summer time, so its
bars go through exp3's to_utc_metaquotes; daily bars are later rebuilt from H1 at New York 17:00.
"""
import json
from datetime import datetime, timezone

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from src import data_mt5
from src.config import PROJECT_ROOT, load_settings
from src.data_access import check_window
from src.exp3.pull_data import METAQUOTES_TERMINAL, to_utc, to_utc_metaquotes
from src.timeutils import NEW_YORK

START = datetime(2022, 1, 1, tzinfo=timezone.utc)
RAW = PROJECT_ROOT / "data" / "raw" / "exp6"
PROCESSED = PROJECT_ROOT / "data" / "processed" / "exp6"
RESULTS = PROJECT_ROOT / "results" / "exp6"
REAL_SPREAD_CHECK_FROM = pd.Timestamp("2025-01-01", tz="UTC")
SPREAD_YEAR = pd.Timestamp("2026-01-01", tz="UTC")


def asset_class(info):
    p = info.path.lower()
    if "crypto" in p:
        return "Crypto"
    if "indices" in p:
        return "Index"
    if "commodities" in p:
        return "Metal" if info.currency_base in ("XAU", "XAG") or info.name.startswith(("XAU", "XAG")) else "Commodity"
    if "fx" in p:
        return "FX"
    return "Other"


def record(info, account_ccy):
    return {
        "symbol": info.name, "class": asset_class(info), "path": info.path, "description": info.description,
        "currency_base": info.currency_base, "currency_profit": info.currency_profit,
        "currency_margin": info.currency_margin, "account_currency": account_ccy,
        "contract_size": info.trade_contract_size, "volume_min": info.volume_min, "volume_step": info.volume_step,
        "volume_max": info.volume_max, "digits": info.digits, "point": info.point,
        "tick_size": info.trade_tick_size, "tick_value_now": info.trade_tick_value,
        "trade_calc_mode": info.trade_calc_mode, "commission_in_symbol_info": None,     # not exposed by MT5
        "swap_mode": info.swap_mode, "swap_long": info.swap_long, "swap_short": info.swap_short,
        "swap_rollover3days": info.swap_rollover3days,
        "margin_initial_field": info.margin_initial, "margin_maintenance_field": info.margin_maintenance,
        "spread_points_now": info.spread, "visible_in_market_watch": info.visible,
    }


def coverage(d1, h1, point):
    """Start, end, gaps and spread facts for one symbol (no prices or returns)."""
    days = pd.DatetimeIndex(d1.time_server.dt.normalize())
    weekdays = pd.bdate_range(days.min(), days.max())
    t = h1.time_utc
    gaps_h = t.diff().dt.total_seconds().div(3600)
    real = h1[(h1.spread > 0) & (h1.time_utc >= REAL_SPREAD_CHECK_FROM)]
    real_from = real.time_utc.min() if len(real) else None
    ny = h1.time_utc.dt.tz_convert(NEW_YORK)
    at10 = h1[(ny.dt.hour == 10) & (h1.time_utc >= SPREAD_YEAR) & (h1.spread > 0)]
    hours = ny[h1.time_utc >= SPREAD_YEAR].dt.hour.value_counts()
    weeks = max(1.0, (t.max() - SPREAD_YEAR).days / 7)
    return {
        "d1_first_utc": str(d1.time_utc.min()), "d1_last_utc": str(d1.time_utc.max()), "d1_bars": len(d1),
        "d1_missing_weekdays": int(len(weekdays.difference(days))),
        "d1_years_2022_2025": round(((d1.time_utc < pd.Timestamp("2026-01-01", tz="UTC")).sum()) / 252, 2),
        "h1_first_utc": str(t.min()), "h1_last_utc": str(t.max()), "h1_bars": len(h1),
        "h1_gaps_over_2h_within_week": int(((gaps_h > 2) & (gaps_h < 48)).sum()),
        "h1_largest_gap_h": float(gaps_h.max()),
        "real_spread_from_utc": str(real_from) if real_from is not None else None,
        "spread_p75_points_10ny_2026": float(at10.spread.quantile(0.75)) if len(at10) else None,
        "spread_p75_price_10ny_2026": float(at10.spread.quantile(0.75) * point) if len(at10) else None,
        "h1_bars_per_week_2026": round(hours.sum() / weeks, 1),
        "ny_hours_with_bars_2026": int((hours > 0.5 * hours.max()).sum()) if len(hours) else 0,
    }


def main():
    check_window(START, None, "Experiment 6 MT5 download")       # 2022+ only
    cfg = load_settings()["mt5"]
    account = data_mt5.connect(cfg["terminal_path"], cfg["connect_timeout_ms"])
    now = datetime.now(timezone.utc)
    for d in (RAW, PROCESSED, RESULTS):
        d.mkdir(parents=True, exist_ok=True)
    out = {"broker": account.company, "server": account.server, "account_currency": account.currency,
           "account_leverage": account.leverage, "pulled_at_utc": now.isoformat(),
           "clock_estimate": None, "symbols": []}
    try:
        symbols = mt5.symbols_get() or []
        for info in symbols:
            mt5.symbol_select(info.name, True)
            info = mt5.symbol_info(info.name)
            rec = record(info, account.currency)
            if rec["class"] != "Crypto":
                raw = {tf: data_mt5.pull_rates(info.name, tf, START, now) for tf in ("D1", "H1")}
                for tf, bars in raw.items():
                    bars.to_parquet(RAW / f"{info.name}_{tf}.parquet", index=False)
                d1, h1 = to_utc(raw["D1"]), to_utc(raw["H1"])
                d1.to_parquet(PROCESSED / f"{info.name}_D1.parquet", index=False)
                h1.to_parquet(PROCESSED / f"{info.name}_H1.parquet", index=False)
                rec.update(coverage(d1, h1, info.point))
            out["symbols"].append(rec)
            print(f"{info.name:12} {rec['class']:9} {rec.get('d1_first_utc', 'not pulled (crypto)')[:10]}", flush=True)
        xau = mt5.symbol_info_tick("XAUUSD.sim")
        if xau is not None:
            out["clock_estimate"] = data_mt5.server_time_estimate("XAUUSD.sim", now)
    finally:
        data_mt5.disconnect()
    (RESULTS / "e6_0_symbols.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(out["symbols"]).to_csv(RESULTS / "e6_0_symbols.csv", index=False)


def pull_metaquotes_fx(terminal_path=METAQUOTES_TERMINAL):
    """D1 + H1 from 2022-01-01 for every FTMO FX pair MetaQuotes-Demo offers (name without '.sim')."""
    check_window(START, None, "Experiment 6 MetaQuotes-Demo FX download")      # 2022+ only
    ftmo = json.loads((RESULTS / "e6_0_symbols.json").read_text(encoding="utf-8"))["symbols"]
    pairs = [s["symbol"].replace(".sim", "") for s in ftmo if s["class"] == "FX"]
    account = data_mt5.connect(terminal_path)
    if account.server != "MetaQuotes-Demo":
        data_mt5.disconnect()
        raise ConnectionError(f"expected MetaQuotes-Demo, terminal is on {account.server}")
    raw_dir, out_dir = RAW / "metaquotes", PROCESSED / "metaquotes"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    offered = {s.name for s in mt5.symbols_get() or []}
    rows = []
    try:
        for pair in pairs:
            if pair not in offered:
                rows.append({"pair": pair, "offered": False})
                continue
            mt5.symbol_select(pair, True)
            rec = {"pair": pair, "offered": True}
            for tf in ("D1", "H1"):
                raw = data_mt5.pull_rates(pair, tf, START, now)
                if raw.empty:
                    continue
                raw.to_parquet(raw_dir / f"{pair}_{tf}.parquet", index=False)
                bars = to_utc_metaquotes(raw)
                bars.to_parquet(out_dir / f"{pair}_{tf}.parquet", index=False)
                rec[f"{tf}_first_utc"], rec[f"{tf}_last_utc"], rec[f"{tf}_bars"] = str(bars.time_utc.min()), str(bars.time_utc.max()), len(bars)
                if tf == "H1":
                    gaps = bars.time_utc.diff().dt.total_seconds().div(3600)
                    rec["H1_largest_gap_h"] = float(gaps.max())
                    rec["H1_gaps_over_72h"] = int((gaps > 72).sum())          # longer than a weekend
            rows.append(rec)
            print(pair, rec.get("H1_first_utc", "no data")[:10], rec.get("H1_last_utc", "")[:10], flush=True)
    finally:
        data_mt5.disconnect()
    pd.DataFrame(rows).to_csv(RESULTS / "e6_0_metaquotes_fx_coverage.csv", index=False)
    (RESULTS / "e6_0_metaquotes_fx_coverage.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


TICKS_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
FALLBACK_FROM = datetime(2025, 10, 1, tzinfo=timezone.utc)      # most recent 3 months before 2026


def p75_from_hist(row):
    """Smallest spread (points) with at least 75% of ticks at or below it; None if the hour has no ticks."""
    n = row.sum()
    return int(np.searchsorted(np.cumsum(row), 0.75 * n)) if n else None


def tick_spread_table():
    """Change Log v1.2: per symbol and broker hour, the 75th percentile of tick spreads (ask - bid),
    all 2026 ticks on the FTMO terminal (fallback: Oct-Dec 2025 if a symbol has no 2026 ticks)."""
    check_window(TICKS_FROM, None, "Experiment 6 FTMO tick spreads")              # 2026 data only
    symbols = [s for s in json.loads((RESULTS / "e6_0_symbols.json").read_text(encoding="utf-8"))["symbols"]
               if s["class"] != "Crypto"]
    cfg = load_settings()["mt5"]
    data_mt5.connect(cfg["terminal_path"], cfg["connect_timeout_ms"])
    now = datetime.now(timezone.utc)
    out = {"method": "75th percentile of tick spread (ask - bid) per broker-server hour of day",
           "pulled_at_utc": now.isoformat(), "symbols": {}}
    try:
        for s in symbols:
            hist, months = data_mt5.tick_spread_histograms(s["symbol"], TICKS_FROM, now, s["point"])
            window = "2026"
            if hist.sum() == 0:
                hist, months = data_mt5.tick_spread_histograms(s["symbol"], FALLBACK_FROM, TICKS_FROM, s["point"])
                window = "fallback 2025-10..12"
            p75 = [p75_from_hist(hist[h]) for h in range(24)]
            out["symbols"][s["symbol"]] = {
                "class": s["class"], "point": s["point"], "window": window, "months": months,
                "ticks": int(hist.sum()), "ticks_by_server_hour": [int(x) for x in hist.sum(axis=1)],
                "p75_points_by_server_hour": p75,
                "p75_price_by_server_hour": [None if v is None else v * s["point"] for v in p75]}
            print(f"{s['symbol']:12} {int(hist.sum()):>11,} ticks  {months[0] if months else '-'}..{months[-1] if months else '-'}", flush=True)
    finally:
        data_mt5.disconnect()
    (RESULTS / "e6_0_tick_spreads.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    import sys
    if "--metaquotes" in sys.argv:
        pull_metaquotes_fx()
    elif "--ticks" in sys.argv:
        tick_spread_table()
    else:
        main()
