# Experiment 7 — Trend → Consolidation → Breakout on Gold ("Yash's pattern") — Spec v1.0 (LOCKED 2026-10-09)

Owner: Yash. Built by: Claude Code. Written: 2026-10-08.

**Status: LOCKED (v1.0, 2026-10-09)** after E7-0 counts only; no outcomes were computed before locking. Nothing changes because of a result; any change needs a dated Change Log entry approved by Yash before the run it affects.

Inherited: data lock (`src/data_access.py`), clock rules, leak-free fills (decide at bar close, fill next bar open, stop-first on same-bar ties, M1 for resolution), commission table, FTMO rule simulation (portfolio-level `ftmo_rules.py` from Exp 6), trial ledger.

## 1. The question
On gold, does a breakout from a tight consolidation that follows a clear trend continue in the trend's direction often enough to profit after real costs?

## 2. Market, timeframes, hours
- XAUUSD only. **Trend on H1; consolidation, entry and management on M15** (M15 built from M1 where needed).
- New entries 07:00–20:00 London; any open trade closed at 20:00 London. FTMO Standard compatible (no overnight, no weekend). No entries ±5 min around the fixed USD event list.
- One position at a time; setups that occur while a trade is open are skipped and counted.
- Risk: 1R = $50 per trade, fractional lots (lots = $50 / (stop distance × 100 oz)). Results in R = net $ / $50 risk (net of spread, commission and swap).
- Stop/target/time exits resolved on M1 bars (longs on bid, shorts on ask); a bar touching both stop and target = stop first; a gap through the stop fills at the bar open. Exit at 20:00 London at the first M1 open at/after 20:00 London.
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

**Target:** fixed 2R from the actual entry price (the v0.10 zone rule is removed). Time exit 20:00 London.

**Spread model (guard and costs):** tick-p75 spread per broker hour as a **fraction of price** (from 2026 ticks, `results/exp7/e7_tick_spread_frac.json`) × that bar's open price (M15 bar for the entry, M1 bar for exits). Commission 0.0007% of value per side. Swap per rollover (none expected: flat by 20:00 London). Stress tests: 1.5× spread; +1 tick ($0.001) slippage on every fill. Stresses change costs only: the set of setups (cost guard) is decided with the 1× spread.

**Cost guard:** skip the setup if the modelled spread at the fill bar > 10% of the stop distance.

