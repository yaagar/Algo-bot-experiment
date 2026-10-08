"""Phase 1 check: connect to MT5, detect gold, print symbol info and server time.

Run:  .venv/Scripts/python -m src.check_mt5
Reads only. Pulls no history and places no trades.
"""
from src.config import load_settings
from src import data_mt5

STALE_TICK_SECONDS = 120


def main():
    settings = load_settings()
    mt5_cfg = settings["mt5"]

    account = data_mt5.connect(mt5_cfg["terminal_path"], mt5_cfg["connect_timeout_ms"])
    try:
        print("== Connection")
        print(f"  broker:  {account.company}")
        print(f"  server:  {account.server}")
        print(f"  demo:    {account.trade_mode == 0}")
        print(f"  balance: {account.balance:.2f} {account.currency}")

        symbol, candidates = data_mt5.resolve_symbol(mt5_cfg["symbol"])
        print("\n== Gold symbol")
        print(f"  chosen:     {symbol}")
        print(f"  candidates: {candidates}")
        for key, value in data_mt5.symbol_specs(symbol).items():
            print(f"  {key:18} {value}")

        t = data_mt5.server_time_estimate(symbol)
        print("\n== Server time (first estimate; verified properly in Phase 2)")
        print(f"  last tick, server time: {t['server_time_of_last_tick']}")
        print(f"  UTC now:                {t['utc_now']}")
        print(f"  estimated offset:       UTC{t['offset_hours']:+d}")
        print(f"  last tick age:          {t['last_tick_age_seconds']} s")
        print(f"  bid / ask:              {t['bid']} / {t['ask']}")
        if abs(t["last_tick_age_seconds"]) > STALE_TICK_SECONDS:
            print("  WARNING: last tick is stale (market closed?) - offset estimate unreliable.")
    finally:
        data_mt5.disconnect()


if __name__ == "__main__":
    main()
