import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config import PROJECT_ROOT, commission_usd, load_settings
from src.data_mt5 import pick_gold_symbol


def sym(name, base, profit):
    return SimpleNamespace(name=name, currency_base=base, currency_profit=profit)


# --- gold symbol detection ---------------------------------------------------

def test_picks_xauusd_by_currency_even_with_suffix():
    symbols = [sym("EURUSD", "EUR", "USD"), sym("XAUUSD.sim", "XAU", "USD"), sym("XAUEUR", "XAU", "EUR")]
    assert pick_gold_symbol(symbols)[0] == "XAUUSD.sim"


def test_prefers_plain_xauusd_when_several_match():
    symbols = [sym("XAUUSD.pro", "XAU", "USD"), sym("XAUUSD", "XAU", "USD")]
    assert pick_gold_symbol(symbols)[0] == "XAUUSD"


def test_falls_back_to_name_when_currencies_missing():
    symbols = [sym("GOLD", "", ""), sym("SILVER", "", "")]
    assert pick_gold_symbol(symbols)[0] == "GOLD"


def test_no_gold_raises():
    with pytest.raises(LookupError):
        pick_gold_symbol([sym("EURUSD", "EUR", "USD")])


# --- config -------------------------------------------------------------------

def test_settings_match_locked_spec_numbers():
    s = load_settings()
    assert s["account"]["initial_balance"] == 10000
    assert s["risk"]["risk_per_trade_usd"] == 50
    assert s["risk"]["daily_stop_usd"] == 150
    assert s["risk"]["kill_switch_drawdown_usd"] == 600
    assert s["strategy_asian"]["take_profit_r"] == 1.5


def test_commission_matches_real_ftmo_trial_fills():
    # Two real gold fills on Yash's FTMO trial account (2026-10-07), broker rounds to cents.
    pct = load_settings()["costs"]["commission_pct_per_side"]
    assert round(commission_usd(0.10, 4106.91, 100, pct), 2) == 0.29
    assert round(commission_usd(0.01, 4111.48, 100, pct), 2) == 0.03


def test_commission_cost_cases_from_spec_v1_1():
    costs = load_settings()["costs"]
    assert costs["commission_pct_per_side"] == 0.0007
    assert costs["commission_pct_per_side_stress"] == 0.0025
    assert costs["spread_stress_multiplier"] == 1.5


# --- safety: this project never trades ---------------------------------------

TRADING_CALLS = re.compile(r"\b(order_send|order_check|order_calc_margin)\b")


def test_no_trading_functions_in_source():
    offenders = [p.name for p in (PROJECT_ROOT / "src").rglob("*.py")
                 if TRADING_CALLS.search(re.sub(r'""".*?"""', "", p.read_text(encoding="utf-8"), flags=re.S))]
    assert offenders == [], f"Trading calls found in: {offenders}"
