# Gold Bot Experiment — Spec v1.1 (LOCKED)

Owner: Yash. Built by: Claude Code. Written: 2026-10-07.

**Locked means:** the rules, numbers, data periods and pass/fail criteria below must not change after any backtest result has been seen. If something looks wrong or impossible, STOP and ask Yash. Record any approved change in the Change Log at the bottom with the date and reason, and bump the version.

---

## 1. The question

Does adding an LLM filter (Claude) to a simple rule-based gold bot make it **less risky and more consistent** — not just more profitable — compared with the same bot without Claude?

Secondary question: does the simple rule bot have any real edge at all (vs. random entries)?

## 2. Arms

| Arm | What it is |
|---|---|
| **A** | Asian Range Breakout bot (rules only), news blackout ON |
| **B** | Same as A, plus Claude can VETO each A signal and can declare a NO-TRADE day each morning |
| **C1 — random entry** | Same days, same risk and exits as A, but random direction at a random M15 bar in the entry window. 200 seeds |
| **C2 — random veto** | A's trades, with the same *fraction* of trades Claude vetoed removed at random. 1,000 seeds |
| **Context** | Buy-and-hold gold, same period (for reference only) |

Run every arm on two entry timeframes: **M15** and **H1** (breakout candle timeframe). The Asian box is identical in both.

## 3. Account rules — FTMO 2-Step, $10,000, Standard account

| Rule | Value |
|---|---|
| Initial balance | $10,000 |
| Phase 1 profit target | 10% ($1,000) |
| Phase 2 profit target | 5% ($500) |
| Max daily loss | 5% ($500) — measured on **equity incl. floating P&L**, from the start-of-day balance; day resets 00:00 Europe/Prague |
| Max loss (static) | 10% ($1,000) — equity may never go below $9,000 |
| Min trading days | 4 |
| Trading period | Unlimited |
| Standard funded-stage restrictions | No new trades within ±2 min of high-impact news; positions closed before weekend |
| Position mode | FTMO US uses **netting** mode (one position per symbol). Bots A/B hold at most one gold position at a time, so this changes no rule. |

Simulate these rules on every backtest and report whether/when the account would have been breached.

## 4. Our own risk rules (tighter than FTMO)

- Risk per trade: **0.5% of initial balance = $50**
- Daily stop: stop opening trades for the day after **−1.5% ($150)** realised+floating
- Kill switch: stop the whole strategy if equity drops **6% ($600)** from its peak
- All trades closed same day (see §5). No overnight, no weekend holds.

## 5. Bot A — Asian Range Breakout (exact rules)

All times are **Europe/London local time** (handles UK daylight saving automatically). Convert from broker server time using §8.

1. **Box:** highest high and lowest low of all price bars from 00:00 to 07:00 London.
2. **Sanity skip:** skip the day if box height < 5 × the median spread during the box (stop too tight to be meaningful), or if box data has gaps > 30 min.
3. **Entry window:** 07:00 – 16:00 London.
4. **Signal:** first candle (M15 or H1, per variant) that **closes** above box high → LONG; first that closes below box low → SHORT. Max one trade per day (inherent to the strategy: one box, one breakout).
5. **Fill:** at the **open of the next candle**, paying the spread (buy at ask, sell at bid) + commission.
6. **Stop-loss:** opposite edge of the box.
7. **Take-profit:** 1.5 × stop distance (1.5R).
8. **Time exit:** close any open trade at 20:00 London.
9. **Size:** lots = floor_to_step( $50 / (stop distance in $ × contract size) ). Read contract size, volume step and minimum volume from the broker's `symbol_info`. If size < minimum volume → skip trade.
10. **News blackout (applies to A and B equally):** no new entry from 30 min before to 30 min after any **USD high-impact** scheduled event. Open trades keep their stop/target. Count and report any exit that happens within ±2 min of such an event ("FTMO-flagged").
11. **Same-bar rule:** if one candle touches both stop and target, use M1 data to see which came first; if M1 isn't available for that bar, assume the **stop** hit first.

No other filters in v1. No parameter optimisation.

## 6. Bot B — Claude filter

B = A's exact signals + two kinds of Claude calls:

