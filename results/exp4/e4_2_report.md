# Experiment 4 — E4-2 development run, 2022-01-01 → 2025-12-31 (run once)

**Summary.** The combined-signal system loses after costs: -0.048R per trade over 2,333 trades, negative in all 4 years, and worse than 95% of random-direction runs.
Most of the loss comes from ranging days, where only the mean-reversion signal D trades (-0.058R/trade); trending days lose less (-0.027R). No single signal, robustness variant or cost case is positive.
Development verdict: **FAIL** on 7 of 8 criteria, so per spec §8–§10 there is no FTMO table and no final exam. 2026 (information only) is slightly positive and does not count.

## Verdict (spec §8 development criteria)

| Criterion | Value | Threshold | Result |
|---|---:|---|---|
| Trades (portfolio) | 2333 | >= 200 | PASS |
| Expectancy (R/trade) | -0.0485 | >= +0.10 | FAIL |
| Years with positive total R | 0 | >= 3 of 4 | FAIL |
| Worst year total R | -45.4 | >= -10 | FAIL |
| Beats % of C1 (portfolio total R) | 4.6 | >= 95% | FAIL |
| Deflated Sharpe probability | 0.0 | >= 0.95 | FAIL |
| Stress expectancy (1.5x spread, 2x comm, +1 tick) | -0.0659 | > 0 | FAIL |
| Worst robustness expectancy | -0.06 | > 0 | FAIL |
| **Overall** | | all must pass | **FAIL** |

Deflated Sharpe: daily Sharpe -0.0756 over 1039 days, skew 0.22, kurtosis 4.86; V = 9.847e-04 (cross-config 8.788e-04, sampling 9.847e-04; **sampling term won**); SR0 = 0.0752; N = 69. C1 median total R -47.5.

## Per year (main, base costs)

| Year | Trades | Total R |
|---|---:|---:|
| 2022 | 493 | -14.138 |
| 2023 | 620 | -45.399 |
| 2024 | 614 | -15.802 |
| 2025 | 606 | -37.777 |

## Per regime of the entry day (main, base costs)

| Regime | Trades | Expectancy (R) | Total R |
|---|---:|---:|---:|
| trending | 718 | -0.027 | -19.275 |
| ranging | 1615 | -0.058 | -93.840 |

## Ablation and robustness (information only, base costs)

| Configuration | Trades | Expectancy (R) | Total R |
|---|---:|---:|---:|
| main | 2333 | -0.048 | -113.115 |
| entry_0.20 | 2976 | -0.042 | -125.638 |
| entry_0.40 | 1793 | -0.060 | -107.551 |
| stop_1.0 | 2678 | -0.054 | -145.367 |
| stop_2.0 | 2116 | -0.041 | -86.718 |
| only_A | 524 | -0.031 | -16.123 |
| only_B | 733 | -0.003 | -1.854 |
| only_C | 1143 | -0.018 | -20.965 |
| only_D | 1615 | -0.058 | -93.840 |
| no_gates | 375 | -0.042 | -15.610 |
| main, cost stress | 2348 | -0.066 | -154.628 |

**2026 information only** (2026-01-01 → latest data, main config): 325 trades, expectancy +0.039R, total +12.727R.
