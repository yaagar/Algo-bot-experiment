# Phase E4-1 — build and verify (no performance numbers)

Data: development period 2022-01-01 → 2025-12-31 only, via `src/data_access.py`. 2010–2021 not touched.
US500 M1 downloaded 2022-01-02 → 2026-10-08 (`src/exp4/pull_data.py`); spreads before 2025-12-17 = 2026 p75 per London hour (4–5 points).

| Check | Gold | US500 |
|---|---|---|
| Trading days built | 1,038 | 1,030 |
| Future-scramble test (20 cuts; every bar's scores/gates/F, signals, fills, exits before the cut) | 20 / 20 identical | 20 / 20 identical |
| Scramble changed later decisions (min per cut) | ≥ 1,817 | ≥ 1,516 |
| Independent rebuild (`src/exp4/rebuild.py`, no shared code) — bars compared | 23,615 | 24,502 |
| Rebuild max difference (scores, F) | 9e-14 | 1.2e-13 |
| Rebuild efficiency / shock ratio / window flags | exact | exact |

Files: `e4_1_leak_test.csv`, `e4_1_rebuild_check.csv`, `handcheck_5_trades_per_market.csv` (UTC + server times, four scores, F, gates, size, stop; no P&L).
Trial ledger: `results/trial_ledger.md` → 69 configurations, N = 69.

## E4-1b re-verification (Change Log v1.2, 2026-10-08)
| Check | Gold | US500 |
|---|---|---|
| Future-scramble test, 20 cuts | 20 / 20 identical | 20 / 20 identical |
| Rebuild (v1.2 forecast written separately), main config, max diff | 9e-14 | 1.2e-13 |
| Rebuild on variants only_A / only_D / no_gates | match | match |
| Slippage tick (`symbol_info` trade_tick_size) | 0.001 | 0.1 |
| Hand-check trades on ranging days (efficiency < 0.30) | 2 of 5 | 2 of 5 |

v1.1 open questions 1–4 resolved by Change Log v1.2 (a)–(d).
