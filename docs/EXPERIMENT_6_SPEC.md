# Experiment 6 — Diversified Trend Portfolio on FTMO Swing — Spec v1.0 (LOCKED)

Owner: Yash. Built by: Claude Code. Written: 2026-10-08.

**Locked:** every rule, number, period and pass criterion below is fixed before any Experiment 6 result exists. If something is impossible or ambiguous, STOP and ask Yash; record any approved change in the Change Log *before* running anything it affects. Nothing may change because of a result.

Inherited unless stated: data lock (`src/data_access.py`), clock handling (broker server = New York + 7 h from 2021, fixed UTC+2 before 2021), cost model, leak-free fills, trial ledger, C1 idea. Reuse code; one config-driven runner (`config/exp6.yaml`).

---

## 0. Why this design (lessons from Experiments 1–4)

| Lesson | Built in here |
|---|---|
| Textbook intraday patterns had ~zero edge before costs | Use the one pattern with decades of multi-market evidence: time-series momentum (trends persist) |
| Costs were large relative to small intraday moves | Daily signals, positions held days–weeks, no-trade buffer to avoid tiny trades |
| Swap destroyed Exp 3 | Real per-symbol swap charged every night; markets with too-high cost are excluded *before* any result, using costs and volatility only |
| One market / one regime drove everything | All tradeable FTMO symbols, equal risk each, portfolio volatility targeted |
| Combining zero-edge signals doesn't help | One idea only (trend), three standard lookbacks — not tuned |
| Mean reversion failed in trending markets | Not used |
| Short good stretches fooled us | 2022–2025 is only a **gate**; the decisive test is the untouched 12-year 2010–2021 exam |
| Spec flaws found late | Mechanics check (trade counts, positions per market, no P&L) before any run |
| 2022–2025 already used by 69 trials (incl. Exp 3 daily trend on 8 of these markets) | Exp 6 configurations are added to the ledger; the exam carries the verdict |

**Known contamination (disclosed):** the choice of a cost-aware, diversified trend system was informed by Exp 1–4 results on 2022–2025. That knowledge pushes toward caution (costs), not toward fitted parameters. No parameter here was chosen by looking at any return.

## 1. The question
Does a cost-aware, volatility-targeted trend portfolio across all tradeable FTMO symbols earn a real return after spread, commission and swap, robustly enough to run on an FTMO 2-Step **Swing** account without breaching its limits?

## 2. FTMO account terms modelled (2-Step, Swing, US / FTMO×OANDA)
Sources checked 2026-10-08: ftmo.com Trading Objectives; ftmo.oanda.com FAQ "What are the account specifications?"; dated 2026 third-party summaries. Yash re-checks the checkout page before buying; any difference → Change Log before running.

| Item | Value modelled |
|---|---|
| Account type | 2-Step, **Swing** (weekend and overnight holds allowed; no news restriction) |
| Leverage | Swing up to **1:30**. Per-asset Swing leverage not published → assume **1:30 for every symbol** unless `symbol_info` margin data is stricter; report peak margin use |
| Max Daily Loss | Equity (balance + floating P/L ± swaps − commissions) must stay above **(balance at 00:00 CE(S)T) − 5% of initial capital**. Reset at **00:00 CE(S)T** (= 01:00 broker server time). Checked on intraday (H1 high/low) equity, not only closes |
| Max Loss | Static: equity must stay above **90% of initial capital**, always |
| Profit targets (evaluation only) | Phase 1: +10%; Phase 2: +5%; balance with all positions closed; no time limit |
| Minimum trading days | 4 per evaluation phase (a day counts only if a position is **opened**) |
| Funded account | No target. First reward ≥ 14 days after first funded trade, then on request; account must be in profit with **no open positions** at request; split 80% (90% via scaling) |
| Costs | Real spread; commission and **swap per night** from `symbol_info` (`swap_long`, `swap_short`, `swap_rollover3days`) |
| Platform clock | MT5 server GMT+2 with DST (matches project clock) |

