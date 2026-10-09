# Phase E6-0 — data prep (no returns, no signals)

Account OANDA-Demo-1 (FTMO trial), USD, account leverage 1:100. 49 symbols: 42 FX, 3 indices (US100, US500, US30), 2 metals, USOIL, BTCUSD (crypto, excluded, not pulled).
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
