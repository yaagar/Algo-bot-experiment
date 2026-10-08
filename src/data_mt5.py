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
