# Experiment 3 — multi-market daily Donchian 55/20 — results

## Summary

One rule (Turtle System 2 on daily bars) run on 8 markets, 2022-01 to 2026-09, every trade risking the same 1R. The portfolio made **166 trades, -0.03R per trade, -5.29R in total**, with a worst drawdown of 36.2R. Before commission and swap (after spread) it made +12.62R; commission cost 0.3R and swap a net 17.6R. It beat 47% of 200 random-direction runs. **Verdict (§6): FAIL** — edge fails, diversification does not work, tradeable for Yash: no.

FX before 2025-05-21 uses MetaQuotes-Demo prices with FTMO costs (Change Log v1.1). Swap is today's rate applied to all history (estimate); spreads before real recording are the open-hour 75th percentile (estimate).

## §6 verdict

| Test | Result | Pass |
|---|---|---|
| Expectancy >= +0.10R | -0.03R | **no** |
| Positive R in >= 3 of 2022-2025 | 0 of 4 (2022: -4.85, 2023: -14.16, 2024: -4.45, 2025: -3.77) | **no** |
| Beats >= 90% of C1 | 47.0% (C1 median -4.4R) | **no** |
| Positive under each stress | 1.5x spread: -5.53R, 2x commission: -5.57R, 1.5x swap charges: -17.11R | **no** |
| Diversification: portfolio max DD < average single-market max DD | 36.2R vs 8.8R | **no** |
| Tradeable at 0.25% risk | avg >= $100/month: fails; >= 4 of every 6 months profitable: fails; no FTMO breach: ok; margin never exceeded: ok | **no** |
| Tradeable at 0.50% risk | avg >= $100/month: fails; >= 4 of every 6 months profitable: fails; no FTMO breach: fails; margin never exceeded: ok | **no** |

## Portfolio vs single markets (R, base costs)

| Market | Trades | R/trade | Total R | % months + | Max DD (R) | Worst month (R) | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Gold | 17 | +0.85 | +14.42 | 11% | 6.5 | -1.68 | -0.46 | -4.90 | +2.60 | +5.82 | +11.36 |
| Silver | 19 | +0.62 | +11.73 | 7% | 9.1 | -2.07 | +0.19 | -4.37 | +0.17 | -2.90 | +18.63 |
| WTI crude oil | 18 | -0.25 | -4.45 | 5% | 9.6 | -2.85 | -2.50 | -1.15 | -2.11 | -3.81 | +5.12 |
| S&P 500 | 18 | -0.07 | -1.26 | 11% | 4.7 | -1.30 | -2.81 | -0.23 | +4.33 | +1.03 | -3.58 |
| Nasdaq 100 | 19 | +0.03 | +0.63 | 11% | 3.9 | -1.07 | -0.74 | +1.28 | +1.47 | -0.16 | -1.21 |
| EURUSD | 25 | -0.45 | -11.17 | 7% | 11.3 | -1.26 | -2.29 | -1.84 | -5.46 | +1.97 | -3.56 |
| USDJPY | 23 | +0.08 | +1.91 | 16% | 8.2 | -1.29 | +7.55 | +0.88 | +1.66 | -4.09 | -4.10 |
| AUDUSD | 27 | -0.63 | -17.09 | 7% | 17.1 | -2.02 | -3.79 | -3.83 | -7.12 | -1.64 | -0.72 |
| **Portfolio** | 166 | -0.03 | -5.29 | 28% | 36.2 | -5.59 | -4.85 | -14.16 | -4.45 | -3.77 | +21.94 |

Average single-market max drawdown 8.8R. Monthly R correlation between markets: mean -0.01, range -0.39 to +0.51 (pairs counted twice). 2026 = Jan-Sep.

## FTMO Swing tradeability ($10k, real lots from `symbol_info`)

| Risk per trade | Signals skipped (min lot) | Avg $/month | % months profitable | Min profitable in any 6 months | Worst month | Max DD $ | Worst day $ | FTMO breach | Max margin / equity (1:30) |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| $25 (0.25%) | 75 / 166 (45%) | $-9 | 21% | 0 / 6 | $-80 | $619 | $54 | none | 0.02 |
| $50 (0.50%) | 56 / 166 (34%) | $-25 | 23% | 0 / 6 | $-186 | $1588 | $163 | total 10% on 2025-11-07 | 0.05 |

Daily loss is conservative: every open position is marked at its day's worst price (spec §5.5). Skipped signals are dropped without re-running later signals the engine skipped while that trade was open.

## Monthly R correlation

| | Gold | Silver | WTI crude oil | S&P 500 | Nasdaq 100 | EURUSD | USDJPY | AUDUSD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Gold | +1.00 | +0.04 | -0.08 | -0.17 | -0.03 | +0.09 | -0.04 | +0.44 |
| Silver | +0.04 | +1.00 | -0.04 | -0.20 | -0.13 | -0.17 | +0.02 | +0.02 |
| WTI crude oil | -0.08 | -0.04 | +1.00 | +0.04 | +0.05 | +0.04 | +0.00 | +0.06 |
| S&P 500 | -0.17 | -0.20 | +0.04 | +1.00 | +0.51 | +0.05 | +0.00 | -0.17 |
| Nasdaq 100 | -0.03 | -0.13 | +0.05 | +0.51 | +1.00 | -0.03 | +0.03 | -0.14 |
| EURUSD | +0.09 | -0.17 | +0.04 | +0.05 | -0.03 | +1.00 | -0.12 | +0.14 |
| USDJPY | -0.04 | +0.02 | +0.00 | +0.00 | +0.03 | -0.12 | +1.00 | -0.39 |
| AUDUSD | +0.44 | +0.02 | +0.06 | -0.17 | -0.14 | +0.14 | -0.39 | +1.00 |

## Checks on the final data

| Symbol | Independent check (trades identical) | Scramble test (cuts identical) | Decisions changed after cut (median) |
|---|---|---|---:|
| XAUUSD.sim | 17 / 17 pass | 20 / 20 | 78 |
| XAGUSD.sim | 19 / 19 pass | 20 / 20 | 36 |
| USOIL.sim | 18 / 18 pass | 20 / 20 | 85 |
| US500.sim | 18 / 18 pass | 20 / 20 | 115 |
| US100.sim | 19 / 19 pass | 20 / 20 | 114 |
| EURUSD.sim | 25 / 25 pass | 20 / 20 | 94 |
| USDJPY.sim | 23 / 23 pass | 20 / 20 | 79 |
| AUDUSD.sim | 27 / 27 pass | 20 / 20 | 70 |

## Notes

- Stress '1.5x swap' multiplies swap charges only; swap credits are unchanged (a stress should not help).
- '>= 4 of every 6 months' = every rolling 6-month window (as in Experiment 1).
- Months and years are counted by trade exit (UTC). FTMO days = broker days (New York 17:00), not Prague midnight (1 hour apart).
- Swap counts 5 rollovers per week (none on Saturday/Sunday broker days; the triple day covers the weekend). The reused Experiment 2 engine also charged weekend days; fixed in E3-2 (Experiment 2 never held over a weekend, its results are unchanged).
- Trades: `trades.csv`. C1 totals by seed: `c1_total_r_by_seed.csv`.
