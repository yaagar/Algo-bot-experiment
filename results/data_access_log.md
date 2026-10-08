# Data access log — reserved period (before 2022-01-01)

The hard lock (`src/data_access.py`) was added on 2026-10-08. From then on, every read, download or data-prep step that reaches before 2022-01-01 needs a purpose plus a confirmation sentence containing that day's date, and is logged automatically in the table at the bottom.

## Before the lock (reconstructed by audit, 2026-10-08)

All of these happened in **Phase 1–2 (2026-10-07/08), before spec v1.4 reserved 2010–2021**. None produced a strategy result (no signal, trade, P&L or return was computed on pre-2022 data).

| When | What touched pre-2022 data | What was seen |
|---|---|---|
| Phase 1 | MT5 connection probe requested H1 bars from 2020-01-01 | Bar count and first-bar date only |
| Phase 2 | MT5 history-depth probes (sampled weeks 2015–2026), M1/M15 limit checks (Mar 2022) | Bar counts per sampled week; first-bar dates |
| Phase 2 | `pull_prices`: downloaded all M1/M15/H1 bars from 2010 into `data/raw/` | Row counts per year 2010–2026; first three 2010 bars (open/close) printed once |
| Phase 2 | Spread check: share of bars with spread = 0 and median spread, per year 2010–2026 | Every year before 2025 had spread 0 (no spread data) |
| Phase 2 | `process_prices`: converted every row to UTC (`data/processed/`); `spread_model`: filled estimated spreads on every row | Coverage dates; share of bars with estimated spread (95%) |
| Phase 2 | Forex Factory calendar (2007–2025) read in full, then filtered to 2022+ | Total USD high-impact event count and date range |
| Phase 2 | Fed FOMC calendar page parsed (includes 2021 meetings), then filtered to 2022+ | Count of 2021 FOMC meetings (8) |

Not touched: no backtest, control, filter tag, leak test, Claude call or bootstrap ever used pre-2022 data (see `results/period_usage.md`). Phase 4b deliberately left the first 20 trading days of 2022 untagged rather than reach into 2021 for history. Phase 4c is drafted but has never run.

## Confirmed uses since the lock

| When (local) | What | Window | Purpose | Caller | Git commit | User |
|---|---|---|---|---|---|---|