## 4. Phases
- **E7-0 Pattern count (no outcomes).** Count qualifying setups in the development period (first run 2022–2025 under v0.9; recount 2019–2025 under v0.10): per year, per month (median/min/max), per direction; how many blocked by each "messy" rule and by the cost guard; typical stop distance in $ and spread/stop ratio. No returns, win rates, R, or exit outcomes may be computed or printed.
- **Lock v1.0** (done 2026-10-09). E7-1 build & verify (engine, future-scramble test with 20 cuts, independent rebuild, C1/C2/M2 smoke tests, hand-check export, mechanics table — no outcomes). E7-2 dev run 2019–2025 (one run). E7-3 one-time exam 2010–2018 (needs Yash's dated confirmation).
- **Build discipline:** during build/debug, never print or inspect P&L, R, equity, win rates or exit-reason counts; debug on synthetic data or with outcome fields hidden. Any glimpse must be reported.

## 5. Controls, variants, pass criteria
Controls (1,000 seeds each; control trades are simulated independently, no one-position interaction):
- **C1** random direction at the real trade times: same fill bar, same $ stop distance, 2R target, same costs and exits.
- **C2** trend-only baseline: for each real trade, one C2 trade at a random M15 bar of the same period whose fill falls inside trading hours (07:00–20:00 London, outside the ±5 min news window) and where the H1 trend condition holds (swing structure AND t-stat), in the trend direction, same $ stop distance as that real trade, 2R target, same costs and exits.
- "Beats X% of C" = the real expectancy (mean net R per trade) is higher than that seed's expectancy in X% of seeds.

**Robustness variants** (reported, never selected; each re-runs the full system with one change): box min bars 5 / 8; box max range 1.25 / 1.75 × ATR(14, H1) (instead of 1.5); t threshold 1.5 / 2.5 (instead of 2.0). Pass rule: no variant with dev expectancy ≤ 0.

Dev 2019–2025 ("M1" = the base rules; years by London entry date): ≥ 150 trades; expectancy ≥ +0.10R after costs; positive total R in ≥ 5 of 7 years; beats ≥ 95% of C1 AND ≥ 90% of C2; Deflated Sharpe ≥ 0.95 (daily net R, Exp 4 method, N = ledger N); expectancy > 0 under 1.5× spread; robustness rule above. **Idea-source check** (the pattern was noticed in 2025–26): expectancy ≥ +0.05R on M1 trades entered 2019–2024 alone (2025 excluded). All must hold.

Exam 2010–2018: expectancy ≥ +0.05R, positive in ≥ 6 of 9 years, beats ≥ 90% of C1 and of C2, positive under 1.5× spread.

**Meta-labeling layer "M2"** (pre-declared; judged only if M1 passes the dev gate): logistic regression on standardized inputs, L2 penalty C = 1.0 (intercept not penalized), no tuning. Inputs at the setup: trend t-stat; box height / ATR(14, H1); box length in bars; distance from entry to the nearest $10 level / stop distance. Label: win = net R > 0. Expanding walk-forward: on each 1 January (2021 … 2025), fit on M1 trades closed before that date (standardization fitted on the same training trades), predict that year's M1 trades; first predictions 2021 (trained on 2019–2020). M2 takes an M1 trade only if predicted P(win) ≥ 0.40 (it filters M1's trade list; the one-position rule is not re-run). M2 is adopted only if M1 passes AND M2's expectancy on 2021–2025 > M1's on 2021–2025 AND M2 keeps ≥ 100 trades. M2 can never rescue a failing M1.

**Reporting rule (information only, verdict unchanged):** E7-2 ALWAYS reports M1 and M2 side by side on 2021–2025, whether M1 passes or fails: trades, expectancy, win rate, total R, per year, trades M2 skipped and the win rate of the skipped trades.

FTMO limits ($10k account) are reported for information; they are not a pass criterion.

## Change Log
- v0.9 — 2026-10-08 — draft for E7-0 count only.
- v0.10 — 2026-10-09 — changes after E7-0 counts only; no outcomes computed. (a) periods: dev 2019–2025, exam 2010–2018, 2026 never used; (b) box runs end at any gap > 30 min; (c) spread = 2026 tick-p75 fraction of price × bar price, 1.5× spread and +1 tick slippage stresses; (d) target lookback 20 London trading days; (e) controls C1 + C2; (f) pass criteria for 7 dev / 9 exam years; (g) meta-labeling only if recount ≥ 300; (h) idea-source check on 2019–2024; (i) build discipline; (j) robustness variants and mechanics check to be fixed at v1.0.
- v1.0 — 2026-10-09 — locked after counts only; no outcomes computed. (a) fixed 2R target (zone rule removed: it applied to 4% of setups), time exit 20:00 London, stop as v0.10; (b) one position at a time (skipped setups counted), 1R = $50, fractional lots, M1 resolution, stop wins ties; (c) C1 and C2 made concrete, 1,000 seeds; (d) robustness variants box min bars 5/8, box range 1.25/1.75 × ATR(H1), t 1.5/2.5, rule: none with expectancy ≤ 0; (e) M2 meta-labeling layer, walk-forward from 2021, threshold 0.40, adoption rule and side-by-side reporting; (f) ledger +8 configurations; (g) all other v0.10 rules unchanged. Clarified at lock (before any outcome): win = net R > 0; "beats C" compares expectancy; stresses change costs only; years by London entry date; DSR on daily net R as Exp 4; FTMO limits info only.
