# Gold Bot Experiment — Spec v1.6 (LOCKED)

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
| **C1 — random entry** | Same days as A's trades (per timeframe), same risk and exits as A, but random direction at a random M15 bar in the entry window (outside news blackouts). Stop distance = A's stop distance that day. 200 seeds |
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
- Kill switch: stop the whole strategy if equity drops **6% ($600)** from its peak. **From v1.4:** in backtests the official verdict also reports an information-only run without it; in live/forward trading it means **pause and review** (Yash decides whether to resume), not a permanent stop. FTMO limits (§3) remain the breach rules.
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
10. **News blackout (applies to A and B equally):** no new entry from 30 min before to 30 min after any **USD high-impact** scheduled event. Open trades keep their stop/target. Count and report any exit that happens within ±2 min of such an event ("FTMO-flagged"). If the day's first breakout falls inside a blackout, there is no trade that day (the strategy does not wait for a later breakout).
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
- Events already released earlier today: name and minutes since release only (no actual or forecast values).
- News headlines from the last 12 hours, only those whose **first-seen time ≤ decision time − 15 min**, with times shown as "3h ago" (no dates). Headlines matched only by the "gold" topic are passed only if the title also contains one of: price, prices, ounce, bullion, futures, XAU, rally, falls, drops, rises, record. Headlines from the other topics pass unchanged. The raw data keeps everything.

### 6.2 Output (strict JSON schema)
```json
{"decision": "TAKE|VETO", "confidence": 0.0, "reason": "≤40 words"}
```
Morning call uses `"decision": "TRADE_DAY|NO_TRADE_DAY"`.

### 6.3 Prompt
Draft both prompts in `prompts/veto_v1.md` and `prompts/morning_v1.md`. Core instruction: *"You are a risk manager for a small gold breakout strategy. Your only job is to protect the account. VETO only when the supplied news, events or price behaviour give a specific reason this trade is unusually risky. If there is no specific reason, answer TAKE."* Both prompts also tell Claude to ignore headlines that are not about gold markets, the US economy or geopolitical risk. **Yash must approve the prompts before any B run. After approval they are locked.**

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
| Claude window | 2026-07-01 → latest available | best bot (A or A + filter), B, C1, C2 |
| Filter discovery (Phase 4b, information only) | 2022-01-01 → 2025-12-31 | A, tagged by candidate filters |
| Filter confirmation (Phase 4c, run ONCE) | 2010-01-01 → 2021-12-31 | A and A + adopted filter(s), C1 |

**2010–2021 is reserved:** no code, report or person looks at results from this period until Phase 4c. Spreads there use the same 2026 estimate (§8), which overstates costs because gold was cheaper — a harsher test, not an easier one.

If the broker's history doesn't reach 2022, use the earliest available and report it.

## 8. Data