Rewards require **no open positions**, so the system must be able to go flat on a chosen day. The FTMO report (§9) shows the cost of a once-a-month flatten-and-reopen for reward requests (information only).

## 3. Markets
Candidate set = every symbol on Yash's FTMO MT5 account (`symbols_get()`; Market Watch shows 49, not only the 16 in the menu). Exclude crypto and any symbol with < 3 years of daily history in 2022–2025.

**Cost screen (decided before any return is computed; uses only spread, commission, swap and volatility):**
- `cost_ratio` = round-trip cost per unit (75th-percentile spread at 10:00 New York in 2026 recorded data, + 2× commission) ÷ median daily ATR(20) over 2022–2025.
- `carry_ratio` = worst-side annual swap cost per unit (max(−swap_long, −swap_short, 0) × 365, incl. triple days) ÷ annualised standard deviation of daily price changes per unit over 2022–2025.
- **Exclude** a symbol if `cost_ratio > 0.10` or `carry_ratio > 0.30`.
- If fewer than **8** symbols survive, STOP and report: a diversified test is impossible.
- Correlated markets are kept (risk is controlled at portfolio level, §5).

## 4. Signal
At each broker-day close (New York 17:00), for each market and lookback L ∈ {21, 63, 252} trading days:
`s_L = sign(close_today − close_L_days_ago)` (0 if equal).
**Forecast** `f = (s_21 + s_63 + s_252) / 3` ∈ {−1, −⅓, 0, ⅓, 1}.
A market trades only when all three lookbacks and 60 days of volatility history exist inside the current period.

## 5. Sizing
- Per-market unit: size such that 1 unit has expected daily $-volatility `(target_vol × capital / √252) / √N`, with σ = std dev of daily price changes over the previous **60** broker days (past only). N = markets currently tradeable.
- Desired position = `f × unit`.
- **Portfolio scaler:** each day compute ex-ante portfolio volatility of desired positions from the 60-day covariance of daily returns (past only); scale all positions so it equals `target_vol`, capped at 2.0× and at the §2 margin limit.
- **No-trade buffer:** trade a market only if |desired − current| > **25%** of that market's full unit (|f| = 1); otherwise keep the current position.
- Round to lot step; if below minimum lot, hold 0 and count the skip.
- `target_vol` for the edge verdict: **10% annual** (reference; results scale linearly). FTMO table: 5% and 8%.

## 6. Execution and costs
- Signals at broker-day close; orders filled at the **open of the 10:00 New York H1 bar** the next trading day (liquid hour, avoids the rollover spread spike), plus spread at that hour.
- Spread: real recorded where available, else the 2026 75th-percentile hourly estimate. Commission per symbol. Swap every night held, triple per `swap_rollover3days`.
- **Swap caveat:** swap is applied at current (2026) rates in every period because history is unavailable. Declared, and stressed ×1.5.
- No stop-losses (exits come from the signal). Intraday equity for FTMO checks from H1 high/low.
- Positions are held through weekends (Swing); gaps are real.

## 7. Periods, controls, ledger

| Use | Period | Runs |
|---|---|---|
| **Gate** | 2022-01-01 → 2025-12-31 (trading effectively from ~2023 after warm-up) | Main, C1, stress, robustness, benchmark |
| Recent information | 2026-01-01 → latest | Main only, no decisions |
| **Final exam** | 2010-01-01 → 2021-12-31 | **One run**: main + C1 + stress + robustness + benchmark, only if the gate passes and Yash approves with the data-lock sentence |

