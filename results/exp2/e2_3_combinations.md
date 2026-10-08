# Experiment 2 — E2-3 combinations, 2022–2025 (INFORMATION ONLY)

No strategy passed the §7 "promising" test in E2-2, so no combination can be judged "better". Spec §6 then asks for the **two least-correlated strategies with positive expectancy**, information only; the **S1 + S3 + S5** run was added by Yash and recorded in the Change Log before running. One account, one position at a time, first signal wins (busy from signal to close; same-time events: exits, fills, then signals; ties S1, S3, S5). Base costs. $ = R × $50 (fractional size, every accepted signal traded). The combination engine reproduces every strategy's standalone run exactly when given that strategy alone (checked in this run).

## Correlation of monthly R (2022–2025, standalone runs)

| | S1 H1 | S2 | S3 | S4 | S5 |
|---|---:|---:|---:|---:|---:|
| **S1 H1** | — | -0.32 | -0.07 | -0.37 | -0.16 |
| **S2** | -0.32 | — | -0.01 | -0.09 | +0.07 |
| **S3** | -0.07 | -0.01 | — | +0.12 | +0.23 |
| **S4** | -0.37 | -0.09 | +0.12 | — | -0.02 |
| **S5** | -0.16 | +0.07 | +0.23 | -0.02 | — |

Positive expectancy (E2-2): S1 H1, S3, S5. Pairs by correlation: S1 H1 + S5 -0.16; S1 H1 + S3 -0.07; S3 + S5 +0.23. **Least-correlated pair: S1 H1 + S5.**

## Side by side, base costs

| | Trades | Total R | Total $ | Expectancy | % months profitable | Max drawdown | Worst month | Signals skipped (netting) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| S1 H1 | 877 | +12.4R | $+619 | +0.014R | 52% | 29.9R ($1,494) | -10.5R ($-527) | — |
| S3 | 243 | +3.1R | $+156 | +0.013R | 44% | 29.6R ($1,480) | -6.1R ($-305) | — |
| S5 | 1022 | +7.6R | $+381 | +0.007R | 50% | 30.0R ($1,500) | -5.6R ($-278) | — |
| S1 H1 + S5 (least-correlated pair) | 1709 | +17.0R | $+849 | +0.010R | 48% | 34.3R ($1,716) | -8.0R ($-401) | S1 H1: 190, S5: 0 |
| S1 H1 + S3 + S5 (all positive) | 1312 | +31.6R | $+1,582 | +0.024R | 54% | 40.7R ($2,034) | -10.6R ($-528) | S1 H1: 433, S3: 538, S5: 352 |

Inside each combination — trades and R by strategy:

- **S1 H1 + S5 (least-correlated pair):** S1 H1 687 trades, +9.4R (+0.014R/trade); S5 1022 trades, +7.6R (+0.007R/trade)
- **S1 H1 + S3 + S5 (all positive):** S1 H1 462 trades, +20.3R (+0.044R/trade); S3 176 trades, +7.5R (+0.042R/trade); S5 674 trades, +3.9R (+0.006R/trade)

## Per year, base costs (trades / total R / $)

| | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| S1 H1 | 230 / +13.3R / $+665 | 225 / -13.0R / $-651 | 213 / +17.4R / $+872 | 209 / -5.3R / $-267 |
| S3 | 66 / -10.4R / $-521 | 62 / -4.1R / $-203 | 59 / +2.9R / $+147 | 56 / +14.6R / $+732 |
| S5 | 254 / -20.1R / $-1,005 | 255 / +4.9R / $+245 | 258 / +8.2R / $+410 | 255 / +14.6R / $+732 |
| S1 H1 + S5 (least-correlated pair) | 434 / -5.3R / $-267 | 427 / +1.5R / $+73 | 418 / +15.2R / $+758 | 430 / +5.7R / $+284 |
| S1 H1 + S3 + S5 (all positive) | 334 / +1.7R / $+87 | 337 / -4.8R / $-239 | 325 / +11.0R / $+549 | 316 / +23.7R / $+1,185 |

## Regime table — total R per month type, base costs

| | Trending up | Trending down | Ranging up | Ranging down | All trending | All ranging |
|---|---:|---:|---:|---:|---:|---:|
| S1 H1 | +2.9R | -4.7R | +3.0R | +11.2R | -1.8R | +14.2R |
| S3 | +31.1R | -12.1R | +1.4R | -17.3R | +19.0R | -15.8R |
| S5 | +40.6R | -18.3R | -4.2R | -10.5R | +22.3R | -14.7R |
| S1 H1 + S5 (least-correlated pair) | +39.3R | -17.9R | -2.7R | -1.8R | +21.4R | -4.4R |
| S1 H1 + S3 + S5 (all positive) | +60.0R | -17.5R | +1.1R | -11.9R | +42.5R | -10.8R |

Months: trending up 17, ranging up 13, ranging down 11, trending down 7.
