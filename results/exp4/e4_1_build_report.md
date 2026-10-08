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

## For Yash to decide before E4-2
1. **Ranging days can never trade.** In ranging regime only D is on, so |F| = |D|/4 ≤ 0.25 < 0.30 entry threshold. Signal D therefore never opens a trade; the system is trend-only in practice. Keep as written, or change via the Change Log?
2. **Ablation "each signal alone":** with F always ÷4, one signal alone also tops out at 0.25 and never trades. Divide by 1 for the ablation runs?
3. **"Without gates"**: assumed = no regime gate *and* no shock gate. OK?
4. **+1 tick slippage stress** needs a small engine addition (not in Exp 2 engine). OK to add in E4-2?