**Price:** MetaTrader5 Python package from Yash's MT5 terminal. Gold symbol name varies by broker (`XAUUSD`, `XAUUSD.`, `GOLD`…): detect it.
- Pull M1 (as far back as available), M15 and H1, including the `spread` column. Save to `data/raw/` as Parquet with a metadata file (symbol, broker, server, contract size, volume step, min volume, pull timestamp).
- **Broker server time:** MT5 timestamps are server time with no timezone. Determine the offset (usually UTC+2 winter / UTC+3 summer) and verify it: plot average absolute M1 return around US NFP release times (08:30 New York) on at least 4 summer and 4 winter dates; the spike must line up after conversion. Store all data internally in UTC.
- **Spread:** from the data where the broker recorded it (from 2025-12-17). Before that, and on any bar with spread 0, use the **75th-percentile real spread for the same London hour, measured on 2026 data**, flagged as *estimated* on every bar and in every report. The 1.5× spread stress applies on top.
- **Costs:** spread as above; commission = **% of notional, charged per side** (on entry and again on exit), where notional = lots × contract size × fill price. Base case **0.0007% per side** (observed on Yash's FTMO trial account); stress case **0.0025% per side** (FTMO US published rate). Values in `config/settings.yaml`. Swap = 0 (no overnight).

**Economic calendar (USD, high impact) — one fixed event list for the whole period:**
- Events: FOMC decision (14:00 NY) + press conference (14:30), FOMC minutes (14:00), NFP, CPI, PPI, PCE, GDP, retail sales (08:30 NY), ISM manufacturing, ISM services (10:00 NY).
- Sources: Fed FOMC calendar page; FRED API release dates for NFP/CPI/PPI/PCE/GDP/retail sales (revision-only days removed); ISM rule-based — manufacturing 1st business day, services 3rd business day (one business day later in January, as observed 2022–2025). BEA's schedule overrides the 08:30 time where it publishes another. Respect each site's terms; no aggressive scraping.
- The Forex Factory dataset (Hugging Face) is used only to cross-check dates/times for 2022 → Apr 2025.
- Store event time in UTC.

**Headlines (only needed for B):** primary source = GDELT 2.0 raw 15-minute GKG files (data.gdeltproject.org, kept permanently). Keep English-source articles whose **page title** matches a topic: gold, "Federal Reserve", "US dollar", inflation, "geopolitical conflict" (multi-word topics as exact phrases). "Available at" time = the GKG file's 15-minute timestamp (GDELT first-seen). Backup: GDELT 2.0 DOC API (English sources, same queries, ≥ 6 s between requests). Save raw records.

## 9. Leak prevention (must pass before results count)

1. **Event loop:** at each bar close the strategy receives only data up to and including that bar.
2. **Future-scramble test:** randomly scramble all data after time T; every decision at or before T must be identical. Run for 20 random T values. Any difference = leak = stop.
3. Fills at next-bar open with spread; same-bar rule as in §5.11.
4. Claude inputs anonymised (§6.1) and built only from data available at decision time.
5. Every decision logged with the timestamp of the newest data it saw.
6. Yash hand-checks 10 random trades from `trades.csv` against his MT5 chart.

## 10. Metrics (per arm, per timeframe)

Trades; win rate; average R; expectancy in $; net profit; **monthly P&L table**; % months profitable; average monthly $; worst month; worst day; max drawdown ($ and %); longest losing streak; FTMO breach (yes/no/when); number of FTMO-flagged exits; cost stress at 1.5× spread (applied to fills only; the §5.2 skip filter keeps base spread); cost stress at 0.0025% commission per side.

**Robustness nudge (A only, report — do not select):** box end 06:30 / 07:30; take-profit 1.3R / 1.7R. Flag any variant where profit collapses.

**Controls:** A's percentile vs the 200 C1 runs. B's drawdown and worst month vs the 1,000 C2 runs.

## 11. Pass / fail (LOCKED)

**A strategy passes overall if ALL of:**
- Average net profit **≥ $100 per month** on $10k
- **≥ 4 of every 6 months** profitable: every rolling 6-month window must contain at least 4 profitable months
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
4. **Holdout run** of A + C1 (once). ✅ Done — FAIL (income below $100/month), see Change Log.
4b. **Filter discovery (information only, 2022–2025, kill switch off).** Tag every A trade with: year/quarter, long/short, box width vs the median box width of the prior 20 days, breakout direction vs the daily trend (close above/below the 20-day average of daily closes at box time), and FOMC/CPI/NFP day yes/no. Report expectancy and P&L per tag per year, plus the 2026 long/short split. Candidate filters, fixed in advance: **narrow box only**, **with-trend only**, **skip FOMC/CPI/NFP days**. A filter counts as helpful only if it improves expectancy in **≥ 3 of the 4 years**, using a median split, with no threshold search. Adopt at most two; Yash decides. 2026 results may not be used to choose filters.
4c. **Filter confirmation (run ONCE, 2010–2021).** A and A + adopted filter(s), plus C1, under all three cost cases. If the filter doesn't improve expectancy there, it is rejected. Also report A + filter on the 2026 holdout period next to the Phase 4 numbers, labelled **information only** (2026 has already been seen, so it can't confirm or reject a filter).
5. **Claude filter:** prompts for approval → isolation test → B + C2 on the Claude window, built on the best bot from 4c (A, or A + filter if confirmed).
6. **Forward demo test, 8–12 weeks:** the best bot runs live on the FTMO trial account, with Claude in shadow mode (logs TAKE/VETO on every signal from live news, never changes a trade). Afterwards compare: were vetoed trades losers more often than chance?
7. **Final report and decision:** `results/report.md` with all metrics, equity curves, monthly tables and verdicts; Yash decides on the FTMO challenge.

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
Bot #2: box rule (previous-day high/low wick rejection), tested with the same process.

