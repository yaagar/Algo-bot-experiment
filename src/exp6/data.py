"""Experiment 6 market data for one period: H1 bars, broker-day closes, USD conversion, spreads.

Plain English: for each of the 18 markets we load H1 bid bars for the period only (warm-ups never
cross a period boundary, spec §7), through src/data_access.py. FX prices come from MetaQuotes-Demo,
everything else from the FTMO account (Change Log v1.1 a). Daily closes are built from H1 bars by
broker day (server date; a broker day ends 17:00 New York), so every market uses the same clock.
Prices in a non-USD currency are converted with the matching USD pair's last H1 close.
Spreads: per server hour, the 75th percentile of 2026 FTMO tick spreads (Change Log v1.2).
"""
import copy
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
import yaml

from src.config import PROJECT_ROOT
from src.data_access import read_prices
from src.exp2.market import to_ns
from src.timeutils import utc_to_server

CONFIG_PATH = PROJECT_ROOT / "config" / "exp6.yaml"
PROCESSED = PROJECT_ROOT / "data" / "processed" / "exp6"
RESULTS = PROJECT_ROOT / "results" / "exp6"
COLS = ["time_utc", "open", "high", "low", "close"]
NS_HOUR = 3600 * 10**9

# quote currency -> (MetaQuotes pair, True if USD is that pair's base: USD per unit = 1 / price)
USD_PAIRS = {"JPY": ("USDJPY", True), "CAD": ("USDCAD", True), "ZAR": ("USDZAR", True),
             "PLN": ("USDPLN", True), "NOK": ("USDNOK", True), "SEK": ("USDSEK", True),
             "CHF": ("USDCHF", True), "NZD": ("NZDUSD", False), "AUD": ("AUDUSD", False),
             "GBP": ("GBPUSD", False), "EUR": ("EURUSD", False)}


def load_config(path=CONFIG_PATH):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def variant_config(cfg, name):
    out = copy.deepcopy(cfg)
    for key, value in cfg["variants"][name].items():
        if isinstance(value, dict):
            out[key].update(value)
        else:
            out[key] = value
    out["variant"] = name
    return out


def period(cfg, name):
    p = cfg["periods"][name]
    return pd.Timestamp(p["start"], tz="UTC"), (pd.Timestamp(p["end"], tz="UTC") if p["end"] else None)


def read_h1(symbol, cls, start, end):
    """H1 bid bars [start, end): FX from MetaQuotes-Demo (UTC-converted), others from the FTMO account."""
    if cls == "FX":
        pair = symbol.replace(".sim", "")
        path = PROCESSED / "metaquotes" / f"{pair}_H1.parquet"
        return read_prices(pair, "H1", start, end, columns=COLS, path=path).reset_index(drop=True)
    return read_prices(symbol, "H1", start, end, columns=COLS, path=PROCESSED / f"{symbol}_H1.parquet").reset_index(drop=True)


@dataclass
class Market:
    symbol: str
    cls: str                  # FX / Index / Metal / Commodity (asset group per config "classes")
    contract: float
    tick: float
    profit_ccy: str
    volume_min: float
    volume_step: float
    t: np.ndarray             # H1 bar open, UTC ns
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    spread_by_hour: np.ndarray   # price units, per server hour 0..23
    days: np.ndarray          # server dates (datetime64[D]) with a daily close
    day_close: np.ndarray     # close of the last H1 bar of each server date


def server_hour(t_ns):
    return ((pd.to_datetime(t_ns, utc=True).tz_convert("America/New_York").hour + 7) % 24).to_numpy()