- **Morning call (07:00 London, every trading day):** "Is today a NO-TRADE day?" → `TRADE_DAY` or `NO_TRADE_DAY`.
- **Signal call (each time A produces a signal, after A's own filters pass):** → `TAKE` or `VETO`.

Claude **cannot** create trades, change direction, size, stop or target. It only removes.

### 6.1 What Claude is given (and nothing else)
- Recent price action **anonymised**: last 48 H1 candles + today's M15 candles, expressed relative to the box (`(price − box_mid) / box_height`), plus ATR in the same units. **No dates, no years, no symbol name, no absolute prices.** Day of week is allowed.
- The signal: direction, stop and target in R.
- Scheduled events for the next 6 hours: name, impact, minutes until. **Never actual values for future events.**
- Events already released earlier today: name, actual vs forecast.
- News headlines from the last 12 hours, only those whose **first-seen time ≤ decision time − 15 min**, with times shown as "3h ago" (no dates).

### 6.2 Output (strict JSON schema)
```json
{"decision": "TAKE|VETO", "confidence": 0.0, "reason": "≤40 words"}
```
Morning call uses `"decision": "TRADE_DAY|NO_TRADE_DAY"`.

### 6.3 Prompt
Draft both prompts in `prompts/veto_v1.md` and `prompts/morning_v1.md`. Core instruction: *"You are a risk manager for a small gold breakout strategy. Your only job is to protect the account. VETO only when the supplied news, events or price behaviour give a specific reason this trade is unusually risky. If there is no specific reason, answer TAKE."* **Yash must approve the prompts before any B run. After approval they are locked.**

### 6.4 How Claude is called
- Use the Claude Code CLI in print mode with the Pro subscription login: `claude -p ... --output-format json --json-schema <schema> --model <PINNED_MODEL>`. Do **not** use `--bare` (it requires an API key, not the subscription).
- Run each call from an **empty sandbox folder** outside the project (so no CLAUDE.md, data or code is visible) and **disable all tools** (no web search, no file reading, no shell), e.g. `--disallowedTools` for WebSearch, WebFetch, Read, Bash, Edit, Write. Verify flag names with `claude --help`.
- **Isolation test before any B run:** send a prompt asking Claude to search the web and to read a file; both must fail.
- **Pin one model** for the whole experiment and log it. B's data window must start **after that model's training cutoff**. If the pinned model's cutoff is later than June 2026, STOP and tell Yash.
- Cache every response keyed by a hash of the exact input. Log tokens/cost from the JSON output.
- **Failure rule:** if a call errors or times out (60 s), default to `TAKE` / `TRADE_DAY` and log it.
- **Consistency check:** re-ask a random 20% of calls; report the flip rate.

## 7. Data periods (LOCKED)

| Use | Period | Arms |
|---|---|---|
| Development (bug-fixing allowed) | 2022-01-01 → 2025-12-31 | A, C1 |
| Holdout (run ONCE, no changes after) | 2026-01-01 → 2026-09-30 | A, C1 |
| Claude window | 2026-07-01 → latest available | A, B, C1, C2 |

If the broker's history doesn't reach 2022, use the earliest available and report it.

## 8. Data

**Price:** MetaTrader5 Python package from Yash's MT5 terminal. Gold symbol name varies by broker (`XAUUSD`, `XAUUSD.`, `GOLD`…): detect it.
- Pull M1 (as far back as available), M15 and H1, including the `spread` column. Save to `data/raw/` as Parquet with a metadata file (symbol, broker, server, contract size, volume step, min volume, pull timestamp).
- **Broker server time:** MT5 timestamps are server time with no timezone. Determine the offset (usually UTC+2 winter / UTC+3 summer) and verify it: plot average absolute M1 return around US NFP release times (08:30 New York) on at least 4 summer and 4 winter dates; the spike must line up after conversion. Store all data internally in UTC.
- **Costs:** spread from data; commission = **% of notional, charged per side** (on entry and again on exit), where notional = lots × contract size × fill price. Base case **0.0007% per side** (observed on Yash's FTMO trial account); stress case **0.0025% per side** (FTMO US published rate). Values in `config/settings.yaml`. Swap = 0 (no overnight).

**Economic calendar (USD, high impact):**
- 2022 → Apr 2025: the public Forex Factory calendar dataset on Hugging Face (2007–2025).
- After Apr 2025: official release schedules (Fed FOMC calendar, BLS for CPI/NFP, BEA for GDP/PCE). Respect each site's terms; no aggressive scraping.
- Store event time in UTC, plus impact and, for released events, actual/forecast.

**Headlines (only needed for B):** GDELT 2.0 DOC API (free, no key). **Urgent:** the DOC API only searches roughly the last ~3 months, so pull and save everything from 2026-07-01 onward **first**, before it ages out. Queries: gold, Federal Reserve, US dollar, inflation, geopolitical conflict. Save the raw JSON with GDELT's first-seen timestamp. Use the first-seen time as the "available at" time.

## 9. Leak prevention (must pass before results count)

1. **Event loop:** at each bar close the strategy receives only data up to and including that bar.
2. **Future-scramble test:** randomly scramble all data after time T; every decision at or before T must be identical. Run for 20 random T values. Any difference = leak = stop.
3. Fills at next-bar open with spread; same-bar rule as in §5.11.
4. Claude inputs anonymised (§6.1) and built only from data available at decision time.
5. Every decision logged with the timestamp of the newest data it saw.
6. Yash hand-checks 10 random trades from `trades.csv` against his MT5 chart.

## 10. Metrics (per arm, per timeframe)

Trades; win rate; average R; expectancy in $; net profit; **monthly P&L table**; % months profitable; average monthly $; worst month; worst day; max drawdown ($ and %); longest losing streak; FTMO breach (yes/no/when); number of FTMO-flagged exits; cost stress at 1.5× spread; cost stress at 0.0025% commission per side.

**Robustness nudge (A only, report — do not select):** box end 06:30 / 07:30; take-profit 1.3R / 1.7R. Flag any variant where profit collapses.

**Controls:** A's percentile vs the 200 C1 runs. B's drawdown and worst month vs the 1,000 C2 runs.

## 11. Pass / fail (LOCKED)

**A strategy passes overall if ALL of:**
- Average net profit **≥ $100 per month** on $10k
- **≥ 4 of every 6 months** profitable (≥ 67% of months)
- Never breaches FTMO max daily loss (5%) or max loss (10%)
- Beats ≥ 90% of random-entry (C1) runs on net profit

**B is "better than A" only if ALL of:**
- Lower max drawdown AND better worst month than A (same window)
- Beats ≥ 90% of random-veto (C2) runs on both drawdown and worst month
- Still passes the overall rule
- Consistency check flip rate < 20%

**Cost cases:** report every pass/fail verdict above under the base case, under the 1.5× spread stress, and under the 0.0025% commission stress.

Because the Claude window is only ~3 months, a B pass is **provisional** until confirmed by a 4–6 week demo forward test.

## 12. Build phases — stop for Yash's review after each

1. **Setup:** project skeleton, `requirements.txt`, config, tests folder. Confirm MT5 connection and print symbol info.
2. **Data:** pull price data, server-time verification plot, calendar, GDELT headlines (Jul 2026 → now first). Report coverage.
3. **Backtester + Bot A + C1** on the development period. Future-scramble test. Export 10 trades for hand-checking.
4. **Holdout run** of A + C1 (once).
5. **Claude filter:** prompts for approval → isolation test → B + C2 on the Claude window.
6. **Report:** `results/report.md` with all metrics, equity curves, monthly tables, pass/fail verdicts.

## 13. Project layout

```
gold-experiment/
  CLAUDE.md
  docs/EXPERIMENT_SPEC.md
  config/settings.yaml
  prompts/                # veto_v1.md, morning_v1.md (locked after approval)
  data/raw/  data/processed/   # git-ignored
  src/  data_mt5.py  timeutils.py  calendar_events.py  headlines.py
        strategy_asian.py  backtest.py  ftmo_rules.py  claude_filter.py
        controls.py  metrics.py  report.py
  tests/
  results/
```

Python 3.11+, pandas, MetaTrader5, pyarrow, pyyaml, requests, matplotlib, pytest.

## 14. Later (not in this spec)
Bot #2: box rule (previous-day high/low wick rejection). Demo forward test of the winner.

## Change Log
- v1.0 — 2026-10-07 — initial lock.
- v1.1 — 2026-10-07 — commission changed from flat per-lot to % of notional per side (base 0.0007% observed on the FTMO trial; stress 0.0025% per FTMO US published rate). Also noted that FTMO US uses netting mode (one position per symbol). Approved by Yash before any backtest result was seen.
