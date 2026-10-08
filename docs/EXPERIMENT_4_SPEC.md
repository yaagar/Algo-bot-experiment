# Experiment 4 — Combined-Signal Intraday System with Regime Gates — Spec v1.0 (LOCKED)

Owner: Yash. Built by: Claude Code. Written: 2026-10-08.

**Locked:** every rule, number, period and pass criterion below is fixed **before any Experiment 4 result exists**. If something is impossible or ambiguous, STOP and ask Yash, and record the approved change in the Change Log *before* running anything affected. Nothing in this spec may be changed because of a result.

Inherited unchanged unless stated: the leak-free engine (closed bars only, fill at next open plus spread, M1 same-bar resolution with stop-first fallback), `src/data_access.py` and the data lock, cost/swap handling, FTMO rule simulation, netting, and the clock and daylight-saving handling. Reuse existing code; read `docs/LESSONS.md` for background.

---

## 0. Lessons from Experiments 1–3 built into this design

| Past problem | Safeguard here |
|---|---|
| Filters chosen after seeing results (Exp 1, Phase 4b) | All gates and thresholds are fixed in this document; no parameter is fitted to data |
| Holdout reused for several decisions (2026) | 2010–2021 is used **once**, for one configuration, only if the dev verdict passes |
| Single famous rules had tiny edges | 4 signals with different logic combined into one forecast, plus regime gates |
| Many variants tried with no count | A **trial ledger** counts every configuration ever run in this project; the Deflated Sharpe uses that count |
| Tiny samples treated as evidence (Exp 1, Phase 5) | Minimum trade counts are part of the pass criteria |
| Results driven by one bull market | Per-year and per-regime results required; years must be consistently positive |
| Markets chosen because they made money | Markets chosen for different drivers (gold, US stock index), not past results |
| Account limits mixed with edge | Edge judged in R first; FTMO tradeability checked separately |
| News blackout removed good trades | Blackout only ±5 min (FTMO compliance), since momentum is *stronger* on news days |
| Swap destroyed multi-day holds (Exp 3) | Intraday only, flat every day, FTMO Standard |
| Token-heavy, many phases | One config-driven runner, 3 stops, short reports |

**No test can make a strategy 100% certain.** This design minimises false positives; the paper forward test that follows is the last guard.

## 1. The question
Does a system that **averages 4 different simple signals into one score**, switches signals off in markets where they are known to fail, and sizes trades by signal strength produce a real edge after costs on gold and a US stock index, under FTMO Standard rules?

## 2. Markets and trading hours (intraday, FTMO Standard)

| Market | Symbol | Trading window (new entries) | Flat by |
|---|---|---|---|
| Gold | XAUUSD.sim | 07:00–16:00 London | 20:00 London |
| S&P 500 | US500.sim | 09:30–15:00 New York | 15:55 New York |

- No positions over the weekend or across the daily break.
- One position per market at a time (netting).
- At most 3 entries per market per day.
- **News:** no new entries from 5 min before to 5 min after a USD high-impact event (fixed event list). Report any exit within ±2 min of an event as "FTMO-flagged".

## 3. Signals
All signals are computed on **closed H1 bars**, using only data available at that time. Each gives a score from −1 (strong sell) to +1 (strong buy).

**Common scaling:** `score = clip(raw / (2 × σ_raw), −1, +1)`, where σ_raw is the standard deviation of that signal's raw value over the **previous 60 trading days** (rolling, past data only).

| # | Name | Raw value | Active from |
|---|---|---|---|
| A | Quiet-range breakout | If close > range high: (close − high) / range height. If close < range low: (close − low) / range height. Inside: 0. Range: gold 00:00–07:00 London; US500 18:00 (previous day)–09:30 New York | End of range |
| B | Intraday momentum | Return from the previous session's flat time (gold 20:00 London, US500 16:00 New York) to the end of the first hour of today's window (gold 08:00 London, US500 10:30 New York) | That time, for the rest of the day |
| C | Short-term trend | (close − SMA(20) of H4 closes) / ATR(20, H4) | Always |
| D | Mean reversion | −(close − SMA(20) of H1 closes) / ATR(14, H1) | Always |

Signal B's raw value is fixed for the day once set. ATRs use Wilder smoothing.

## 4. Gates (fixed, not fitted)

**Regime gate** (the "where strategies fail" rule):
- **Efficiency** = |close today − close 10 days ago| / sum of the absolute daily changes over those 10 days, from completed daily bars only.
- **Trending** (efficiency ≥ 0.30): signal D is forced to 0, because mean reversion fails in trends.
- **Ranging** (efficiency < 0.30): signals A, B and C are forced to 0, because breakout, momentum and trend fail in chop.
- 0.30 is a common convention for Kaufman's efficiency ratio. It is **not** tuned.

**Shock gate:** no new entries if today's average H1 range so far is more than **3 ×** its median over the previous 60 days.