def build_market(sym, meta, h1, tick_spreads, last_day=None):
    server = utc_to_server(h1.time_utc)
    day = server.dt.normalize().to_numpy().astype("datetime64[D]")
    if last_day is not None:                                    # keep whole broker days only
        keep = day <= last_day
        h1, day = h1[keep].reset_index(drop=True), day[keep]
    sp = np.array([np.nan if v is None else v for v in tick_spreads["p75_price_by_server_hour"]], dtype=float)
    sp[np.isnan(sp)] = np.nanmax(sp)                            # hour without ticks: the worst hour's spread
    weekday = pd.DatetimeIndex(day).dayofweek < 5
    closes = pd.Series(h1.close.to_numpy()[weekday]).groupby(day[weekday]).last()
    return Market(sym, meta["class"], meta["contract_size"], meta["tick_size"], meta["currency_profit"],
                  meta["volume_min"], meta["volume_step"], to_ns(h1.time_utc), h1.open.to_numpy(),
                  h1.high.to_numpy(), h1.low.to_numpy(), h1.close.to_numpy(), sp,
                  closes.index.to_numpy().astype("datetime64[D]"), closes.to_numpy())


@dataclass
class Conversion:
    """USD per 1 unit of a quote currency at time t (last H1 close at or before t)."""
    series: dict              # ccy -> (t ns array, usd-per-unit array)

    def usd_per(self, ccy, t_ns):
        if ccy == "USD":
            return 1.0
        t, v = self.series[ccy]
        j = int(np.searchsorted(t, t_ns, "right")) - 1
        return float(v[max(j, 0)])


def conversion_symbols(ccys):
    return [USD_PAIRS[c][0] + ".sim" for c in sorted(set(ccys) - {"USD"})]


def load_conversion(ccys, start, end, frames=None):
    series = {}
    for ccy in sorted(set(ccys) - {"USD"}):
        pair, usd_base = USD_PAIRS[ccy]
        sym = pair + ".sim"
        h1 = frames[sym] if frames is not None and sym in frames else read_h1(sym, "FX", start, end)
        t = to_ns(h1.time_utc) + NS_HOUR                       # a bar's close is known at its end
        series[ccy] = (t, 1.0 / h1.close.to_numpy() if usd_base else h1.close.to_numpy())
    return Conversion(series)


@dataclass
class Universe:
    markets: list
    conv: Conversion
    swaps: dict               # symbol -> (long %, short %)
    start: pd.Timestamp
    end: pd.Timestamp


def load_universe(cfg, period_name="gate", frames=None):
    """All markets for one period. `frames` = {symbol: H1 DataFrame} to reuse (e.g. scrambled) data."""
    start, end = period(cfg, period_name)
    meta = {s["symbol"]: s for s in json.loads((RESULTS / "e6_0_symbols.json").read_text(encoding="utf-8"))["symbols"]}
    ticks = json.loads((RESULTS / "e6_0_tick_spreads.json").read_text(encoding="utf-8"))["symbols"]
    swaps = pd.DataFrame(json.loads((RESULTS / "e6_0_swaps_locked.json").read_text(encoding="utf-8")))
    swaps = {r.symbol: (r.swap_long_pct, r.swap_short_pct) for r in swaps.itertuples()}
    last_day = None
    if end is not None:                                         # last broker day that ends before `end`
        last_day = (utc_to_server(pd.Series([end])).dt.normalize() - pd.Timedelta(days=1)).iloc[0].to_datetime64().astype("datetime64[D]")
    markets = []
    for cls, syms in cfg["universe"].items():
        for s in syms:
            h1 = frames[s] if frames is not None else read_h1(s, cls, start, end)
            markets.append(build_market(s, meta[s], h1, ticks[s], last_day))
    conv = load_conversion([m.profit_ccy for m in markets], start, end, frames)
    return Universe(markets, conv, swaps, start, end)


def load_frames(cfg, period_name="gate"):
    """Every H1 frame a run needs (markets + USD conversion pairs), so tests can scramble them all."""
    start, end = period(cfg, period_name)
    meta = {s["symbol"]: s for s in json.loads((RESULTS / "e6_0_symbols.json").read_text(encoding="utf-8"))["symbols"]}
    frames = {s: read_h1(s, cls, start, end) for cls, syms in cfg["universe"].items() for s in syms}
    for sym in conversion_symbols([meta[s]["currency_profit"] for s in frames]):
        frames.setdefault(sym, read_h1(sym, "FX", start, end))
    return frames
