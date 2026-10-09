"""Experiment 4 unit checks on synthetic inputs (no price files needed)."""
from types import SimpleNamespace

import numpy as np
import pandas as pd

from src.exp4.data import Clock, h1_from_m1, load_config, variant_config
from src.exp4.signals import efficiency_by_day
from src.exp4.system import E4Strategy

NS_H = 3600 * 10**9


def utc_ns(text):
    return pd.Timestamp(text, tz="UTC").value


def test_config_matches_locked_spec_numbers():
    cfg = load_config()
    t, g, s = cfg["trading"], cfg["gates"], cfg["signals"]
    assert (t["entry_threshold"], t["exit_threshold"], t["full_size_forecast"], t["stop_atr"]) == (0.30, 0.10, 0.60, 1.5)
    assert (t["max_entries_per_day"], t["news_blackout_min"]) == (3, 5)
    assert (g["efficiency_days"], g["efficiency_trend"], g["shock_mult"], g["shock_days"]) == (10, 0.30, 3.0, 60)
    assert (s["sigma_days"], s["sigma_mult"], s["c_sma"], s["c_atr"], s["d_sma"], s["d_atr"]) == (60, 2.0, 20, 20, 20, 14)
    v = variant_config(cfg, "stop_2.0")
    assert v["trading"]["stop_atr"] == 2.0 and v["trading"]["entry_threshold"] == 0.30 and cfg["trading"]["stop_atr"] == 1.5


def test_us500_day_starts_18_00_new_york_the_evening_before():
    clk = Clock("America/New_York", 18 * 60)
    # Monday 2024-03-04: 18:00 NY Sunday = 23:00 UTC Sunday (winter)
    assert clk.at(pd.Timestamp("2024-03-04"), "18:00") == utc_ns("2024-03-03 23:00")
    assert clk.at(pd.Timestamp("2024-03-04"), "09:30") == utc_ns("2024-03-04 14:30")
    day, minute = clk.day_and_minute(np.array([utc_ns("2024-03-03 23:30"), utc_ns("2024-03-04 14:30")]))
    assert list(day) == [pd.Timestamp("2024-03-04")] * 2
    assert list(minute) == [30, 930]                     # 18:30 and 09:30 NY, minutes since 18:00


def test_gold_day_is_the_london_date_and_weekends_have_no_day():
    clk = Clock("Europe/London", 0)
    day, minute = clk.day_and_minute(np.array([utc_ns("2024-07-01 00:00"), utc_ns("2024-07-01 06:00"),
                                               utc_ns("2024-06-30 23:00")]))
    # 00:00 UTC = 01:00 London Monday (summer time)
    assert day[0] == pd.Timestamp("2024-07-01") and minute[0] == 60
    assert day[1] == pd.Timestamp("2024-07-01") and minute[1] == 7 * 60     # the 06:00-07:00 London bar
    assert minute[2] == 1440 and pd.isna(day[2])        # closes at midnight -> Sunday's last minute, no day


def test_us500_h1_bars_start_at_half_past():
    t = pd.date_range("2024-03-04 14:00", periods=120, freq="1min", tz="UTC")     # 09:00-10:59 NY
    m1 = pd.DataFrame({"time_utc": t, "open": 1.0, "high": np.arange(120.0), "low": 0.0,
                       "close": np.arange(120.0), "spread_used": 5})
    bars = h1_from_m1(m1, 0.1, offset_min=30)
    assert list(pd.to_datetime(bars.t_open, utc=True).dt.strftime("%H:%M")) == ["13:30", "14:30", "15:30"]
    assert bars.close.tolist() == [29.0, 89.0, 119.0] and bars.high.tolist() == [29.0, 89.0, 119.0]


def test_efficiency_uses_completed_days_only():
    closes = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 99.0])
    eff = efficiency_by_day(closes, 10)
    assert np.isnan(eff[10]) and eff[11] == 1.0          # day 11 sees days 0..10 only, not its own 99


def test_exit_on_sign_flip_or_weak_forecast():
    table = pd.DataFrame({"F": [0.5, 0.2, 0.09, -0.3], "t_close": [1, 2, 3, 4], "day_idx": 0,
                          "in_window": True, "shock_ok": True, "atr14": 1.0, "trending": True, "ranging": False,
                          **{f"score_{s}": 0.0 for s in "ABCD"}, "efficiency": 0.5, "shock_ratio": 1.0})
    mk = SimpleNamespace(h1=table, days=[pd.Timestamp("2024-03-04")], cfg={"flat_by": "20:00"},
                         clock=Clock("Europe/London", 0))
    strat = E4Strategy(mk, table, load_config(), SimpleNamespace(within=lambda t, m: False))
    long_pos = SimpleNamespace(order=SimpleNamespace(direction=1))
    assert [strat.exit_signal(i, long_pos) for i in range(4)] == [False, False, True, True]
    assert strat.signal(0).direction == 1 and strat.signal(0).info["size"] == 0.5 / 0.6
    assert strat.signal(1) is None                      # |F| < 0.30: no entry


