# Gold Bot Experiment 2 — Strategy Comparison — Spec v1.0 (LOCKED)

Owner: Yash. Built by: Claude Code. Written: 2026-10-08.

**Locked means:** the rules, numbers, periods and pass criteria below must not change after any Experiment 2 result has been seen. If something is wrong or impossible, STOP and ask Yash. Record approved changes in the Change Log with date and reason.

Everything not stated here (data pipeline, clock conversion, cost model, FTMO rule simulation, news calendar, leak tests, data lock) is inherited unchanged from `docs/EXPERIMENT_SPEC.md` (Experiment 1).

---

## 1. The question

Which simple, rule-based gold strategy — or simple combination of them — gives the most **consistent** results (steady months, small drawdowns) with a real edge after costs?

Experiment 1 result (context): the Asian breakout was roughly break-even over 2022–2025, beat random entries only slightly, and failed the $100/month target. Adding Claude as a filter did not help.

## 2. Strategies (rules fixed from standard textbook versions — no tuning)

One family each. Each runs on one fixed timeframe.

| # | Name | Family | Timeframe |
|---|---|---|---|
| S1 | Asian breakout (benchmark) | Session breakout | H1 (M15 also reported, not used in the combination) |
| S2 | Box rule (wick rejection at yesterday's high/low) | Reversal at key levels | H1 |
| S3 | Donchian breakout (Turtle-style) | Trend-following, multi-day | H4 |
| S4 | RSI(2) pullback (Connors) | Buy dips inside a trend | H1 |
| S5 | Time-of-day (Asian-hours long) | Seasonality | H1 bars, fixed clock times |

### S1 — Asian breakout
Exactly Experiment 1 spec §5 (box 00:00–07:00 London, first close outside the box 07:00–16:00 London, stop at opposite box edge, target 1.5R, time exit 20:00 London). Re-run under this spec's common settings (§3) so all strategies are compared the same way.

### S2 — Box rule (H1)
- **Levels:** previous broker trading day's high (PDH) and low (PDL). The broker day already aligns with the New York close.
- **Entry window:** signal candles that close between 07:00 and 16:00 London.
- **Definitions per closed H1 candle:** `body = |close − open|`, `range = high − low`, `upper_wick = high − max(open, close)`, `lower_wick = min(open, close) − low`.
- **SELL signal:** `high ≥ PDH` AND `close < PDH` AND `upper_wick ≥ 2 × body` AND `upper_wick ≥ 0.5 × range`.
- **BUY signal:** `low ≤ PDL` AND `close > PDL` AND `lower_wick ≥ 2 × body` AND `lower_wick ≥ 0.5 × range`.
- **Entry:** next candle open. **Stop:** beyond the signal candle's wick tip (high for a sell, low for a buy), plus the current spread. **Target:** 1.5R. **Time exit:** 20:00 London.
- **Limits:** at most one trade per level per day (so at most two per day).

### S3 — Donchian breakout (H4)
- **BUY:** an H4 candle closes above the highest high of the previous 20 H4 candles. **SELL:** closes below the lowest low of the previous 20.
- **Entry:** next H4 open, only when flat.
- **Initial stop:** 2 × ATR(20, H4) from entry.
- **Exit (whichever comes first):** a long exits when an H4 candle closes below the lowest low of the previous 10 H4 candles (a short exits when one closes above the previous 10-candle high), at the next open; or the stop is hit; or the weekend close (§3). No profit target.
- **No session restriction** except the news blackout and no new entries after 16:00 London on Friday.

### S4 — RSI(2) pullback (H1)
- **Indicators on H1 closes:** SMA(200); RSI(2) with Wilder smoothing; ATR(14).
- **BUY:** close > SMA(200) AND RSI(2) < 10. **SELL:** close < SMA(200) AND RSI(2) > 90.
- **Entry:** next candle open, only when flat, signals only 07:00–16:00 London.
- **Exits (first of):** long exits when RSI(2) closes > 70 (short when < 30), at the next open; stop at 2 × ATR(14) from entry; time exit 20:00 London.

### S5 — Time-of-day (Asian-hours long)
Based on documented intraday seasonality: gold tends to rise during Asian hours and fall during Western hours.
- **Entry:** BUY at the first price at or after **18:00 New York** (the start of the new trading day, after the daily break, so no swap is charged), Sunday through Thursday evenings.
- **Exit:** **03:00 New York** (London open, 08:00 London).
- **Stop:** 2 × ATR(14, H1) below entry.
- **Long only, by design.** Skip the day if a high-impact event falls inside the holding window.

## 3. Common settings (identical for all strategies)

- **Edge is measured in R** (1R = the trade's initial stop distance × size). For the main comparison, position size is **fractional** (no minimum-lot rounding), so every signal is traded. Real lot limits are applied only in the tradeability check (§7).
- **Costs:** as in Experiment 1. Real spread per bar from 2025-12-17, the estimated hourly 75th percentile before that; commission base 0.0007% of notional per side.
  - **Stresses:** 1.5 × spread; 0.0025% per side.
  - **Swap (overnight holds, mainly S3):** use the broker's current `swap_long` / `swap_short` and triple-swap day from `symbol_info`, applied to all history, labelled as an estimate.
- **News blackout (all strategies):** no new entries from 30 min before to 30 min after any event in the fixed USD event list. Open trades keep their exits. Report FTMO-flagged exits (±2 min).
- **Fills:** signal on a closed candle, filled at the next candle's open, paying the spread. **Same-candle rule:** if one candle touches both stop and target, use M1 to see which came first; if M1 is unavailable, assume the stop.
- **Weekend (FTMO Standard):** every position closes by 20:00 London on Friday; no new entries after 16:00 London on Friday. Holding across the normal ~1-hour daily break is allowed. Flag any trade held across a market break longer than 2 hours (holidays).
- **Netting:** one gold position at a time. This matters only in the combination (§6).
- **No kill switch in backtests.** FTMO rules are simulated in the tradeability check.
- **Leak safety:** the future-scramble test (20 random cut times) must pass for every strategy. All data goes through `src/data_access.py`.

## 4. Data periods (LOCKED)

| Use | Period |
|---|---|
| **Main comparison** (all verdicts in this spec) | 2022-01-01 → 2025-12-31 |
| Recent information only (no verdicts; already seen in Exp. 1) | 2026-01-01 → latest |
| Reserved, **not used in Experiment 2** | 2010-01-01 → 2021-12-31 — kept locked for a single future confirmation run of whatever survives |

Indicator warm-up (e.g. SMA(200), the 20-day trend) may only use bars from 2022 onward. The first days of 2022 simply have no signal until enough history exists. No reaching into 2021.

## 5. Controls and diagnostics (per strategy)

- **C1 — random direction:** same entry times, same stop distance and same holding time as the strategy's real trades, but random direction. 200 seeds. This tests whether the strategy's direction calls beat a coin flip.
- **Buy-and-hold gold reference** over the same period (S5 is long-only, so this matters).
- **Regime table:** classify each month of 2022–2025 by trend strength, where `efficiency = |month's net change| / sum of |daily changes|` from daily closes. Above the 2022–2025 median = "trending", below = "ranging"; also up vs down. Report each strategy's R in each regime. This answers "where does each strategy fail?"
- **Robustness nudges** (report, never select):

  | Strategy | Nudges |
  |---|---|
  | S1 | box end 06:30 / 07:30 |
  | S2 | wick ratio 1.5 / 2.5 |
  | S3 | channel 16 / 24 |
  | S4 | RSI thresholds 5 / 15 (and 95 / 85) |
  | S5 | exit 02:00 / 04:00 New York |

  Flag any strategy whose results collapse under a nudge.

## 6. Combination

- **Eligible:** strategies that pass the §7 "promising" test.
- **Correlation:** report the matrix of monthly R between all five strategies (standalone runs), so we can see which ones lose at the same time.
- **Combined run:** all eligible strategies on one account, with the netting rule. **First signal wins:** while a position is open, other strategies' signals are skipped and logged, with counts per strategy. Same R per trade.
- If fewer than two strategies are eligible, also run the combination of the **two least-correlated strategies with positive expectancy**, labelled information only.

## 7. Pass criteria (LOCKED) — all on 2022–2025

**A strategy is "promising" if ALL of:**
- Expectancy **≥ +0.10R per trade** after base costs
- Positive total R in **≥ 3 of the 4 years**
- Beats **≥ 90%** of C1 runs on total R
- Still positive expectancy under both cost stresses
- No collapse under its robustness nudges

**The combination is "better" if ALL of:**
- Total R ≥ the best single eligible strategy's
- Max drawdown (in R) ≤ the best single strategy's
- Higher percentage of profitable months than the best single strategy

**Tradeability check** (for promising strategies and the combination), using real lot rules (0.01 minimum and step) on the FTMO $10k account at **$50 and $100 risk per trade**:
- Percentage of signals skipped because of the minimum lot
- Average $/month
- Percentage of months profitable
- Worst month and max drawdown in $
- FTMO breach (5% daily / 10% total) yes/no

Yash's goal is ≥ $100/month average, ≥ 4 of 6 months profitable, and no breach.

**Nothing is "confirmed" by this experiment.** Survivors still need the single reserved 2010–2021 run and a paper forward test before any real money.

## 8. Phases — stop for Yash's review after each

- **E2-1 Build and verify:** implement S2–S5, re-wire S1 to the common settings, add C1 and the regime classifier, and pass the future-scramble test for every strategy. Export 5 trades per new strategy (UTC + MT5 server time, levels, entry, stop, exit) for Yash to hand-check. No performance numbers yet.
- **E2-2 Main comparison:** all five on 2022–2025 with C1, cost stresses, regime table, nudges, and the per-year table. Verdict per strategy (§7).
- **E2-3 Combination:** correlation matrix plus the combined run(s).
- **E2-4 Tradeability and recent information:** the real-lot check at $50 / $100 risk, then all strategies and the combination on 2026 (information only).
- **E2-5 Report:** `results/exp2/report.md` with a plain-English summary first.

## 9. Later (not in this spec)
- Single confirmation run on 2010–2021 for all survivors together.
- Paper forward test of the final choice.
- Optional: a once-a-day Claude morning briefing (news and event schedule) as a no-trade-day check.

## Change Log
- v1.0 — 2026-10-08 — initial lock. Experiment 1's pending Phase 4c is folded into the future single 2010–2021 run (§9).
- v1.0 clarifications — 2026-10-08 — confirmed by Yash before any Experiment 2 result: (1) each strategy holds at most one position at a time in its standalone run; a signal while in a trade is skipped and counted. (2) C1 exit: random direction, same stop distance, otherwise closed at the real trade's exit time; no profit target. (3) Swap: the broker reports swap mode 5 (annual interest % of the current price), long −5.66%, short −3.02%, and an invalid triple-swap day (7); per Yash, the Wednesday-night rollover charges 3 nights. Per-night swap = price × 100 oz × lots × rate ÷ 360, applied to all history as an estimate.
- v1.0 implementation choices — 2026-10-08 — made in E2-1, approved by Yash after hand-checking 20 trades, before any performance result: (1) H4 bars = H1 bars grouped into 4-hour blocks of broker server time (as MT5 builds them). (2) All ATRs use Wilder smoothing (as the RSI). (3) S2: the stop's "current spread" is the spread at entry; each level gives one signal per day, even if that signal is blocked by news; a candle qualifying at both PDH and PDL is skipped. (4) S5: the stop uses the last H1 ATR completed before 18:00 New York; an evening with no price within 60 minutes of 18:00 is skipped. (5) Holidays: a trade still open when the market halts early is closed at the first price after the reopen and flagged; but a Friday deadline is never crossed — if the market closes early on a Friday, the trade exits at the last price before the close ("closes by 20:00 London Friday"). (6) Entries from Friday 16:00 London are blocked for every strategy, including S1.
- v1.0 clarification 4 — 2026-10-08 — set by Yash before any E2-2 result: a robustness nudge "collapses" if its expectancy per trade (R, base costs) falls below half of the strategy's base expectancy, or to zero or below.
- v1.0 addition — 2026-10-08 — requested by Yash after E2-2 (no strategy promising), recorded before running E2-3: one extra **information-only** combined run of all three positive-expectancy strategies, **S1 (H1) + S3 + S5**, on one account with the netting rule (first signal wins; skipped signals logged per strategy). It cannot produce a verdict. Combination mechanics (apply to every combined run): the account is busy from a strategy's signal until its position closes (including the wait for the next-bar fill), so another strategy's signal in that time is skipped; events at the same timestamp are processed exits first, then fills, then new signals; ties between strategies go in the order S1, S3, S5. Results are also shown in $ at $50 risk per trade (R × $50, fractional size).
