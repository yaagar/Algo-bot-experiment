# Timeframe question — is M15 or H1 distinguishably better?

Data: 2022–2025 (Phase 4b run, kill switch off) + 2026 Jan–Sep (Phase 4 holdout; kill switch never fired), base costs. 57 months; 953 M15 trades, 887 H1 trades. Monthly R = sum of each trade's net P&L ÷ its initial risk in $. Difference = M15 − H1 for the same month.

| | M15 | H1 | M15 − H1 |
|---|---:|---:|---:|
| Mean monthly R | +0.196 | +0.412 | **-0.217** |
| Total R over 57 months | +11.1 | +23.5 | -12.3 |
| Months positive | 33 | 33 | M15 ahead in 28 |

95% confidence interval for the mean monthly difference (M15 − H1):

- Bootstrap over months (10,000 resamples): **-0.822R to +0.388R**
- Moving-block bootstrap, 3-month blocks: **-0.839R to +0.319R**

**Answer: no — neither timeframe is distinguishably better.** Both intervals include zero; the observed difference (-0.217R per month, favouring H1) is well within what chance alone produces.
