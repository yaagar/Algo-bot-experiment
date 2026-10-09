# Phase E6-0 — data prep (no returns, no signals)

Account OANDA-Demo-1 (FTMO trial), USD, account leverage 1:100; symbol margin fields are 0 (no per-symbol leverage published) → 1:30 everywhere per §2. 49 symbols: 42 FX, 3 indices (US100, US500, US30), 2 metals, USOIL, BTCUSD (crypto, excluded, not pulled).
Files: `e6_0_symbols.csv/json` (contract, lots, tick, swap, margin, spread, coverage per symbol); bars in `data/processed/exp6/` (D1 + H1, 2022+).

| Group | D1/H1 from (UTC) | to | Missing weekdays (D1) | Real spread from |
|---|---|---|---|---|
| 42 FX pairs (broker) | 2025-05-19 | 2026-10-08 | 2 | 2025-05-20 |
| US100, US500, US30, XAUUSD, XAGUSD, USOIL | 2022-01-02 | 2026-10-08 | 13–16 (holidays) | 2025-12-17 (XAG 2025-01-01) |

Swap: mode 5 (annual % of price) for all; `swap_rollover3days` = 7 (invalid) on 48 symbols, 5 (Friday) on USOIL only.
Commission: not exposed by `symbol_info`. Sessions: not exposed by the MT5 Python API (H1 bars ~114 per week, all symbols).
Clock: live tick offset UTC+3 on 2026-10-09 (NY+7 holds); server follows US DST (Phase 2), so 00:00 Prague = 01:00 server except ~3 weeks/yr (02:00).
`src/ftmo_rules.py` does not match §2 (single-trade list, entry-day grouping, no concurrent positions, no swap/commission in equity) — to fix in E6-1.

Pre-2022 for E6-3 (not touched): exist — broker H1+M1 US100, US500, USOIL, XAGUSD; gold in `data/processed/XAUUSD.sim_*`; MetaQuotes H1 EURUSD, USDJPY, AUDUSD.
Missing — US30 (broker) and the 39 other FX pairs (MetaQuotes or other source).

## E6-0b (Change Log v1.1) — MetaQuotes FX, swap lock, cost screen (no returns)
- MetaQuotes-Demo offers all 42 FTMO FX pairs from 2022-01-02; 41 have full 2022–2025 coverage (largest H1 hole ≤ 73 h). Excluded: GBPNZD (159 h hole). File: `e6_0_metaquotes_fx_coverage.csv`.
- Swap: both snapshots swap_mode 5 (annual % of price), so the US500/US100 change is a rate change, not units. Long + short stays −5.00 in both (benchmark moved, 2.5% markup kept) — not explained by swap_mode → costlier per side locked: US500 −5.97 / −2.95, US100 −6.06 / +0.58. All other symbols identical or single snapshot. `e6_0_swaps_locked.csv` ($ per lot per night at latest close).
- Cost screen `e6_0_cost_screen.csv`: 15 pass — FX 11 / 41, Indices 2 / 3 (US100, US30), Commodities 2 / 3 (USOIL, XAG). Most exclusions are carry_ratio.
- **Open:** FTMO FX H1 bar spreads are 0 on 92–97% of 2026 bars (MT5 bar spread = minimum in the bar); 9 majors have no non-zero 10:00 NY spread at all → cost_ratio undefined, marked "no 2026 spread at 10:00 NY", not included. 3 of them (GBPUSD, AUDUSD, NZDUSD) pass carry. FX spread method needs Yash's decision.

## E6-0c (Change Log v1.2) — tick-data spreads (no returns)
- `e6_0_tick_spreads.json`: 75th pct of tick spread (ask − bid) per server hour, all 2026 ticks, 48 symbols (7–121 M ticks each; XAGUSD from Feb 2026, others Jan–Oct). No fallback needed.
- Cost screen re-run (`e6_0_cost_screen.csv`): 18 pass — FX 14 / 41 (adds GBPUSD, AUDUSD, NZDUSD), Indices 2 / 3, Commodities 2 / 3. Tick spreads are 1.4–8× the old bar values; no cost_ratio above 0.061 (XAG), all exclusions are carry_ratio.
- Gold, information only: tick p75 vs the Exp 1–4 table is 1.8–2.5× (median 2.2×) per London hour → old costs understated; LESSONS.md updated, nothing re-run.
