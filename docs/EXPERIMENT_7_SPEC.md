# Experiment 7 — Trend → Consolidation → Breakout on Gold ("Yash's pattern") — Spec v0.10 (DRAFT)

Owner: Yash. Built by: Claude Code. Written: 2026-10-08.

**Status: DRAFT.** Only Phase E7-0 (pattern count, no outcomes) may run under v0.10. After E7-0, Yash may adjust definitions (counts reveal frequency, not profit); then the spec is locked as v1.0 before any outcome is computed. After v1.0, nothing changes because of a result.

Inherited: data lock (`src/data_access.py`), clock rules, leak-free fills (decide at bar close, fill next bar open, stop-first on same-bar ties, M1 for resolution), commission table, FTMO rule simulation (portfolio-level `ftmo_rules.py` from Exp 6), trial ledger.

## 1. The question
On gold, does a breakout from a tight consolidation that follows a clear trend continue in the trend's direction often enough to profit after real costs?

## 2. Market, timeframes, hours
- XAUUSD only. **Trend on H1; consolidation, entry and management on M15** (M15 built from M1 where needed).
- New entries 07:00–20:00 London; any open trade closed at 20:00 London. FTMO Standard compatible (no overnight, no weekend). No entries ±5 min around the fixed USD event list.
- One position at a time.
- **Periods:** development 2019-01-01 → 2025-12-31; final exam 2010-01-01 → 2018-12-31 (one run, later). 2026 is never used for any decision. Pre-2022 XAUUSD use confirmed by Yash on 2026-10-09 (`results/data_access_log.md`).

## 3. Definitions (all computed on closed bars, past data only)
**Swings:** a swing high is an H1 bar whose high is the highest of the 5 bars centred on it (confirmed 2 bars later); swing low likewise.

**Trend (H1), at the moment of the breakout:**
- Uptrend: the last 3 confirmed swing highs are rising AND the last 3 swing lows are rising (≥ 2 higher highs and ≥ 2 higher lows). Downtrend: mirror.
- Strength: t-statistic of the OLS slope of the last 48 H1 closes ≥ +2.0 for up (≤ −2.0 for down).

**Consolidation box (M15):**
- The most recent run of ≥ 6 consecutive closed M15 bars whose combined high−low ≤ 1.5 × ATR(14, H1).
- A run may not cross the daily break or a weekend: any gap > 30 min between bars ends the run.
- Box high/low = highest high / lowest low of those bars; midpoint = average of the two.

**"Messy — do not trade" (any one blocks the setup):**
- More than 1 bar inside the box run closed outside a prior box edge and came back (false breaks).
- Choppiness Index(14, M15) at the breakout bar > 61.8.
- Box height > 3 × ATR(14, M15) (a range, not a pause).

**Entry:** an M15 bar closes above the box high in an uptrend (buy) or below the box low in a downtrend (sell). Fill at the next M15 open + spread.

**Stop:** box midpoint, but never closer than 1 × ATR(14, M15) from entry; if the stop lands within $0.50 of a round $10 level, move it $0.50 beyond that level.

**Target:** the nearest earlier qualifying M15 box within the last 20 London trading days whose midpoint lies beyond entry in the trade direction (target = that midpoint), placed $0.50 before the nearest round $10 level if one lies between. If none exists or it is < 1R away: target = 2R. Time exit 20:00 London.

**Spread model (guard and costs):** tick-p75 spread per broker hour as a **fraction of price** (from 2026 ticks) × that bar's price. Commission as before. Stress tests: 1.5× spread; +1 tick slippage.

**Cost guard:** skip the setup if the modelled spread at the fill bar > 10% of the stop distance.

## 4. Phases
- **E7-0 Pattern count (no outcomes).** Count qualifying setups in the development period (first run 2022–2025 under v0.9; recount 2019–2025 under v0.10): per year, per month (median/min/max), per direction; how many blocked by each "messy" rule and by the cost guard; typical stop distance in $ and spread/stop ratio. No returns, win rates, R, or exit outcomes may be computed or printed.
- **Lock v1.0** (Yash): adds a fixed list of robustness variants (box min bars, ATR multiple, t threshold), reported and never selected. Then E7-1 build & verify, a mechanics check before E7-2 (trades per year / direction / session, no P&L), E7-2 dev run (2019–2025), E7-3 one-time exam on 2010–2018.
- **Build discipline:** during build/debug, never print or inspect P&L, R, equity, win rates or exit-reason counts; debug on synthetic data or with outcome fields hidden. Any glimpse must be reported.

## 5. Pass criteria (to be confirmed at v1.0; same spirit as Exp 4)
Controls (1,000 seeds each): **C1** random direction (same times/stops/targets); **C2** trend-only baseline (same number of trades, random entry times inside trading hours when the H1 trend condition holds, always in trend direction, same stop/target/cost rules).

Dev 2019–2025: ≥ 150 trades; expectancy ≥ +0.10R after costs; positive in ≥ 5 of 7 years; beats ≥ 95% of C1 AND ≥ 90% of C2; Deflated Sharpe ≥ 0.95 with ledger N; positive under 1.5× spread. **Idea-source check** (the pattern was noticed in 2025–26): expectancy ≥ +0.05R on 2019–2024 alone (2025 excluded).

Exam 2010–2018: expectancy ≥ +0.05R, positive in ≥ 6 of 9 years, beats ≥ 90% of C1 and of C2, positive under 1.5× spread.

Optional pre-declared layer (decided at v1.0, counted in the ledger): a meta-labeling probability filter with ≤ 4 inputs — only if the E7-0 recount shows ≥ 300 setups.

## Change Log
- v0.9 — 2026-10-08 — draft for E7-0 count only.
- v0.10 — 2026-10-09 — changes after E7-0 counts only; no outcomes computed. (a) periods: dev 2019–2025, exam 2010–2018, 2026 never used; (b) box runs end at any gap > 30 min; (c) spread = 2026 tick-p75 fraction of price × bar price, 1.5× spread and +1 tick slippage stresses; (d) target lookback 20 London trading days; (e) controls C1 + C2; (f) pass criteria for 7 dev / 9 exam years; (g) meta-labeling only if recount ≥ 300; (h) idea-source check on 2019–2024; (i) build discipline; (j) robustness variants and mechanics check to be fixed at v1.0.
