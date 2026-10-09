"""Experiment 6 unit checks on synthetic inputs (no price files)."""
import numpy as np
import pandas as pd

from src.exp6.c1 import c1_forecasts
from src.exp6.engine import Account
from src.exp6.signals import apply_buffer, class_budgets
from src.ftmo_rules import PortfolioLimits


def ns(text):
    return pd.Timestamp(text, tz="UTC").value


def test_prague_reset_is_midnight_prague_in_summer_winter_and_dst_gap_weeks():
    lim = PortfolioLimits(10_000)
    # winter (CET = UTC+1): midnight = 23:00 UTC
    lim.new_time(ns("2024-01-15 22:00"), 10_000)
    lim.new_time(ns("2024-01-15 23:00"), 9_900)
    assert str(lim.day) == "2024-01-16" and lim.day_start_balance == 9_900
    # summer (CEST = UTC+2): midnight = 22:00 UTC
    lim.new_time(ns("2024-07-15 21:00"), 9_800)
    assert str(lim.day) == "2024-07-15"
    lim.new_time(ns("2024-07-15 22:00"), 9_700)
    assert str(lim.day) == "2024-07-16" and lim.day_start_balance == 9_700
    # US already on summer time, Europe not yet (2024-03-10 .. 03-31): still Prague midnight = 23:00 UTC
    lim.new_time(ns("2024-03-20 22:00"), 9_600)
    assert str(lim.day) == "2024-03-20"
    lim.new_time(ns("2024-03-20 23:00"), 9_500)
    assert str(lim.day) == "2024-03-21" and lim.day_start_balance == 9_500


def test_daily_limit_uses_start_of_day_balance_minus_5pct_of_initial():
    lim = PortfolioLimits(10_000)
    lim.new_time(ns("2024-01-15 23:00"), 10_400)          # balance above initial: floor = 10,400 - 500
    lim.check(ns("2024-01-16 01:00"), 9_950)
    assert lim.breaches == []
    lim.check(ns("2024-01-16 02:00"), 9_899)
    assert [b[1] for b in lim.breaches] == ["max daily loss 5%"]
    lim.check(ns("2024-01-16 03:00"), 8_999)               # also below the static 90% floor
    assert [b[1] for b in lim.breaches] == ["max daily loss 5%", "max loss 10%"]


def test_multi_position_equity_swap_and_commission():
    acct = Account(2, 10_000)
    acct.fill(0, 1.0, 100.0, usd_ppu=10.0, commission=3.0)    # long 1 lot, $10 per price unit
    acct.fill(1, -2.0, 50.0, usd_ppu=1.0, commission=1.0)     # short 2 lots, $1 per price unit
    assert acct.balance == 10_000 - 4.0                      # commissions leave the balance at the fill
    acct.swap[:] = [-2.0, 0.5]                               # accrued swap stays on the positions
    marks = np.array([101.0, 49.0])
    equity = acct.balance + acct.floating(marks, np.array([10.0, 1.0])) + acct.swap.sum()
    assert np.isclose(equity, 9_996 + 10.0 + 2.0 - 1.5)
    acct.fill(0, 0.5, 102.0, usd_ppu=10.0, commission=1.5)    # close half: realise P/L and half the swap
    assert np.isclose(acct.balance, 9_996 - 1.5 + 0.5 * 2.0 * 10.0 - 1.0)
    assert np.isclose(acct.swap[0], -1.0) and acct.avg[0] == 100.0


def test_flip_realises_old_side_and_opens_new_at_fill_price():
    acct = Account(1, 0.0)
    acct.fill(0, 2.0, 10.0, 1.0, 0.0)
    acct.fill(0, -1.0, 12.0, 1.0, 0.0)
    assert acct.balance == 4.0 and acct.lots[0] == -1.0 and acct.avg[0] == 12.0


def test_class_budget_split_equal_by_class_then_market():
    share = class_budgets(["FX", "FX", "Indices", "Commodities", "Commodities"], np.array([True, True, True, True, False]))
    assert np.allclose(share, [1 / 6, 1 / 6, 1 / 3, 1 / 3, 0])


def test_buffer_trades_only_bigger_changes():
    new = apply_buffer(np.array([1.0, 1.0, 0.5]), np.array([1.2, 1.3, 0.0]), np.array([1.0, 1.0, 0.0]), 0.25)
    assert np.allclose(new, [1.0, 1.3, 0.0])                  # 0.2 <= 0.25 kept; 0.3 traded; untradeable closed


def test_c1_redraws_coin_at_each_sign_change_only():
    s = pd.DataFrame({"f": [0, 1 / 3, 1, 1, -1 / 3, -1, 0, 1]})
    f = c1_forecasts([s], ["X"], seed=3)["X"]
    assert np.allclose(np.abs(f), np.abs(s.f))
    assert np.sign(f[1]) == np.sign(f[2]) == np.sign(f[3]) and np.sign(f[4]) == np.sign(f[5])
