# Next steps

Updated 2026-10-08.

**Pending:**
1. Extend the news calendar to 2010–2021 via option (a): FRED release dates (same revision filter), ISM business-day rule, FOMC dates/times and press conferences from the Fed's historical pages, cross-checked against Forex Factory. Commit before 4c; log in the Change Log as a data fix (no rule change).
2. Run Phase 4c once (`src/run_phase4c.py`, drafted, not yet run): A and A + with-trend, plus C1, 2010–2021, three cost cases, per-year results in $ and R; judge the v1.5 decision rule.

No 2010–2021 result has been produced or looked at.

Order changed by spec v1.6: Phase 5 (Claude filter on plain Bot A) runs before 4c.

Phase 5 done 2026-10-08 (B not better than A in any of the 6 cases; report `results/phase5/phase5_report.md`).
3. Phase 6 paper forward test: design proposed in `results/phase6_design.md`; needs Yash's decisions (section 7) before building.
