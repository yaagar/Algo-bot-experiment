"""Read-only access to the MT5 terminal.

This project NEVER trades. Only connection, symbol info and price-reading
functions from the MetaTrader5 package are allowed here (no order_send etc.).
"""
from datetime import datetime, timezone

import MetaTrader5 as mt5


def connect(terminal_path, timeout_ms=60000):
    """Attach to the already-running, already-logged-in terminal. No credentials are passed."""
    if not mt5.initialize(path=terminal_path, timeout=timeout_ms):
        raise ConnectionError(f"MT5 initialize failed: {mt5.last_error()}  (path: {terminal_path})")
    account = mt5.account_info()
    if account is None or not mt5.terminal_info().connected:
        mt5.shutdown()
        raise ConnectionError("MT5 started but is not logged in to a trade server. Log in inside MT5 first.")
    return account


def disconnect():
    mt5.shutdown()


def pick_gold_symbol(symbols):
    """Choose the XAU/USD symbol from the broker's symbol list.

    Matches on currencies (base XAU, profit USD) rather than the name, because
    brokers name it differently (XAUUSD, XAUUSD., GOLD, XAUUSD.sim ...).
    If several match, prefer plain "XAUUSD", then the shortest name, so the
    choice is always the same.
    """
    candidates = [s.name for s in symbols
                  if s.currency_base == "XAU" and s.currency_profit == "USD"]
    if not candidates:
        candidates = [s.name for s in symbols
                      if s.name.upper().startswith(("XAUUSD", "GOLD"))]
    if not candidates:
        raise LookupError("No gold (XAU/USD) symbol found on this broker.")
    candidates.sort(key=lambda name: (name.upper() != "XAUUSD", len(name), name))
    return candidates[0], candidates


def resolve_symbol(setting):
    """Use the symbol named in settings, or detect it when the setting is 'auto'."""
    if setting and setting != "auto":
        return setting, [setting]
    return pick_gold_symbol(mt5.symbols_get() or [])


def symbol_specs(symbol):
    """Contract details the backtester needs (spec §5.9 and §8 metadata)."""
    if not mt5.symbol_select(symbol, True):
        raise LookupError(f"Could not select {symbol} in Market Watch: {mt5.last_error()}")
    info = mt5.symbol_info(symbol)
    return {
        "symbol": info.name,
        "description": info.description,
        "contract_size": info.trade_contract_size,
        "volume_min": info.volume_min,
        "volume_step": info.volume_step,
        "volume_max": info.volume_max,
        "digits": info.digits,
        "point": info.point,
        "tick_size": info.trade_tick_size,
        "tick_value": info.trade_tick_value,
        "currency_base": info.currency_base,
        "currency_profit": info.currency_profit,
        "spread_points_now": info.spread,
        "spread_float": info.spread_float,
    }


def server_time_estimate(symbol, now_utc=None):
    """Estimate the broker's server-time offset from UTC using the latest tick.

    MT5 stamps ticks in server time but labels them as if they were UTC, so
    (tick time - real UTC now) ~= the server's offset. Only trustworthy while
    the market is open and ticking; a stale tick gives a wrong offset, which is
    why we also return the tick's age. Phase 2 verifies the offset properly
    against NFP releases (spec §8) — this is just a first look.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise LookupError(f"No tick for {symbol}: {mt5.last_error()}")
    server_now = datetime.fromtimestamp(tick.time, timezone.utc).replace(tzinfo=None)
    raw_gap_s = tick.time - now_utc.timestamp()
    offset_hours = round(raw_gap_s / 3600)
    tick_age_s = offset_hours * 3600 - raw_gap_s   # how old the last tick is
    return {
        "server_time_of_last_tick": server_now,
        "utc_now": now_utc.replace(tzinfo=None, microsecond=0),
        "offset_hours": offset_hours,
        "last_tick_age_seconds": round(tick_age_s),
        "bid": tick.bid,
        "ask": tick.ask,
    }


TIMEFRAMES = {"M1": mt5.TIMEFRAME_M1, "M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1, "D1": mt5.TIMEFRAME_D1}


def month_starts(first, last):
    """First day of each month from `first` to `last` inclusive (tz-aware UTC)."""
    current = datetime(first.year, first.month, 1, tzinfo=timezone.utc)
    while current <= last:
        yield current
        current = datetime(current.year + current.month // 12, current.month % 12 + 1, 1,
                           tzinfo=timezone.utc)


def pull_rates(symbol, timeframe, first, last):
    """All bars between `first` and `last`, pulled one month at a time.

    Times in and out are BROKER SERVER wall-clock time (MT5 stores bars that
    way). Datetimes passed to MT5 must be timezone-aware: a naive datetime is
    silently read as this PC's local time and shifts the request by hours.

    Monthly chunks keep each request small. Bars outside the requested month
    are dropped: when a month has no data, MT5 returns its oldest bar instead
    of nothing, which would otherwise sneak in as a fake duplicate.
    """
    import pandas as pd

    tf = TIMEFRAMES[timeframe]
    chunks = []
    for start in month_starts(first, last):
        end = datetime(start.year + start.month // 12, start.month % 12 + 1, 1, tzinfo=timezone.utc)
        rates = mt5.copy_rates_range(symbol, tf, start, end)
        if rates is None or len(rates) == 0:
            continue
        df = pd.DataFrame(rates)
        df["time_server"] = pd.to_datetime(df["time"], unit="s")
        df = df[(df["time_server"] >= start.replace(tzinfo=None)) & (df["time_server"] < end.replace(tzinfo=None))]
        chunks.append(df.drop(columns="time"))
    if not chunks:
        return pd.DataFrame()
    out = pd.concat(chunks).drop_duplicates("time_server").sort_values("time_server").reset_index(drop=True)
    return out[["time_server", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]


def tick_spread_histograms(symbol, first, last, point):
    """Spread (ask - bid, in points) of every tick between `first` and `last`, as one histogram per
    broker-server hour of day: returns (counts[24, max_points + 1], months seen). Pulled one day at a
    time (tick history is large); ticks missing a bid or ask are skipped. Read-only."""
    import numpy as np
    from datetime import timedelta

    hist = np.zeros((24, 1), dtype=np.int64)
    months = set()
    day = first
    while day < last:
        nxt = min(day + timedelta(days=1), last)
        ticks = mt5.copy_ticks_range(symbol, day, nxt, mt5.COPY_TICKS_INFO)
        if ticks is not None and len(ticks):
            ok = (ticks["bid"] > 0) & (ticks["ask"] > 0)
            t = ticks[ok]
            pts = np.maximum(np.rint((t["ask"] - t["bid"]) / point).astype(np.int64), 0)
            hour = (t["time_msc"] // 3_600_000) % 24                 # tick times are server wall-clock
            if pts.max(initial=0) >= hist.shape[1]:
                hist = np.pad(hist, ((0, 0), (0, int(pts.max()) + 1 - hist.shape[1])))
            np.add.at(hist, (hour, pts), 1)
            months.add(day.strftime("%Y-%m"))
        day = nxt
    return hist, sorted(months)
