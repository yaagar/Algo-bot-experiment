# Exp 7 — E7-2-TS: exit variant M1-TS (spec v1.1 §6, run once, 2026-10-09)

XAUUSD 2019-01-01 → 2025-12-31. Code and scoring committed in 8be3dfa before the run; N = 90.
Raw: `e7_2_ts_results.json`, `e7_2_ts_trades.csv`. **Verdict: FAIL (8 of 9 criteria).** No exam run.

| Criterion | Value | Threshold | Result |
|---|---|---|---|
| Trades | 268 | ≥ 150 | PASS |
| Expectancy | −0.039R | ≥ +0.10R | FAIL |
| Positive years | 2 of 7 | ≥ 5 | FAIL |
| Beats C1 | 82.4% | ≥ 95% | FAIL |
| Beats C2 | 68.0% | ≥ 90% | FAIL |
| Deflated Sharpe | 0.001 | ≥ 0.95 | FAIL |
| Expectancy at 1.5× spread | −0.067R | > 0 | FAIL |
| Worst variant | −0.080R | all > 0 | FAIL |
| 2019–2024 only | −0.014R | ≥ +0.05R | FAIL |

| Year | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|
| Trades | 28 | 44 | 39 | 43 | 28 | 32 | 54 |
| Win rate | 57% | 39% | 38% | 49% | 50% | 34% | 43% |
| Expectancy R | +0.39 | +0.02 | −0.16 | −0.02 | −0.02 | −0.22 | −0.14 |
| Total R | +10.9 | +0.9 | −6.2 | −1.0 | −0.5 | −7.1 | −7.4 |

Exits: initial stop 43.3%, time 30.6%, trailing stop 24.6%, break-even 1.5%. Average win +0.99R, average loss −0.84R.
Variants: BE 0.75R −0.045 (272) · BE 1.5R −0.080 (264) · trail 1.0 ATR −0.027 (270) · trail 2.0 ATR −0.080 (267).
Stress: 1.5× spread −0.067 · +1 tick −0.039 · both −0.068.
vs M1 (E7-2): M1 274 trades, 40.1%, −0.016R, −4.4R · M1-TS 268 trades, 43.7%, −0.039R, −10.4R.
Info ($50/R, $10k): −$6.16/month, 43% months profitable, max drawdown $1,311 (13.1%).
