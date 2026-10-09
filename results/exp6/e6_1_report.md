# Phase E6-1 — build and verify (no performance numbers), 2022–2025 data only

Universe: the 18 screen-passing markets (FX 14, Indices 2, Commodities 2). Trial ledger: +8 Exp 6 configurations → N = 77.
Edge runs: fractional lots, notional $100k (Change Log v1.3). First tradeable day 2022-12-21 (252-day warm-up inside the period).

| Check | Result |
|---|---|
| Unit tests (all) | 88 passed (7 new: Prague reset winter/summer/US-EU DST gap, 5% daily from start balance, multi-position equity with swap + commission, flip, class split, buffer, C1) |
| Future-scramble, 20 cuts, full system (all markets + FX conversion pairs) | 20/20 identical before the cut; ≥ 2,221 later decisions changed |
| Independent rebuild (`rebuild.py`, no shared engine code), 1,041 broker days, 1,249 Prague days | f exact; targets 1.5e-14 lots; positions exact (6 dp); fills 2,645 = 2,645, prices exact; equity 1.7e-10 $; FTMO start balance / min equity 1.7e-10 $; breach days identical |
| C1 smoke (3 seeds) | runs; same magnitudes; signs re-drawn per sign change |
| All 9 configs run (main, 3 lookbacks, 2 buffers, 12:00 NY, long-only, cost stress) | yes |
| Peak margin use (1:30), main | 6.7% of equity |

Files: `e6_1_leak_test.csv`, `e6_1_rebuild_check.json`, `e6_1_handcheck_10_position_changes.csv`, `e6_1_mechanics.csv`, `e6_1_summary.json`.

Mechanics (per market, `e6_1_mechanics.csv`): 30–63 position changes / year, average holding 11–34 days; f = 0 almost never (three ±1 signs cannot average to 0).
**Min-lot skips at FTMO sizes** (share of position changes below the minimum lot): $10k 100% / 96% (5% / 8% vol); $25k 87% / 72%; $50k 59% / 37%.