# --- Change Log v1.2 ---------------------------------------------------------------------------

from src.exp2.engine import Costs, Order, Result
from src.exp2.market import M1
from src.exp4.signals import forecast
from src.exp4.system import NO_SWAP, E4Engine


def score_rows():
    """Row 0 trending, row 1 ranging, row 2 unknown regime (efficiency NaN)."""
    return pd.DataFrame({"score_A": [0.6, 0.6, 0.6], "score_B": [0.3, 0.3, 0.3], "score_C": [0.0, 0.0, 0.0],
                         "score_D": [0.8, 0.8, 0.8], "trending": [True, False, False], "ranging": [False, True, False]})


def test_forecast_main_averages_allowed_signals_per_regime():
    F = forecast(score_rows(), {"A", "B", "C", "D"}, gated=True)
    assert np.allclose(F, [(0.6 + 0.3 + 0.0) / 3, 0.8, 0.0])        # C inactive still counts as 0


def test_forecast_single_signal_ablation_divides_by_one_with_gates():
    assert np.allclose(forecast(score_rows(), {"A"}, gated=True), [0.6, 0.0, 0.0])
    assert np.allclose(forecast(score_rows(), {"D"}, gated=True), [0.0, 0.8, 0.0])


def test_forecast_no_gates_is_all_four_over_four():
    assert np.allclose(forecast(score_rows(), {"A", "B", "C", "D"}, gated=False), [(0.6 + 0.3 + 0.8) / 4] * 3)


def tiny_engine(slippage):
    t = np.array([0, 60, 120], dtype=np.int64) * 10**9
    m1 = M1(t, np.full(3, 100.0), np.full(3, 100.5), np.full(3, 99.5), np.full(3, 100.0), np.full(3, 0.2))
    return E4Engine(m1, SimpleNamespace(within=lambda t, m: False), Costs(1.0, 0.0), NO_SWAP,
                    risk_usd=50.0, contract=1.0, blackout_min=5, weekend_rule=False, slippage=slippage)


def fills(direction, slippage, reason):
    eng, res = tiny_engine(slippage), Result()
    order = Order(direction, 0, lambda price, spread: price - direction * 2.0, time_exit_ns=10**12, info={"size": 1.0})
    pos = eng.open_position(order, 0, 100.0, 0.2, res)
    eng.close(pos, 60 * 10**9, 101.0, reason, res)
    tr = res.trades[-1]
    return tr["entry_price"], tr["stop"], tr["exit_price"]


def test_slippage_moves_every_fill_one_tick_against_the_trader():
    tick = 0.1
    for direction in (1, -1):
        for reason in ("stop", "exit signal", "time"):
            base, slipped = fills(direction, 0.0, reason), fills(direction, tick, reason)
            assert np.isclose(slipped[0] - base[0], direction * tick)      # entry: buy higher / sell lower
            assert np.isclose(slipped[1] - base[1], direction * tick)      # stop measured from the actual fill
            assert np.isclose(slipped[2] - base[2], -direction * tick)     # exit: sell lower / buy higher


def test_stop_exit_from_m1_walk_is_slipped_too():
    eng, res = tiny_engine(0.1), Result()
    order = Order(1, 0, lambda price, spread: 99.6, time_exit_ns=10**12, info={"size": 1.0})
    pos = eng.open_position(order, 0, 100.0, 0.2, res)
    eng.close(pos, *eng.walk(pos, 0, 180 * 10**9), res)
    assert res.trades[-1]["exit_reason"] == "stop" and np.isclose(res.trades[-1]["exit_price"], 99.6 - 0.1)


def test_deflated_sharpe_sanity():
    from src.exp4.evaluate import deflated_sharpe, sharpe
    rng = np.random.default_rng(1)
    noise = rng.normal(0, 1, 1000)
    strong = noise + 0.5
    weak = deflated_sharpe(noise, [0.0, 0.01, -0.01], 69)
    good = deflated_sharpe(strong, [0.0, 0.01, -0.01], 69)
    assert weak["dsr"] < 0.5 < 0.95 < good["dsr"]
    assert good["V"] == max(good["V_cross"], good["V_sampling"]) and np.isclose(good["sharpe_daily"], sharpe(strong))