- Warm-ups use only bars inside each period; never cross a period boundary.
- Markets join the exam when their data plus warm-up exist (e.g. US100 from 2014-09-15; MetaQuotes FX H1 from Aug 2010).
- **C1 random direction:** per market, every time the real forecast changes sign, draw a fresh coin flip for the sign; magnitudes, timing, sizing, costs identical. 1,000 seeds. Metric: net total return.
- **Benchmark (information):** long-only, same markets, sizing and costs (f = +1 always).
- **Robustness (pre-declared, reported, never selected):** single lookback 21 / 63 / 252; buffer 0% / 50%; execution at 12:00 New York.
- **Cost stress:** 1.5× spread, 1.5× swap, 2× commission, +1 tick slippage per fill, all together.
- **Trial ledger:** add every Exp 6 configuration (main, 3 single lookbacks, 2 buffers, 12:00 execution, benchmark = 8) before computing the Deflated Sharpe. N = max(ledger count, 50).
- **Leak safety:** future-scramble test (20 cuts) on the full system; independent rebuild of signals, sizing and FTMO checks sharing no engine code, matching every day; hand-check export of 10 position changes with times, prices, forecasts, sizes, swap charged.

## 8. Pass criteria (LOCKED)
Metrics use daily portfolio returns at 10% target vol, net of all costs. Sharpe = annualised mean ÷ std dev of daily returns.

**Gate (2022–2025). ALL must hold — otherwise Experiment 6 fails and the exam is not used:**
- ≥ 8 markets pass the cost screen
- Net Sharpe > 0 at base costs
- Net Sharpe > 0 under the cost stress
- Beats ≥ 80% of C1 runs
- Costs (spread + commission + swap) < 50% of gross profit, when gross profit > 0

**Final exam (2010–2021, one run). ALL must hold:**
- Net Sharpe ≥ **0.40** at base costs
- Net return positive in ≥ **70%** of full calendar years traded
- Beats ≥ **95%** of C1 runs
- Deflated Sharpe probability ≥ **0.95** with the ledger's N
- Net Sharpe ≥ **0.20** under the cost stress
- Every robustness variant net Sharpe > 0

**Only if both pass** → FTMO tradeability (§9), then an 8-week paper forward test on the FTMO demo (separate spec), then money.

## 9. FTMO tradeability (after the exam passes; both periods; not part of the edge verdict)
At 5% and 8% target vol on $10k, $25k and $50k Swing accounts, real lot rules:
- Breaches of Max Daily Loss and Max Loss (§2 definitions, intraday equity)
- Average $/month to Yash after the 80% split; % months positive; is **every rolling 12-month window** positive?
- Annual return %, max drawdown, worst day, worst month
- Days to reach Phase 1 (+10%) and Phase 2 (+5%) from random start dates
- Min-lot skips %, peak margin use vs 1:30
- Cost of a monthly flatten-and-reopen for reward requests

**Yash's goal for Exp 6:** average ≥ 5% a year, every rolling 12-month window profitable, no FTMO breach.

## 10. Phases (stop after each)
- **E6-0 Data prep (no returns).** Inventory all account symbols; pull daily and H1 data 2022+; record current spread, commission, swap and contract specs per symbol. Pre-2022 preparation only with Yash's dated data-lock sentence for "data preparation only". Report coverage.
- **E6-1 Build and verify (no performance numbers).** Cost screen (included/excluded with ratios), signals, sizing, buffer, execution, swap, FTMO simulation per §2 (fix `ftmo_rules.py` where it differs, e.g. 00:00 CE(S)T reset, balance-based daily limit), C1, ledger rows, leak tests, rebuild, hand-check export, mechanics table (position changes per market per year, average holding days, % of days at each forecast level). Report < 30 lines.
- **E6-2 Gate run.** §7–§8 on 2022–2025 + 2026 info. Report < 50 lines: plain summary, gate table, per-market and per-year tables, robustness/benchmark table. No FTMO table yet.
- **E6-3 Final exam** (only if gate passes + Yash approves with the data-lock sentence). One run; verdict table; then §9 FTMO table.