## 5. Combining, entries, exits and size
- **Forecast** F = (A + B + C + D) / 4, always divided by 4, with gated or inactive signals counting as 0.
- **Entry:** at an H1 close inside the window, when flat and |F| ≥ **0.30**. Direction = sign of F. Fill at the next open.
- **Exit (first of):**
  - F changes sign, or |F| < **0.10**, at an H1 close (exit at the next open);
  - the stop is hit;
  - the flat-by time.
- **Stop:** 1.5 × ATR(14, H1) from entry. No profit target.
- **Size:** risk = min(1, |F| / 0.60) × R. For the main evaluation R uses fractional lots; real lots are used only in the tradeability check (§9).

## 6. Data and periods (LOCKED)

| Use | Period | Runs allowed |
|---|---|---|
| **Development verdict** | 2022-01-01 → 2025-12-31 | Main configuration, controls, stresses, robustness variants |
| Recent information (no decisions) | 2026-01-01 → latest | Main configuration only |
| **Final exam** | 2010-01-01 → 2021-12-31 | **Exactly one run** of the main configuration + C1 + stresses, only if the dev verdict passes and Yash approves |

- **No walk-forward is needed, because nothing is fitted.** The only data-dependent quantities are rolling past-only normalisations.
- Warm-up windows (60 days, H4 SMA) may only use bars inside each period. Never reach across a period boundary, and never into the final-exam period during development.
- Spread: real where recorded, otherwise the 75th-percentile hourly estimate from 2026 (conservative for earlier, cheaper years). Commission as before (US500 $0). No swap (intraday).

## 7. Controls, diagnostics and the trial ledger
- **C1 random direction:** same entry times, stops, sizes and exits, coin-flip direction. 1,000 seeds.
- **Ablation (information only):** each signal alone, and the system without gates. Shows whether combining and gating actually help.
- **Regime table:** results in trending vs ranging days, and per year.
- **Robustness (pre-declared, reported, never selected):** entry threshold 0.20 / 0.40; stop 1.0 / 2.0 × ATR.
- **Trial ledger (`results/trial_ledger.md`):** count every distinct strategy configuration run in this project so far (Experiments 1–4, including variants, nudges, filters and combinations), from git history and the results folders. Use N = max(count, 50) in the Deflated Sharpe Ratio (Bailey & López de Prado), computed on daily returns of the main configuration.
- **Leak safety:**
  - the future-scramble test (20 cuts) on the full system;
  - an independent rebuild of the signals, gates and forecast that shares no code with the engine, which must match on every bar;
  - export 5 trades per market for Yash's hand-check, with UTC and server times and all four signal scores at entry.

## 8. Pass criteria (LOCKED)

**Development (2022–2025, portfolio of both markets, base costs). ALL must hold:**
- ≥ 200 trades in total
- Expectancy ≥ **+0.10R** per trade
- Positive total R in ≥ **3 of 4** years, and no single year below −10R
- Beats ≥ **95%** of C1 runs
- Deflated Sharpe probability ≥ **0.95** with the ledger's N
- Still positive expectancy under 1.5 × spread, 2 × commission, and +1 tick of slippage on every fill
- No robustness variant has expectancy ≤ 0

**Final exam (2010–2021, one run). ALL must hold:**
- Expectancy ≥ **+0.05R**
- Positive in ≥ **8 of 12** years
- Beats ≥ 90% of C1 runs
- Positive under 1.5 × spread

**Only if both pass** does the system go to an 8-week paper forward test (a separate spec), and only after that to any money.

## 9. FTMO tradeability (reported after a dev pass; not part of the edge verdict)
- **Account:** FTMO Standard 2-step, $10k, risk 0.25% and 0.5% of initial balance at full forecast, with real lot rules from `symbol_info`.
- **Report:**
  - % of trades skipped because of the minimum lot
  - average $/month
  - % of months profitable, and every rolling 6-month window
  - worst day and worst month
  - max drawdown
  - FTMO breaches (5% daily on equity including floating P&L; 10% total)
- **Yash's goal:** ≥ $100/month average, ≥ 4 of every 6 months profitable, no breach.

## 10. Phases (stop after each)
- **E4-1 Build and verify. No performance numbers.**
  - Signals, gates, combiner, sizing, the config-driven runner and the trial ledger.
  - Future-scramble test, independent rebuild match, and the 5-trade-per-market hand-check export.
  - Report in under 25 lines.
- **E4-2 Development run.** Everything in §7–§8 on 2022–2025, plus 2026 information only.
  - Report: plain-English summary, the verdict table, the per-year/per-regime table and the ablation table, under 50 lines.
  - Then the FTMO table (§9) only if the dev verdict passes.
- **E4-3 Final exam** (only if E4-2 passes and Yash explicitly approves, with the data-lock confirmation sentence). One run. The verdict per §8.

## Change Log
- v1.0 — 2026-10-08 — initial lock.
