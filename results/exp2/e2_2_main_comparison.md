# Experiment 2 — E2-2 main comparison, 2022–2025

All results in **R** (1R = the trade's initial risk; fractional size, every signal traded). Base costs unless stated: real spread from 2025-12-17, estimated hourly 75th percentile before; commission 0.0007% per side; swap from the broker's current rates (estimate). Data 2022+ only, through the data lock. S1 is judged on H1; M15 is reported for reference (spec §2).

Fixed before any result: a nudge **collapses** if its expectancy falls below half of the base expectancy or to ≤ 0 (Change Log clarification 4); C1 is compared on total R at base costs.

## Verdicts (spec §7: a strategy is "promising" only if all six checks pass)

| Strategy | Trades | Expectancy | Total R | Promising? |
|---|---:|---:|---:|---|
| S1 H1 | 877 | +0.014R | +12.4R | no |
| S1 M15 | 932 | +0.002R | +1.5R | (reference: would fail) |
| S2 | 142 | -0.014R | -2.0R | no |
| S3 | 243 | +0.013R | +3.1R | no |
| S4 | 621 | -0.010R | -6.1R | no |
| S5 | 1022 | +0.007R | +7.6R | no |

**S1 H1:** ❌ expectancy ≥ +0.10R (+0.014R); ❌ positive total R in ≥ 3 of 4 years (2/4); ✅ beats ≥ 90% of C1 on total R (99.0%); ❌ positive expectancy at 1.5× spread (-0.001R); ✅ positive expectancy at 0.0025% commission (+0.007R); ❌ no collapse under nudges (box end 07:30)

**S1 M15:** ❌ expectancy ≥ +0.10R (+0.002R); ❌ positive total R in ≥ 3 of 4 years (2/4); ✅ beats ≥ 90% of C1 on total R (96.5%); ❌ positive expectancy at 1.5× spread (-0.008R); ❌ positive expectancy at 0.0025% commission (-0.006R); ❌ no collapse under nudges (box end 06:30, box end 07:30)

**S2:** ❌ expectancy ≥ +0.10R (-0.014R); ❌ positive total R in ≥ 3 of 4 years (2/4); ❌ beats ≥ 90% of C1 on total R (75.0%); ❌ positive expectancy at 1.5× spread (-0.038R); ❌ positive expectancy at 0.0025% commission (-0.032R); ❌ no collapse under nudges (wick ratio 1.5, wick ratio 2.5)

**S3:** ❌ expectancy ≥ +0.10R (+0.013R); ❌ positive total R in ≥ 3 of 4 years (2/4); ❌ beats ≥ 90% of C1 on total R (75.5%); ✅ positive expectancy at 1.5× spread (+0.002R); ✅ positive expectancy at 0.0025% commission (+0.009R); ✅ no collapse under nudges (none)

**S4:** ❌ expectancy ≥ +0.10R (-0.010R); ❌ positive total R in ≥ 3 of 4 years (1/4); ❌ beats ≥ 90% of C1 on total R (64.0%); ❌ positive expectancy at 1.5× spread (-0.023R); ❌ positive expectancy at 0.0025% commission (-0.017R); ❌ no collapse under nudges (RSI 5 / 95, RSI 15 / 85)

**S5:** ❌ expectancy ≥ +0.10R (+0.007R); ✅ positive total R in ≥ 3 of 4 years (3/4); ✅ beats ≥ 90% of C1 on total R (97.0%); ❌ positive expectancy at 1.5× spread (-0.026R); ✅ positive expectancy at 0.0025% commission (+0.000R); ❌ no collapse under nudges (exit 02:00 NY)

## Main results, base costs

| Strategy | Trades | Win rate | Expectancy | Total R | Max drawdown | % months profitable | Worst month | C1: 5% / median / 95% total R | Beats % of C1 | FTMO-flagged exits | Held over >2 h break | Swap |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| S1 H1 | 877 | 47% | +0.014R | +12.4R | 29.9R | 52% | -10.5R | -70.7 / -37.2 / -4.8 | 99.0% | 39 | 19 | -0.5R (23 nights) |
| S1 M15 | 932 | 46% | +0.002R | +1.5R | 42.3R | 54% | -10.9R | -73.2 / -38.1 / -2.3 | 96.5% | 39 | 20 | -0.6R (24 nights) |
| S2 | 142 | 39% | -0.014R | -2.0R | 13.7R | 46% | -4.0R | -29.0 / -8.3 / +11.5 | 75.0% | 3 | 1 | -0.1R (1 nights) |
| S3 | 243 | 41% | +0.013R | +3.1R | 29.6R | 44% | -6.1R | -31.6 / -7.6 / +20.3 | 75.5% | 7 | 13 | -8.1R (629 nights) |
| S4 | 621 | 60% | -0.010R | -6.1R | 26.6R | 48% | -6.9R | -39.1 / -11.5 / +16.7 | 64.0% | 16 | 4 | -0.1R (3 nights) |
| S5 | 1022 | 48% | +0.007R | +7.6R | 30.0R | 50% | -5.6R | -71.9 / -36.4 / +2.3 | 97.0% | 0 | 1 | +0.0R (0 nights) |

## Per year, base costs (trades / total R / expectancy)

| Strategy | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| S1 H1 | 230 / +13.3R / +0.058R | 225 / -13.0R / -0.058R | 213 / +17.4R / +0.082R | 209 / -5.3R / -0.026R |
| S1 M15 | 245 / +6.2R / +0.025R | 235 / -14.4R / -0.061R | 229 / +18.4R / +0.080R | 223 / -8.7R / -0.039R |
| S2 | 34 / -3.5R / -0.104R | 41 / +0.2R / +0.005R | 38 / +4.5R / +0.117R | 29 / -3.1R / -0.107R |
| S3 | 66 / -10.4R / -0.158R | 62 / -4.1R / -0.065R | 59 / +2.9R / +0.050R | 56 / +14.7R / +0.262R |
| S4 | 150 / -3.4R / -0.022R | 164 / +11.6R / +0.071R | 157 / -11.0R / -0.070R | 150 / -3.4R / -0.022R |
| S5 | 254 / -20.1R / -0.079R | 255 / +4.9R / +0.019R | 258 / +8.2R / +0.032R | 255 / +14.6R / +0.057R |

## Cost stresses (expectancy / total R)

| Strategy | Base | 1.5× spread | 0.0025% commission |
|---|---|---|---|
| S1 H1 | +0.014R / +12.4R | -0.001R / -1.3R | +0.007R / +6.6R |
| S1 M15 | +0.002R / +1.5R | -0.008R / -7.3R | -0.006R / -5.1R |
| S2 | -0.014R / -2.0R | -0.038R / -5.4R | -0.032R / -4.6R |
| S3 | +0.013R / +3.1R | +0.002R / +0.4R | +0.009R / +2.3R |
| S4 | -0.010R / -6.1R | -0.023R / -14.0R | -0.017R / -10.8R |
| S5 | +0.007R / +7.6R | -0.026R / -26.4R | +0.000R / +0.2R |

## Robustness nudges, base costs (reported, never selected)

| Strategy | Variant | Trades | Expectancy | Total R | vs base expectancy | Collapses? |
|---|---|---:|---:|---:|---:|---|
| S1 H1 | box end 06:30 | 897 | +0.016R | +14.0R | +0.001R | no |
| S1 H1 | box end 07:30 | 837 | -0.003R | -2.5R | -0.017R | **YES** |
| S1 M15 | box end 06:30 | 947 | +0.001R | +0.5R | -0.001R | **YES** |
| S1 M15 | box end 07:30 | 910 | -0.014R | -12.9R | -0.016R | **YES** |
| S2 | wick ratio 1.5 | 168 | -0.017R | -2.9R | -0.003R | **YES** |
| S2 | wick ratio 2.5 | 132 | -0.022R | -2.9R | -0.008R | **YES** |
| S3 | channel 16 | 271 | +0.023R | +6.3R | +0.010R | no |
| S3 | channel 24 | 219 | +0.064R | +14.0R | +0.051R | no |
| S4 | RSI 5 / 95 | 347 | -0.038R | -13.1R | -0.028R | **YES** |
| S4 | RSI 15 / 85 | 846 | -0.012R | -10.3R | -0.002R | **YES** |
| S5 | exit 02:00 NY | 1022 | -0.001R | -1.5R | -0.009R | **YES** |
| S5 | exit 04:00 NY | 1022 | +0.006R | +6.1R | -0.002R | no |

## Regime table — total R per month type, base costs

Months 2022–2025 labelled from broker-day closes: efficiency = |month change| ÷ sum of |daily changes|; above the median (0.174) = trending. Months: trending up 17, ranging up 13, ranging down 11, trending down 7.

| Strategy | Trending up | Trending down | Ranging up | Ranging down | All trending | All ranging | All up | All down |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 H1 | +2.9R (17 mo) | -4.7R (7 mo) | +3.0R (13 mo) | +11.2R (11 mo) | -1.8R (24 mo) | +14.2R (24 mo) | +5.9R (30 mo) | +6.5R (18 mo) |
| S1 M15 | -0.2R (17 mo) | -12.6R (7 mo) | -1.1R (13 mo) | +15.3R (11 mo) | -12.7R (24 mo) | +14.2R (24 mo) | -1.2R (30 mo) | +2.7R (18 mo) |
| S2 | +1.9R (17 mo) | +1.1R (7 mo) | +0.8R (13 mo) | -5.9R (11 mo) | +3.1R (24 mo) | -5.1R (24 mo) | +2.7R (30 mo) | -4.7R (18 mo) |
| S3 | +31.1R (17 mo) | -12.1R (7 mo) | +1.5R (13 mo) | -17.3R (11 mo) | +19.0R (24 mo) | -15.8R (24 mo) | +32.6R (30 mo) | -29.4R (18 mo) |
| S4 | -5.5R (17 mo) | +5.6R (7 mo) | -4.0R (13 mo) | -2.2R (11 mo) | +0.1R (24 mo) | -6.2R (24 mo) | -9.5R (30 mo) | +3.4R (18 mo) |
| S5 | +40.6R (17 mo) | -18.3R (7 mo) | -4.2R (13 mo) | -10.5R (11 mo) | +22.3R (24 mo) | -14.7R (24 mo) | +36.4R (30 mo) | -28.7R (18 mo) |

## Buy-and-hold gold reference (same period)

| Year | Gold change |
|---|---:|
| 2022 | +1.3% |
| 2023 | +13.1% |
| 2024 | +27.2% |
| 2025 | +64.6% |
| **2022–2025** | **+139.8%** (first close of 2022 to last close of 2025) |

Monthly R per strategy (base) is in `e2_2_monthly_r.csv`; trades in `e2_2_trades_*.csv`; C1 totals per seed in `e2_2_c1_total_r_by_seed.csv`.
