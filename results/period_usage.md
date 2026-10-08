# Which data periods each phase used

Confirmed by audit on 2026-10-08 (code, every results file, run logs, the Claude cache and call log, and git history). Dates are London calendar dates unless marked UTC.

| Phase | What ran | Price data used | Other data used |
|---|---|---|---|
| 1 — Setup | MT5 connection check | Live quote only (plus a bar-count probe from 2020, see the access log) | — |
| 2 — Data | Download, UTC conversion, spread estimate, server-clock check, calendar, headlines, P&L check | **Download and prep touched 2010 → 2026-10-08** (no results). Server-clock check: 2022-01-01 → 2026-10. Spread table: 2026 data only | Calendar: Forex Factory filtered to 2022+; Fed/FRED/ISM 2022+. Headlines: 2026-07-01 → 10-07. Demo trades: 2026-10-08 |
| 3 — Backtester, A, C1, nudges, leak test | Development period | **2022-01-01 → 2025-12-31** (loader refused anything reaching 2026) | Calendar 2022–2025 |
| 4 — Holdout (once) | A + C1, kill switch on | **2026-01-01 → 2026-09-30** | Calendar 2026 |
| 4 diagnostic | Holdout skip reasons (re-run, read-only) | 2026-01-01 → 2026-09-30 | — |
| 4b — Filter discovery | A tagged, kill switch off | **2022-01-01 → 2025-12-31** (filter history taken from inside 2022 only); 2026 long/short split read from Phase 4 trade files | Calendar 2022–2025 |
| 4b sanity check | A + with-trend reproduces the 4b tags | 2022-01-01 → 2025-12-31 | — |
| 4c — Confirmation | **Not run** (drafted; now needs the one-time confirmation) | — (would be 2010-01-01 → 2021-12-31) | — |
| 2026 trend comparison (info only) | A vs A + with-trend | 2026-01-01 → 2026-09-30, plus 2025-11-01 → 2025-12-31 for the first 20 trend readings | Calendar 2026 |
| 5 — Claude filter | A, B, C1, C2 + Claude calls | **2026-07-01 → 2026-10-07** (H1 history from 2026-06-17 for the first 48 candles) | Headlines and calendar for the same window |
| Timeframe bootstrap | Reads existing result files | Trades 2022-01-03 → 2026-09-30 (Phase 4b + Phase 4 files) | — |

**2010–2021 has never been used for any strategy result.** From 2026-10-08 the loader refuses it without Yash's dated confirmation, and every confirmed use is logged in `results/data_access_log.md`.
