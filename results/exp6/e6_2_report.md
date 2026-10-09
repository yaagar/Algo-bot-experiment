# Experiment 6 — E6-2 gate run, 2022-01-01 → 2025-12-31 (run once, code 7332070)

**Summary.** The diversified trend portfolio loses after costs on 2022–2025: net Sharpe −0.25 (−5.6% of capital) at 10% target vol, and it beats only 55% of random-direction runs.
Before costs it made +4.7%, but spread, commission and above all swap (8.0% of capital) took 219% of that; FX lost most, indices were the only positive class.
Gate: **FAIL** on 4 of 5 criteria, so per spec §8 Experiment 6 fails and the 2010–2021 exam is not used. 2026 information run had no positions (warm-up longer than 2026 so far).

## Gate (spec §8)

| Criterion | Value | Threshold | Result |
|---|---:|---|---|
| Markets passing the cost screen | 18 | >= 8 | PASS |
| Net Sharpe, base costs | -0.248 | > 0 | FAIL |
| Net Sharpe, cost stress | -0.493 | > 0 | FAIL |
| Beats % of C1 (net total return, 1,000 seeds) | 54.9 | >= 80% | FAIL |
| Costs / gross profit (when gross > 0) | 219.5 | < 50% | FAIL |
| **Overall** | | all must pass | **FAIL** |

Deflated Sharpe (information in the gate): 0.002; daily Sharpe -0.0156 over 789 days; V = 1.249e-03 (sampling term won; cross-config 8.780e-04, sampling 1.249e-03); N = 77. C1 median net return -7.86%.

## Per year (main, base costs)

| Year | Net return % | Net Sharpe |
|---|---:|---:|
| 2023 | -7.44 | -1.32 |
| 2024 | -6.45 | -0.84 |
| 2025 | +7.97 | +0.91 |

## Per class (main, whole gate period, % of capital)

| Class | Net contribution | Spread + commission | Swap (− = paid) |
|---|---:|---:|---:|
| Commodities | -2.36% | -1.35% | -2.09% |
| FX | -7.12% | -0.76% | -1.88% |
| Indices | +3.89% | -0.14% | -4.05% |

## Robustness, benchmark, cost stress (information; the stress is a gate row)

| Configuration | Net Sharpe | Net return % | Max drawdown % |
|---|---:|---:|---:|
| main | -0.25 | -5.59 | 19.33 |
| lookback_21 | -0.30 | -8.11 | 15.11 |
| lookback_63 | -0.73 | -20.57 | 40.43 |
| lookback_252 | +0.15 | +4.00 | 14.58 |
| buffer_0 | -0.26 | -5.79 | 18.84 |
| buffer_50 | -0.17 | -3.71 | 18.81 |
| exec_12ny | -0.17 | -3.94 | 18.36 |
| long_only | +0.90 | +26.58 | 13.95 |
| cost_stress | -0.49 | -11.11 | 23.40 |

## Costs as % of gross profit (main)

Gross profit +4.68% of capital: spread 41.7%, commission 6.2%, net swap 171.5%.

**2026 information only:** 201 broker days loaded, 0 with any tradeable market (the 252-day warm-up must sit inside 2026).
