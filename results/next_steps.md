# Next steps

Updated 2026-10-08.

**Pending:**
1. ~~Extend the calendar to 2010–2021 and run Phase 4c~~ — **replaced (2026-10-08):** Experiment 1 is finished. Its Phase 4c is folded into the single future 2010–2021 confirmation run of whatever survives Experiment 2 (`docs/EXPERIMENT_2_SPEC.md` §9). The calendar extension to 2010–2021 (option a) will be needed before that run. `src/run_phase4c.py` stays as a draft, never run.
2. **Active: Experiment 2** (`docs/EXPERIMENT_2_SPEC.md`), starting with phase E2-1.

No 2010–2021 result has been produced or looked at.

Order changed by spec v1.6: Phase 5 (Claude filter on plain Bot A) runs before 4c.

Phase 5 done 2026-10-08 (B not better than A in any of the 6 cases; report `results/phase5/phase5_report.md`).
3. Phase 6 paper forward test: design proposed in `results/phase6_design.md`; needs Yash's decisions (section 7) before building.

2026-10-08: hard lock on pre-2022 data added (`src/data_access.py`). Running 4c (and re-running `pull_prices`, `process_prices` or `spread_model`) now needs `--purpose` and `--confirm "I confirm one-time use of pre-2022 data on <today> for: <purpose>"`, given only after Yash approves. Audit and period record: `results/period_usage.md`, `results/data_access_log.md`.

## 2026-10-08 — 2010-2021 data preparation (no results)
Yash's one-time confirmation: data preparation only. Reports in `results/reserved_prep/` (calendar_check, gold_integrity, markets_integrity); every access logged in `results/data_access_log.md`. No backtest, signal or return was computed.

Decisions needed before any 2010-2021 run:
1. **Broker clock before 2021 is fixed UTC+2 (no summer time)**, not New York + 7 h (daily-break and NFP-timing checks agree, gold and all broker markets). Processed pre-2022 files still use NY+7, so they are 1 h off in US summers 2010-2020. Raw server-time files are kept; re-converting needs Yash's OK (clock rule is inherited from Exp 1).
2. Retail sales 2010-2012 (and 4 months of 2013) missing: FRED's unadjusted key series RSXFSN has no vintages that early, so the revision filter keeps nothing. Needs a substitute rule.
3. ISM "one business day later in January" holds only 2018-2021; 2010-2017 Januaries were on the plain business-day rule.
4. FOMC: 2012 statement times taken from the Fed press-conference pages (12:20/12:35) differ from FF (~12:30); presser times for unscheduled 2020-03-03/15 statements are rule-based and wrong vs FF (11:00 / 18:30). PPI keeps 6 February revision days; PCE was at 10:00 on 5 days.
5. Gaps: Nasdaq 100 has no history before 2014-09-15 anywhere (broker or MetaQuotes); FX only from MetaQuotes H1 from Aug 2010, no M1; gold misses 2021-04-20 to 2021-05-20 (30 days); silver, oil and US500 miss ~4 days from 2021-04-28.
6. MetaQuotes clock pre-2022: weekly open = server midnight with summer time every year (not fixed UTC+2); European vs US DST dates not separable without M1.
