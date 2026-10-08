"""Phase 2: check our P&L + commission formulas against real trades on the demo account.

Reads the account's closed gold trades from MT5 history (read-only) and
compares, for each trade, what the broker booked with what src/pnl.py
calculates from the same prices and lot size.

To test: place a 0.01-lot gold trade by hand in MT5, close it, then run
  .venv/Scripts/python -m src.check_pnl
"""
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5

from src import data_mt5
from src.config import commission_usd, load_settings
from src.pnl import gross_pnl_usd

CENT = 0.005   # broker rounds to cents


def closed_trades(symbol):
    # Deal times are server time (up to 3 h ahead of UTC), so search to a day past now
    until = datetime.now(timezone.utc) + timedelta(days=1)
    deals = mt5.history_deals_get(datetime(2020, 1, 1, tzinfo=timezone.utc), until) or []
    by_position = {}
    for d in deals:
        if d.symbol == symbol and d.entry in (mt5.DEAL_ENTRY_IN, mt5.DEAL_ENTRY_OUT):
            by_position.setdefault(d.position_id, []).append(d)
    for legs in by_position.values():
        entry = [d for d in legs if d.entry == mt5.DEAL_ENTRY_IN]
        exit_ = [d for d in legs if d.entry == mt5.DEAL_ENTRY_OUT]
        if len(entry) == 1 and len(exit_) == 1:
            yield entry[0], exit_[0]


def main():
    settings = load_settings()
    cfg, pct = settings["mt5"], settings["costs"]["commission_pct_per_side"]
    data_mt5.connect(cfg["terminal_path"], cfg["connect_timeout_ms"])
    try:
        symbol = cfg["symbol"]
        contract = data_mt5.symbol_specs(symbol)["contract_size"]
        print(f"{'opened (server)':19} {'dir':5} {'lots':>5} {'entry':>9} {'exit':>9} | "
              f"{'P&L broker':>10} {'ours':>7} | {'comm broker':>11} {'ours':>6} | ok")
        all_ok, n = True, 0
        for e, x in closed_trades(symbol):
            direction = 1 if e.type == mt5.DEAL_TYPE_BUY else -1
            ours_pnl = gross_pnl_usd(direction, e.price, x.price, e.volume, contract)
            # broker rounds each side's commission to cents
            ours_comm = -(round(commission_usd(e.volume, e.price, contract, pct), 2)
                          + round(commission_usd(x.volume, x.price, contract, pct), 2))
            broker_comm = e.commission + x.commission
            ok = abs(ours_pnl - x.profit) < CENT and abs(ours_comm - broker_comm) < CENT
            all_ok &= ok
            n += 1
            opened = datetime.fromtimestamp(e.time, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            print(f"{opened:19} {'LONG' if direction > 0 else 'SHORT':5} {e.volume:5.2f} {e.price:9.2f} {x.price:9.2f} | "
                  f"{x.profit:10.2f} {ours_pnl:7.2f} | {broker_comm:11.2f} {ours_comm:6.2f} | {'YES' if ok else 'NO'}")
        if n == 0:
            print("\nNo closed gold trades found — nothing checked.")
        else:
            print(f"\n{n} trade(s) checked: " + ("all match." if all_ok else "MISMATCH — formula needs a look."))
    finally:
        data_mt5.disconnect()


if __name__ == "__main__":
    main()
