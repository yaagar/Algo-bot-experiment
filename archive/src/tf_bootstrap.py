"""Is M15 or H1 distinguishably better? Bootstrap CI of the monthly R difference.

Data (already produced, base costs, no kill switch in effect):
  * 2022-2025: Phase 4b run (kill switch off), results/phase4b/tagged_trades_A_*.csv
  * 2026 Jan-Sep: Phase 4 holdout run (kill switch never fired), results/phase4/trades_A_*_holdout.csv
Monthly R = sum over the month's trades of net P&L / the trade's initial risk in $.
Difference d = M15 - H1 per month (paired: same month), 57 months.
95% CI of mean(d) by (1) bootstrap over months, (2) moving-block bootstrap, 3-month blocks.

Run:  .venv/Scripts/python -m src.tf_bootstrap
"""
import numpy as np
import pandas as pd

from src.config import PROJECT_ROOT

OUT = PROJECT_ROOT / "results" / "phase5" / "timeframe_bootstrap.md"
CONTRACT = 100.0
REPS, SEED, BLOCK = 10_000, 7, 3
MONTHS = pd.period_range("2022-01", "2025-12", freq="M").append(pd.period_range("2026-01", "2026-09", freq="M"))


def monthly_r(tf):
    dev = pd.read_csv(PROJECT_ROOT / "results" / "phase4b" / f"tagged_trades_A_{tf}.csv")
    hold = pd.read_csv(PROJECT_ROOT / "results" / "phase4" / f"trades_A_{tf}_holdout.csv")
    t = pd.concat([dev, hold], ignore_index=True)
    t["net_r"] = t.net_pnl / (t.stop_distance * t.lots * CONTRACT)
    return t.groupby(pd.to_datetime(t.date).dt.to_period("M")).net_r.sum().reindex(MONTHS, fill_value=0.0), len(t)


def main():
    (m15, n15), (h1, nh1) = monthly_r("M15"), monthly_r("H1")
    d = (m15 - h1).to_numpy()
    rng = np.random.default_rng(SEED)
    n = len(d)
    iid = d[rng.integers(0, n, size=(REPS, n))].mean(axis=1)
    starts = rng.integers(0, n - BLOCK + 1, size=(REPS, int(np.ceil(n / BLOCK))))
    idx = (starts[:, :, None] + np.arange(BLOCK)).reshape(REPS, -1)[:, :n]
    block = d[idx].mean(axis=1)
    ci = lambda x: (np.percentile(x, 2.5), np.percentile(x, 97.5))
    lo, hi = ci(iid)
    blo, bhi = ci(block)
    distinguishable = (lo > 0 or hi < 0) and (blo > 0 or bhi < 0)
    better = "M15" if d.mean() > 0 else "H1"

    L = ["# Timeframe question — is M15 or H1 distinguishably better?", "",
         f"Data: 2022–2025 (Phase 4b run, kill switch off) + 2026 Jan–Sep (Phase 4 holdout; kill switch never fired), "
         f"base costs. {n} months; {n15} M15 trades, {nh1} H1 trades. Monthly R = sum of each trade's net P&L ÷ its "
         "initial risk in $. Difference = M15 − H1 for the same month.", "",
         "| | M15 | H1 | M15 − H1 |", "|---|---:|---:|---:|",
         f"| Mean monthly R | {m15.mean():+.3f} | {h1.mean():+.3f} | **{d.mean():+.3f}** |",
         f"| Total R over {n} months | {m15.sum():+.1f} | {h1.sum():+.1f} | {d.sum():+.1f} |",
         f"| Months positive | {(m15 > 0).sum()} | {(h1 > 0).sum()} | M15 ahead in {(d > 0).sum()} |", "",
         "95% confidence interval for the mean monthly difference (M15 − H1):", "",
         f"- Bootstrap over months ({REPS:,} resamples): **{lo:+.3f}R to {hi:+.3f}R**",
         f"- Moving-block bootstrap, {BLOCK}-month blocks: **{blo:+.3f}R to {bhi:+.3f}R**", "",
         ("**Answer: yes — " + better + " is distinguishably better** (both intervals exclude zero)." if distinguishable else
          f"**Answer: no — neither timeframe is distinguishably better.** Both intervals include zero; the observed "
          f"difference ({d.mean():+.3f}R per month, favouring {better}) is well within what chance alone produces.")]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L).encode("ascii", "replace").decode())


if __name__ == "__main__":
    main()
