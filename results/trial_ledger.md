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
| 14 | Exp 6 (pre-declared, spec §7; added 2026-10-08 in E6-1 before any Exp 6 result) | Main; lookback 21 / 63 / 252 only; buffer 0% / 50%; execution 12:00 New York; long-only benchmark | 8 |
| 15 | Exp 7 (pre-declared, spec v1.0 §5; added 2026-10-09 at the lock, before any Exp 7 outcome) | M1 base rules; box min bars 5 / 8; box range 1.25 / 1.75 × ATR(H1); t threshold 1.5 / 2.5; M2 meta-labeling layer | 8 |
| 16 | Exp 7 v1.1 (exit variant requested after E7-2; added 2026-10-09 before any M1-TS code or result) | M1-TS (break-even + trailing stop); break-even trigger 0.75R / 1.5R; trail 1.0 / 2.0 × ATR(M15) | 5 |
| | | **Total** | **90** |

**N for the Deflated Sharpe Ratio = max(90, 50) = 90** (Exp 4 used N = 69; Exp 6 used 77; Exp 7 E7-2 used 85). Exp 7 E7-0 counts (v0.9, v0.10) computed no outcomes and are not counted.

Not counted: C1 random-direction controls (Exp 1–4, 6), the Exp 6 cost stress, C2 random-veto control (Exp 1 Phase 5), cost stresses
(1.5× spread, higher commission, 1.5× swap), the timeframe bootstrap (re-analysis of existing trades, no new rules).
Checked 2026-10-08 (E4-1b): `src/exp2/regime.py` only labels months as a market description (no trade rules) and `src/exp3/sanity.py` re-computes the already-counted Donchian 55/20 rule — neither adds a rule set; count unchanged.

If any further configuration is run, add a row here before computing the Deflated Sharpe Ratio.
