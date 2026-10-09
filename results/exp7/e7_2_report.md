# Exp 7 — E7-2 development run (spec v1.0, run once, 2026-10-09)

XAUUSD 2019-01-01 → 2025-12-31. Trading code as in 69b0922; scoring committed in 35a9c1f before the run.
Raw: `e7_2_results.json`, `e7_2_trades.csv`. **M1 verdict: FAIL (8 of 9 criteria fail).** M2 not adopted.

| Criterion | Value | Threshold | Result |
|---|---|---|---|
| Trades | 274 | ≥ 150 | PASS |
| Expectancy | −0.016R | ≥ +0.10R | FAIL |
| Positive years | 2 of 7 | ≥ 5 | FAIL |
| Beats C1 | 94.4% | ≥ 95% | FAIL |
| Beats C2 | 73.7% | ≥ 90% | FAIL |
| Deflated Sharpe (N = 85) | 0.004 | ≥ 0.95 | FAIL |
| Expectancy at 1.5× spread | −0.060R | > 0 | FAIL |
| Worst robustness variant | −0.078R | all > 0 | FAIL |
| 2019–2024 only | −0.001R | ≥ +0.05R | FAIL |

| Year | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|
| Trades | 30 | 44 | 40 | 45 | 30 | 32 | 53 |
| Win rate | 57% | 34% | 38% | 40% | 50% | 31% | 38% |
| Expectancy R | +0.43 | −0.05 | −0.12 | −0.09 | +0.23 | −0.27 | −0.08 |
| Total R | +12.8 | −2.1 | −4.7 | −4.2 | +6.8 | −8.7 | −4.2 |

Long 172 trades +0.038R; short 102 trades −0.106R. Exits: stop 47.4%, time 34.3%, target 18.2%.
Variants: box 5 bars −0.041 (322) · 8 bars −0.078 (215) · range 1.25 −0.074 (281) · range 1.75 +0.051 (201) · t 1.5 −0.005 (279) · t 2.5 −0.026 (266).
Stress: 1.5× spread −0.060 · +1 tick −0.016 · both −0.061 (274 trades each).
M1 vs M2 2021–25: M1 200 trades, 39.0%, −0.075R, −15.0R · M2 136 trades, 39.7%, −0.109R, −14.9R · skipped 64, win rate 37.5%.
Info ($50/R, $10k): −$2.59/month, 44% months profitable, worst day −$151, worst month −$316, max drawdown $1,015 (10.2%).
