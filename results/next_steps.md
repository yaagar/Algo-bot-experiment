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
