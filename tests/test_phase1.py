import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config import PROJECT_ROOT, commission_per_lot, load_settings
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


def test_commission_placeholder_refuses_to_guess():
    s = load_settings()
    s["costs"]["commission_per_lot_round_turn_usd"] = None
    with pytest.raises(ValueError):
        commission_per_lot(s)


# --- safety: this project never trades ---------------------------------------

TRADING_CALLS = re.compile(r"\b(order_send|order_check|order_calc_margin)\b")


def test_no_trading_functions_in_source():
    offenders = [p.name for p in (PROJECT_ROOT / "src").rglob("*.py")
                 if TRADING_CALLS.search(re.sub(r'""".*?"""', "", p.read_text(encoding="utf-8"), flags=re.S))]
    assert offenders == [], f"Trading calls found in: {offenders}"
