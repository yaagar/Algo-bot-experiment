# Lessons from Experiments 1–4

## Conclusions (all on 2022+ data; 2010–2021 untouched; Exp 5 skipped)
| Exp | What was tested | Result |
|---|---|---|
| 1 | Asian-box breakout on gold (Bot A) + Claude morning/veto filter (Bot B) | Bot A FAIL on the 2026 holdout (all cases). Bot B not better than A in any of 6 cases. Phase 4c folded into the future 2010–2021 run. |
| 2 | Five intraday gold strategies S1–S5 + combination, in R | No strategy "promising" (best: S1 H1 +0.014R/trade). Combination information-only. |
| 3 | Donchian 55/20 on daily bars, 8 markets | FAIL on every §6 test: −0.03R/trade, −5.3R total, beat 47% of C1 runs; swap ate the pre-cost edge. |
| 4 | 4 intraday signals (range breakout, momentum, H4 trend, H1 mean reversion) combined, regime + shock gates, gold + US500 | FAIL 7 of 8 dev criteria: −0.048R/trade over 2,333 trades, negative all 4 years, beat 4.6% of C1, DSR 0.00; every ablation/robustness/stress negative; mean reversion on ranging days lost most. |

Takeaway: small pre-cost edges vanish after spread, commission and swap. Random-direction control (C1) is the honest benchmark.

**Spread understated in Exp 1–4 (found 2026-10-08, Exp 6 E6-0):** gold spreads came from MT5 bar `spread` = the MINIMUM within each bar (75th pct of M1 bar minimums per London hour, and real bar minimums after 2025-12-17). 2026 tick data (ask − bid, 75th pct) is 1.8–2.5× higher (median 2.2×; e.g. $0.25 → $0.56–0.61 in London hours); other symbols 1.4–8×. Exp 1–4 costs were too LOW, so their FAIL verdicts stand (true costs only worse). Not re-run. From Exp 6 on, spreads come from tick data only.

## Rules that still apply
- **Pre-registered criteria.** Spec, numbers and pass/fail fixed before any result. Changes only through a dated Change Log entry approved by Yash, before running.
- **No optimisation.** Robustness nudges are reported, never selected.
- **No look-ahead.** Decisions use only data available at that time; the future-scramble leak test must pass.
- **Data lock.** All price data via `src/data_access.py`; pre-2022 refused without Yash's dated confirmation; every use logged in `results/data_access_log.md`.
- **Clock.** Broker server time = New York + 7 h; broker day = New York 17:00 to 17:00.
- **Costs.** Real spread (estimated hourly 75th percentile where history lacks it), commission 0.0007% per side, swap per rollover (×3 on the triple-swap day).
- **Fills.** Decide at bar close, fill next bar open; stops on bid (longs) / ask (shorts); stop wins a same-bar tie.
- **FTMO rules.** Daily-loss and max-loss limits simulated with real lots (`src/ftmo_rules.py`).
- **News calendar.** FOMC, NFP, CPI, PPI, PCE, GDP, retail sales, ISM in UTC (`src/calendar_events.py`).
- **Read-only MT5.** Never place trades; no credentials in code or git.

## Archive (`archive/`, full history in git)
- `archive/docs/EXPERIMENT_SPEC.md` — Exp 1 spec; still the source for inherited rules (data pipeline, costs, FTMO, calendar, leak test) that later specs don't restate.
- `archive/docs/EXPERIMENT_2_SPEC.md` — Exp 2 spec.
- `archive/src/` — Exp 1 runners (`run_phase3/4/4b/4c/5`, `run_2026_trend_info`, `phase4_skip_reasons`, `tf_bootstrap`), `filters.py`, Claude filter code (`claude_filter`, `claude_inputs`, `claude_isolation_test`, `headlines`, `headlines_gkg`). Not importable as-is; restore with `git mv` if needed.
- `archive/tests/test_filters.py` — tests for `filters.py`.
- Reports stay in `results/` (phase2–5, exp2, exp3).