## Change Log
- v1.0 — 2026-10-07 — initial lock.
- v1.1 — 2026-10-07 — commission changed from flat per-lot to % of notional per side (base 0.0007% observed on the FTMO trial; stress 0.0025% per FTMO US published rate). Also noted that FTMO US uses netting mode (one position per symbol). Approved by Yash before any backtest result was seen.
- v1.2 — 2026-10-08 — (1) Spread: broker has no spread data before 2025-12-17; those bars use the 75th-percentile 2026 real spread per London hour, labelled estimated; 1.5× stress kept. (2) Calendar: one fixed USD event list for the whole period (FOMC decision + presser, minutes, NFP, CPI, PPI, PCE, GDP, retail sales, ISM manufacturing/services) from the Fed site, FRED release dates and an ISM business-day rule, because BLS blocks scripted access and the Forex Factory set ends Apr 2025 with timezone and missing-time faults. (3) Headlines: GDELT raw GKG files become the primary source (title match, English) because the DOC API returned HTTP 429 to every request; DOC API kept as backup. Approved by Yash before any backtest result was seen.
- v1.3 — 2026-10-08 — Phase 5 inputs locked before any results: (1) Claude only receives "gold"-topic headlines whose title also contains price, prices, ounce, bullion, futures, XAU, rally, falls, drops, rises or record (raw data kept in full); prompts tell Claude to ignore off-topic headlines. (2) "Actual vs forecast" dropped from §6.1 (official sources publish no forecasts); Claude gets event name and minutes since release. Approved by Yash before any backtest result was seen. Clarifications confirmed by Yash before Phase 3: blackout on the first breakout = no trade that day; C1 trades A's trade days with A's stop distance; 1.5× spread stress applies to fills only; the months rule is judged on every rolling 6-month window.
- 2026-10-08 — **HOLDOUT USED.** The 2026-01-01 → 2026-09-30 holdout was run once (Phase 4, driver commit 07f351d, Phase 3 engine unchanged, kill switch included). Official §11 verdict: FAIL for M15 and H1 under all three cost cases (average month below $100). No rule, parameter or code changes may follow from it. No version change: rules unchanged.
- v1.4 — 2026-10-08 — Plan extended after Phase 4, approved by Yash: (1) New Phase 4b (filter discovery on 2022–2025, information only, three candidate filters fixed in advance, adoption rule ≥ 3 of 4 years with median split) and Phase 4c (one-time confirmation on the previously unused 2010–2021 data). (2) Phase 5 runs on the best confirmed bot. (3) New Phase 6: 8–12 week forward demo test with Claude in shadow mode; final report becomes Phase 7. (4) Kill switch: live/forward meaning changed to pause and review; backtests also report an information-only run without it. Reason: Bot A showed a small edge over random entries but failed on income; the extension tests whether simple, pre-chosen rule filters fix that, using data nobody has seen (2010–2021) as the honest check. The holdout result was not used to choose filters.
- v1.5 — 2026-10-08 — Pre-registered before Phase 4c, approved by Yash. (1) Adopted filter: **with-trend only**, for both M15 and H1 (the only Phase 4b candidate passing the ≥ 3-of-4-years rule); no risk or sizing changes. (2) Decision rule: "After 4c, the Asian breakout continues (to a sizing decision, then Phase 5) only if A + with-trend shows ≥ +0.10R expectancy per trade after base costs over 2010–2021 AND is profitable in ≥ 8 of the 12 years. Otherwise it is retired and bot #2 (box rule) starts through the same pipeline." Clarifications: the rule is judged on the 2010–2021 run **with the kill switch off** (official §11 verdicts with it on are reported alongside); expectancy in R after costs = mean of (net P&L ÷ the trade's initial risk in $, i.e. stop distance × lots × contract size); a profitable year = net P&L > 0 at base costs; on days without 20 completed daily closes (early January 2010) A + with-trend does not trade. The rule is checked per timeframe: a timeframe that meets it continues, one that fails is dropped; if both fail, the breakout is retired.
- v1.6 — 2026-10-08 — Approved by Yash. (1) Phase 5 runs now, before Phase 4c, on **plain Bot A** (no trend filter: it was not confirmed and was worse on 2026); Phase 4c stays pending (`results/next_steps.md`). (2) Prompts `prompts/veto_v1.md` and `prompts/morning_v1.md` approved and **locked** (SHA-256 of content with LF line endings: morning e0b1190373b6a716bc99e9a81303bcfba9583c27b726244661d9ffc83c3fc1c0, veto 559615df6fc3dde4b8bc1e2d4a2c3bfa4e3ac836d76e9d28038c2a3825a12d59); `src/claude_filter.py` refuses to run if either changes.
