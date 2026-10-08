# Trial ledger — every strategy configuration run in this project

Built 2026-10-08 (E4-1) from git history (`git log`, commits 726f132 → 2b2c7fc) and the result folders
(`results/phase3`, `phase4`, `phase4b`, `phase5`, `exp2`, `exp3`). Used for the Deflated Sharpe Ratio
(spec §7): **N = max(count, 50)**.

Counting rule (conservative, fixed before any Experiment 4 result): every distinct set of trading rules
whose results were computed counts once, including nudges, filters, filter "tags" (subsets looked at),
single markets inside a portfolio, combinations and Exp 4's pre-declared variants. The same configuration
re-run on another period counts once. Not counted: random controls (C1, C2) and cost stresses (same rules,
different cost assumption) — listed for completeness.

| # | Exp / phase | Configurations | Count |
|---|---|---|---:|
| 1 | Exp 1 Phase 3 | Bot A (Asian-box breakout), M15 and H1 entries | 2 |
| 2 | Exp 1 Phase 3 | Robustness nudges: box end 06:30 / 07:30, target 1.3R / 1.7R, × M15, H1 | 8 |
| 3 | Exp 1 Phase 3/4 | Bot A with the kill switch disabled (information runs), M15 and H1 | 2 |
| 4 | Exp 1 Phase 4 | Holdout run of Bot A M15/H1 (same configurations as row 1) | 0 |
| 5 | Exp 1 Phase 4b | Filter tags looked at: long only, short only, narrow box, wide box, with trend, against trend, FOMC/CPI/NFP days, other days, × M15, H1 | 16 |
| 6 | Exp 1 2026 info | A + with-trend filter (same as the row 5 with-trend tag) | 0 |
| 7 | Exp 1 Phase 5 | Bot B = Bot A + Claude morning/veto filter, M15 and H1 | 2 |
| 8 | Exp 2 E2-2 | S1 H1, S1 M15, S2, S3, S4, S5 | 6 |
| 9 | Exp 2 E2-2 | Nudges: S1 H1/M15 box end 06:30 / 07:30; S2 wick 1.5 / 2.5; S3 channel 16 / 24; S4 RSI 5/95, 15/85; S5 exit 02:00 / 04:00 NY | 12 |
| 10 | Exp 2 E2-3 | Combinations: S1 H1 + S5; S1 H1 + S3 + S5 | 2 |
| 11 | Exp 3 E3-2 | Donchian 55/20 daily on 8 single markets (gold, silver, WTI, S&P 500, Nasdaq 100, EURUSD, USDJPY, AUDUSD) | 8 |
| 12 | Exp 3 E3-2 | The 8-market portfolio | 1 |
| 13 | Exp 4 (pre-declared, spec §7) | Main; entry 0.20 / 0.40; stop 1.0 / 2.0 × ATR; A only, B only, C only, D only; no gates | 10 |
| | | **Total** | **69** |

**N for the Deflated Sharpe Ratio = max(69, 50) = 69.**

Not counted: C1 random-direction controls (Exp 1–3), C2 random-veto control (Exp 1 Phase 5), cost stresses
(1.5× spread, higher commission, 1.5× swap), the timeframe bootstrap (re-analysis of existing trades, no new rules).
If any further configuration is run, add a row here before computing the Deflated Sharpe Ratio.
