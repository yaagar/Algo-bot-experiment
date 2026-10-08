# Experiment 3 — Multi-Market Daily Trend-Following — Spec v1.0 (LOCKED)

Owner: Yash. Built by: Claude Code. Written: 2026-10-08.

**Locked:** rules, markets, periods and pass criteria must not change after any Experiment 3 result is seen. If something is impossible, STOP and ask Yash, and log approved changes in the Change Log.

Inherited unchanged from earlier specs unless stated: the leak-free engine (decisions on closed bars only, fills at next open, future-scramble test), the data lock (`src/data_access.py`), cost/swap handling, the FTMO rule simulation and the netting rule. **Reuse existing code (especially Experiment 2's S3 Donchian), don't rewrite it.**

---

## 1. The question
Does **one simple trend-following rule on daily bars, run across ~10 different markets at once**, produce a positive edge after costs with drawdowns small enough for an FTMO account?

**Why:** Experiments 1–2 found no edge in intraday gold rules. Research finds daily/monthly trend-following profitable on average in nearly every market, but bumpy in any single one. Spreading across markets that trend at different times smooths the results (Moskowitz, Ooi & Pedersen 2012; Hurst, Ooi & Pedersen 2017).

## 2. Strategy — Donchian 55/20 (Turtle "System 2"), daily bars
Experiment 2's S3 code, run on **D1** bars with these settings:
- **BUY:** a daily close above the highest high of the previous 55 days. **SELL:** a daily close below the lowest low of the previous 55.
- **Entry:** next day's open, only when flat in that market.
- **Initial stop:** 2 × ATR(20, daily, Wilder) from entry.
- **Exit:** a long exits when a daily close is below the lowest low of the previous 20 days (a short when above the previous 20-day high), at the next open; or the stop is hit. No target, no time exit.
- **Weekends and overnight holds allowed** (FTMO **Swing** account). Swap is charged.
- **News blackout:** none (daily system; FTMO Swing has no news restriction).
- One position per market (netting). Markets are independent.

## 3. Markets (10)
Gold, Silver, WTI crude oil, S&P 500 index, Nasdaq 100 index, Germany 40 index, Japan 225 index, EURUSD, USDJPY, AUDUSD.
- Detect the broker's symbol names (e.g. `.sim` suffix).
- If a market isn't available or has too little history, **skip it and report**. Don't substitute another.

## 4. Data and periods
- **Bars:** D1 per market from MT5, 2022-01-01 → latest, through the data lock. If the broker's D1 day boundary differs from New York 17:00, build daily bars from H1 at the broker's day boundary (consistent with earlier experiments). Warm-up (55 days + ATR) happens inside 2022; no pre-2022 data.
- **Window:** 2022-01-01 → 2026-09-30, one window. No strategy here was ever tuned on any of this data. Results are reported per calendar year.
- **Spread:**
  - per market, the 75th percentile of real recorded spread at the daily-bar open hour;
  - where the broker recorded 0 (history before 2025-12-17), use that 75th percentile, labelled as an estimate.
- **Commission (base):**

  | Asset class | Base commission |
  |---|---|
  | Metals | 0.0007% of notional per side (observed on Yash's FTMO trial) |
  | FX | $2.50 per lot per side |
  | Indices | $0 |
  | Oil | 0.001% of notional per side |

  If the broker's symbol info or Yash's trial shows different values, **ask Yash before running**.
- **Swap:** each market's current `swap_long` / `swap_short` and triple-swap day from `symbol_info`, applied to all history, labelled as an estimate.

## 5. Evaluation (keep it lean)
1. **In R, fractional size:** per market and for the equal-risk portfolio (every market risks the same R per trade). Report trades, expectancy (R/trade), total R, % profitable months, max drawdown (R), worst month, per-year R.
2. **C1 random direction (200 seeds):** same entries, stops and holding times, coin-flip direction; for the portfolio.
3. **Stresses:** 1.5 × spread, 2 × commission, 1.5 × swap cost.
4. **Diversification check:** the portfolio's max drawdown vs the average single-market max drawdown; and the correlation matrix of monthly R between markets.
5. **FTMO Swing tradeability** (real lot rules per symbol: min lot, step, contract size, tick value from `symbol_info`):
   - **Account and risk:** $10k account, risk per trade **0.25% ($25)** and **0.5% ($50)** of initial balance.
   - **Report:** % of signals skipped because of min lot, average $/month, % months profitable, worst month, max drawdown in $, and FTMO breaches (5% daily, 10% total).
   - **Daily loss is checked conservatively:** each open position's worst intraday price that day (its daily high/low) counts against the 5% limit.
   - **Margin:** report if margin at 1:30 leverage would ever exceed account equity.
6. **Leak test:** the future-scramble test (20 cuts) on the portfolio run.

## 6. Pass criteria (LOCKED)
**Edge (portfolio, base costs):**
- Expectancy ≥ +0.10R per trade
- Positive total R in ≥ 3 of the 4 full years (2022–2025)
- Beats ≥ 90% of C1 runs
- Still positive under each stress

**Diversification works:** portfolio max drawdown (R) < the average single-market max drawdown (R).

**Tradeable for Yash (at 0.25% or 0.5% risk):**
- ≥ $100/month average
- ≥ 4 of every 6 months profitable
- No FTMO breach
- Margin never exceeded

A pass is still **provisional**. It needs a paper forward test before any real challenge.

## 7. Phases (two stops only)
- **E3-1 Data and build:** detect symbols, download D1 (or H1 to build D1) for all 10 markets, record costs and swap per market, wire the 55/20 settings into the existing S3 code, run the leak test, and run a quick automated sanity check (signals recomputed independently with a simple vectorised check must match the engine). Report: market availability, history start dates, cost table. **No performance numbers.**
- **E3-2 Run and report:** everything in §5 → `results/exp3/report.md`. Plain-English summary first, then tables, kept short.

## Change Log
- v1.0 — 2026-10-08 — initial lock.
