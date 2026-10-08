"""Phase 2: download all available M1 / M15 / H1 gold bars from MT5 (spec §8).

Saves raw bars (broker server time, exactly as MT5 gives them) to
data/raw/<symbol>_<TF>.parquet plus a metadata JSON. Conversion to UTC
happens separately in src/timeutils.py once the server offset is verified.

Run:  .venv/Scripts/python -m src.pull_prices
"""
import json
from datetime import datetime, timezone

from src import data_mt5
from src.config import PROJECT_ROOT, load_settings

RAW_DIR = PROJECT_ROOT / "data" / "raw"
SEARCH_FROM = datetime(2010, 1, 1, tzinfo=timezone.utc)   # earlier than any broker history here


def main():
    settings = load_settings()
    cfg = settings["mt5"]
    account = data_mt5.connect(cfg["terminal_path"], cfg["connect_timeout_ms"])
    try:
        symbol, _ = data_mt5.resolve_symbol(cfg["symbol"])
        specs = data_mt5.symbol_specs(symbol)
        now = datetime.now(timezone.utc)
        coverage = {}
        for tf in ("H1", "M15", "M1"):
            bars = data_mt5.pull_rates(symbol, tf, SEARCH_FROM, now)
            path = RAW_DIR / f"{symbol}_{tf}.parquet"
            bars.to_parquet(path, index=False)
            coverage[tf] = {
                "file": path.name,
                "bars": len(bars),
                "first_server_time": str(bars["time_server"].iloc[0]),
                "last_server_time": str(bars["time_server"].iloc[-1]),
            }
            print(f"{tf:4} {len(bars):>9,} bars  {coverage[tf]['first_server_time']} -> {coverage[tf]['last_server_time']}  (server time)")
        meta = {
            "symbol": symbol,
            "broker": account.company,
            "server": account.server,
            "contract_size": specs["contract_size"],
            "volume_step": specs["volume_step"],
            "volume_min": specs["volume_min"],
            "digits": specs["digits"],
            "point": specs["point"],
            "pulled_at_utc": now.isoformat(),
            "times_are": "broker server wall-clock time (not UTC)",
            "spread_units": "points (x point = price units)",
            "coverage": coverage,
        }
        (RAW_DIR / f"{symbol}_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    finally:
        data_mt5.disconnect()


if __name__ == "__main__":
    main()
