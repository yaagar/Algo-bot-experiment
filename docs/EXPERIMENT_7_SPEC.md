# Experiment 7 — Trend → Consolidation → Breakout on Gold ("Yash's pattern") — Spec v0.9 (DRAFT)

Owner: Yash. Built by: Claude Code. Written: 2026-10-08.

**Status: DRAFT.** Only Phase E7-0 (pattern count, no outcomes) may run under v0.9. After E7-0, Yash may adjust definitions (counts reveal frequency, not profit); then the spec is locked as v1.0 before any outcome is computed. After v1.0, nothing changes because of a result.

Inherited: data lock (`src/data_access.py`), clock rules, leak-free fills (decide at bar close, fill next bar open, stop-first on same-bar ties, M1 for resolution), tick-based spreads (Exp 6 v1.2 table, `results/exp6/e6_0_tick_spreads.json`), commission table, FTMO rule simulation (portfolio-level `ftmo_rules.py` from Exp 6), trial ledger.

## 1. The question
On gold, does a breakout from a tight consolidation that follows a clear trend continue in the trend's direction often enough to profit after real costs?

## 2. Market, timeframes, hours
- XAUUSD only. **Trend on H1; consolidation, entry and management on M15** (M15 built from M1 where needed).
- New entries 07:00–20:00 London; any open trade closed at 20:00 London. FTMO Standard compatible (no overnight, no weekend). No entries ±5 min around the fixed USD event list.
- One position at a time.

## 3. Definitions (all computed on closed bars, past data only)
**Swings:** a swing high is an H1 bar whose high is the highest of the 5 bars centred on it (confirmed 2 bars later); swing low likewise.

**Trend (H1), at the moment of the breakout:**
- Uptrend: the last 3 confirmed swing highs are rising AND the last 3 swing lows are rising (≥ 2 higher highs and ≥ 2 higher lows). Downtrend: mirror.
- Strength: t-statistic of the OLS slope of the last 48 H1 closes ≥ +2.0 for up (≤ −2.0 for down).

**Consolidation box (M15):**
- The most recent run of ≥ 6 consecutive closed M15 bars whose combined high−low ≤ 1.5 × ATR(14, H1).
- Box high/low = highest high / lowest low of those bars; midpoint = average of the two.

**"Messy — do not trade" (any one blocks the setup):**
- More than 1 bar inside the box run closed outside a prior box edge and came back (false breaks).
- Choppiness Index(14, M15) at the breakout bar > 61.8.
- Box height > 3 × ATR(14, M15) (a range, not a pause).

**Entry:** an M15 bar closes above the box high in an uptrend (buy) or below the box low in a downtrend (sell). Fill at the next M15 open + spread.

**Stop:** box midpoint, but never closer than 1 × ATR(14, M15) from entry; if the stop lands within $0.50 of a round $10 level, move it $0.50 beyond that level.

**Target:** the nearest earlier consolidation zone in the trade direction (midpoint of the nearest prior qualifying M15 box within the last 5 trading days that lies beyond entry), placed $0.50 before the nearest round $10 level if one lies between. If none exists or it is < 1R away: target = 2R. Time exit 20:00 London.

**Cost guard:** skip the setup if spread at the fill hour (tick p75) > 10% of the stop distance.

## 4. Phases
- **E7-0 Pattern count (no outcomes).** Count qualifying setups in 2022-01-01 → 2025-12-31 (dev only): per year, per month (median/min/max), per direction; how many blocked by each "messy" rule and by the cost guard; typical stop distance in $ and spread/stop ratio. No returns, win rates, R, or exit outcomes may be computed or printed.
- **Lock v1.0** (Yash), then E7-1 build & verify, E7-2 dev run (2022–2025), E7-3 one-time exam on 2010–2021 (gold M1 exists; gap 2021-04-20 → 05-20).

## 5. Pass criteria (to be confirmed at v1.0; same spirit as Exp 4)
Dev: ≥ 150 trades; expectancy ≥ +0.10R after costs; positive in ≥ 3 of 4 years; beats ≥ 95% of C1 (random direction, same times/stops/targets); Deflated Sharpe ≥ 0.95 with ledger N; positive under 1.5× spread. Exam: expectancy ≥ +0.05R, positive in ≥ 8 of 12 years, beats ≥ 90% of C1, positive under 1.5× spread.
Optional pre-declared layer (decided at v1.0, counted in the ledger): a meta-labeling probability filter with ≤ 4 inputs — only if E7-0 shows ≥ 300 setups.

## Change Log
- v0.9 — 2026-10-08 — draft for E7-0 count only.