## Change Log
- v1.0 — 2026-10-08 — initial lock.
- v1.1 — 2026-10-08 — Decided by Yash before any Exp 6 result exists; driven by data availability, not results.
  (a) §3/§6 FX prices: FX price history (D1, H1) for 2022+ comes from MetaQuotes-Demo for every FTMO FX pair it has with full 2022–2025 coverage (second terminal OK to launch). Costs stay FTMO's: spreads recorded on the FTMO account (75th pct hourly, 2026), FTMO swaps, project commission table. FX pairs without full MetaQuotes coverage are excluded. Same rule for pre-2022 in E6-3.
  (b) §5 risk allocation: target risk split equally across 3 asset classes — FX, equity indices (US30, US100, US500), commodities (XAU, XAG, USOIL) — then equally across markets within each class that pass the cost screen. Replaces the 1/√N per-market rule; the portfolio vol scaler is unchanged.
  (c) §6 triple swap: Wednesday for FX and metals, Friday for indices and oil (Exp 3 convention), because swap_rollover3days is invalid.
  (d) §6 commission: project table (metals 0.0007%/side, FX $2.50/lot/side, indices $0, oil 0.001%/side).
  (e) §2 daily-loss reset: exactly 00:00 Europe/Prague (tz-aware), not a fixed server hour.
  (f) §6 swap snapshot: explain the US500 difference vs Exp 3 using each symbol's swap_mode; convert every symbol's swap to $ per 1 lot per night. If the difference is fully explained, lock the E6-0 snapshot; if not, use the more costly value of the two snapshots per side. Locked table recorded in results/exp6/.
- v1.2 — 2026-10-08 — Decided by Yash before any Exp 6 result; input correction, not result-driven.
  MT5 bar 'spread' is the minimum within the bar, so it is not used anywhere in Exp 6. All spreads (cost screen §3 and backtest cost model §6) come from FTMO tick data (copy_ticks_range, ask − bid):
  - per symbol and per broker hour of day, the 75th percentile of tick spreads, using all 2026 ticks available on the FTMO terminal (if 2026 ticks are missing for a symbol, use the most recent 3 months available and record which);
  - the cost screen uses the 10:00 New York hour; the backtest uses the hour of each fill;
  - the same table applies to all periods (declared assumption, already stressed ×1.5).
- v1.3 — 2026-10-08 — Clarifications approved by Yash before any Exp 6 result (no rule or number changed).
  (a) Edge runs (gate, exam) use fractional lots on a notional $100,000 account (results are % of capital, linear in capital); lot-step / min-lot rounding and the skip counter apply in the §9 FTMO table ($10k/$25k/$50k). E6-1's mechanics table reports the skips the FTMO sizes would have.
  (b) v1.1(b) split is linear: unit daily $-vol = (target_vol × capital / √252) × 1/3 × 1/n_class, n_class = tradeable markets in that class that day; classes with none that day are dropped and the rest share equally. "capital" = initial capital (no compounding). The portfolio scaler then rescales to target_vol (cap 2.0×).
  (c) Margin cap: total required margin (Σ |lots × contract × price| in USD / 30) ≤ 100% of current equity.
  (d) Accounting MT5-style: netting by average price; reducing a position realises P/L on the reduced lots into balance; commission hits balance at each fill; swap accrues on the open position (in equity) and moves to balance pro rata when lots are closed.
- v1.4 — 2026-10-08 — §9 information rows: add $100k and $200k account sizes because of the E6-1 min-lot mechanics finding. Reporting only; no rule, signal, sizing or pass criterion changes. Note: during E6-1 debugging a breach of the 90% floor in Oct 2023 on the $100k test account was seen; no code or rule was changed because of it.
- v1.5 — 2026-10-08 — Scoring clarifications approved by Yash before any E6-2 result.
  (a) Daily-return series (gate Sharpe, per-year, DSR): every broker day from the first tradeable day (2022-12-21) to 2025-12-31; days without positions inside that range = 0. Daily return = change in equity at the broker-day close ÷ capital.
  (b) Deflated Sharpe (information in the gate, criterion in the exam), N = 77: V = max(variance of daily Sharpe across the 8 Exp 6 ledger configurations, sampling variance of the main configuration's Sharpe incl. skew/kurtosis); report which term won (Exp 4 method).
  (c) Cost share: costs = spread paid + commission + net swap paid (credits reduce it); gross profit = net profit + costs.
