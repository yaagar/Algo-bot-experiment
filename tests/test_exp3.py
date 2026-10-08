"""Experiment 3 build pieces: symbol detection, triple-swap day, swing-account engine, FX commission."""
import numpy as np
import pandas as pd

from src.backtest import Events
from src.exp2.engine import Costs, Engine, Order, Result, Swap
from src.exp2.market import M1
from src.exp3.markets import MARKETS, find_symbol
from src.exp3.pull_data import triple_swap_day
from src.exp3.sanity import prior_extreme

BY_NAME = {m.name: m for m in MARKETS}
NS_H = 3600 * 10**9


def test_symbol_detection_handles_suffix_and_missing_markets():
    names = ["EURUSD.sim", "US500.sim", "USOIL.sim", "XAUUSD.sim", "EURUSDm"]
    assert find_symbol(BY_NAME["S&P 500"], names) == "US500.sim"
    assert find_symbol(BY_NAME["WTI crude oil"], names) == "USOIL.sim"
    assert find_symbol(BY_NAME["EURUSD"], names) == "EURUSD.sim"
    assert find_symbol(BY_NAME["Germany 40"], names) is None          # skipped, never substituted
    assert find_symbol(BY_NAME["EURUSD"], ["EURUSD", "EURUSD.sim"]) == "EURUSD"


def test_triple_swap_day_from_mt5_field():
    assert triple_swap_day(5) == ("Friday", True)
    assert triple_swap_day(3) == ("Wednesday", True)
    assert triple_swap_day(7) == ("Wednesday", False)                 # invalid field -> provisional


def test_prior_extreme_uses_only_earlier_bars():
    x = np.array([1.0, 5.0, 2.0, 3.0, 9.0])
    out = prior_extreme(x, 2, np.max)
    assert np.isnan(out[:2]).all() and list(out[2:]) == [5.0, 5.0, 3.0]


def _engine(**kw):
    t = np.arange(0, 24 * 10) * NS_H                                   # 10 days of flat hourly prices
    m1 = M1(t, np.full(len(t), 100.0), np.full(len(t), 100.5), np.full(len(t), 99.5),
            np.full(len(t), 100.0), np.zeros(len(t)))
    return Engine(m1, Events([]), kw.pop("costs", Costs(1.0, 0.0)), Swap(0.0, 0.0), risk_usd=50.0,
                  contract=1.0, **kw)


def test_swing_engine_holds_over_weekend_and_never_forces_an_exit():
    eng = _engine(weekend_rule=False)
    res = Result()
    friday_evening = int(pd.Timestamp("2024-01-05 19:00", tz="UTC").value)   # after Friday 16:00 London
    pos = eng.open_position(Order(1, friday_evening, lambda p, s: p - 10), friday_evening, 100.0, 0.0, res)
    assert pos is not None and not pos.forced_is_friday and not res.blocked
    assert eng.walk(pos, 0, int(eng.m1.t[-1]) + 1) is None             # no stop hit, no forced exit


def test_fx_commission_per_lot_converted_to_quote_currency():
    eng = _engine(costs=Costs(1.0, 0.0, 2.50), weekend_rule=False, quote_per_usd=lambda price: price)
    res = Result()
    pos = eng.open_position(Order(1, 0, lambda p, s: p - 1.0), 0, 100.0, 0.0, res)   # risk 50 / (1 x 1) = 50 lots
    eng.close(pos, 2 * NS_H, 100.0, "exit signal", res)
    assert abs(res.trades[0]["commission_usd"] - 50 * 2.50 * 100.0 * 2) < 1e-9     # both sides, in quote units
