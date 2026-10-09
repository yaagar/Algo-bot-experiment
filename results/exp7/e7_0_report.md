# Exp 7 — Phase E7-0 pattern count (spec v0.9 DRAFT)

XAUUSD.sim, 2022-01-01 → 2025-12-31 (dev only), M15 built from M1, broker H1. Run 2026-10-09: `python -m src.exp7.run e7_0`.
**No outcomes computed** (no exits, P&L, R, win rates). Raw counts: `e7_0_counts.json`; per-candidate flags: `e7_0_candidates.csv`.

## Qualifying setups
| Total | 2022 | 2023 | 2024 | 2025 | Long | Short | Per month med / min / max | Months with 0 | Days with ≥1 |
|---|---|---|---|---|---|---|---|---|---|
| 144 | 20 | 12 | 24 | 88 | 114 | 30 | 2 / 0 / 17 | 14 of 48 | 84 (max 7 in a day) |

## Blocks (13,364 candidate breakouts)
| Rule | First block (in this order) | Fails rule at all |
|---|---|---|
| no trend (swing structure) | 12,201 | 12,201 |
| weak t-stat | 236 | 7,354 |
| no box | 301 | 4,167 |
| false breaks | 57 | 834 * |
| choppiness > 61.8 | 16 | 292 |
| box too tall | 152 | 3,713 * |
| cost guard | 189 | 6,096 * |
| news ±5 min | 1 | 77 |
| hours | 67 | 4,596 |

\* of the 9,197 candidates that had a box. Cost guard fails 87% / 90% / 70% / 24% of boxed candidates in 2022 / 23 / 24 / 25.

## Stops and targets
| Stop $ median | p25 | p75 | Spread/stop median | Stop = box midpoint | Target 2R: no zone | 2R: zone < 1R | Zone target |
|---|---|---|---|---|---|---|---|
| 8.98 | 7.05 | 12.37 | 6.5% | 90% | 75.7% | 24.3% | 0% |

## How ambiguous §3 points were coded
1. Swing: high above the 2 bars before, ≥ the 2 after (ties → earlier bar); known 2 H1 bars later. "Rising" = strictly rising, both highs and lows.
2. Trend, t-stat, ATR(14, H1): last H1 bar closed by the breakout bar's close. ATR = Wilder.
3. Box = longest run of M15 bars ending on the bar just before the breakout bar (≥ 6 bars); runs are not cut at daily/weekend gaps.
4. Candidate = close beyond the box edge; with no box, beyond the previous 6 bars' high/low (so "no box" can be counted).
5. False break = box bar (after the first 6) closing outside the edge of the earlier box bars, with a later box bar closing back inside. "Prior box" not read as a separate earlier box.
6. Hours and news are checked on the fill time; 20:00 London excluded.
7. Stop floor uses ATR(14, M15) at the breakout bar; "within $0.50" inclusive; moved to level − $0.50 (long) / + $0.50 (short).
8. Target zone = an earlier maximal box that ended before the current box began; "5 trading days" = 5 London weekdays incl. today; the round-level pull-in is applied before the < 1R test.
9. Spreads: the inherited 2026 tick-p75 $ table is applied to all years, when gold was cheaper and calmer; this is why the cost guard blocks most 2022–24 setups.
10. "One position at a time" needs exits, so it is not applied: counts are setups, not trades.
