# Phase 6 — paper forward test: proposed design (not built)

Proposed 2026-10-08 for Yash's review. **No orders are ever placed.** The bot reads live prices, decides exactly as in the backtest, and writes down what it *would* have done. Claude runs in shadow mode: its decisions are logged but never change a paper trade.

## 1. What runs

- **Bot:** plain Bot A (spec v1.6), both **M15 and H1** in parallel. The bootstrap found no reliable difference between them, so the forward test can collect evidence on both at no extra cost.
- **Claude (shadow):** the morning call at 07:00 London and a veto call at every signal, using the same pinned model, locked prompts and `claude_filter.py` as Phase 5. About 2–3 calls per trading day.
- **Duration:** 8–12 weeks (40–60 trading days). At 2026 trade rates that's about 15–25 trades per timeframe. Section 6 explains why that's enough to check that live matches backtest, but not enough to prove an edge.

## 2. How it works (one loop, same code as the backtest)

1. **Live bars.** A Python process polls the already-open MT5 terminal every 5–10 s with read-only calls (`copy_rates_from_pos`, `symbol_info_tick`). When an M1/M15/H1 bar **closes**, it is stored and passed to the strategy. Only closed bars, exactly as in the backtest event loop (§9.1).
2. **Same decision code.** `compute_box`, `find_breakout`, the news blackout, $50 sizing with the minimum-lot skip, and the 20:00 time exit are imported from `src/`, not rewritten. A divergence between live and backtest then points at the data, not the logic.
3. **Paper fills.** The entry is recorded two ways:
   - the backtest's way: next bar's open plus the bar's spread;
   - the actual live bid/ask at that moment.

   The gap between the two is real-world slippage and spread, a key Phase 6 output. Stops and targets are tracked from live ticks (bid for longs, ask for shorts).
4. **Live news.**
   - **Calendar:** the fixed event list from §8 (FRED, Fed, ISM rule), refreshed weekly from the official schedules.
   - **Headlines:** GDELT's raw 15-minute files, polled as each new file appears, with the same filters as Phase 5.
   - Claude gets exactly the §6.1 inputs built from live data.
5. **Logging.** An append-only JSON-lines log records every decision: box, signal, blocked/skipped and why, paper entry, exit, Claude's call and reason. Each entry carries the timestamp of the newest data it saw (§9.5). Data stays out of git; a weekly summary goes in `results/phase6/`.

## 3. Daily reconciliation (catches live-vs-backtest drift)

Every evening after 20:00 London, the backtester re-runs the day from MT5's own stored bars and compares the result with the live log: same box, same signal, same entry time and direction, same exit. Any mismatch is flagged the same day. It means a data gap (PC asleep, MT5 disconnected) or a live-only bug.

## 4. Safety

- Read-only MT5 access. The existing test that fails if `order_send` / `order_check` appears in `src/` stays.
- No credentials in code. MT5 uses the already-logged-in terminal; Claude uses the Pro login.
- Kill switch = **pause and review** (spec v1.4): if paper equity falls $600 below its peak, the log and a desktop notification tell Yash, and paper trading pauses until he resumes it.
- The MT5 terminal is never restarted or closed by the bot. Restarts are Yash's call.

## 5. Practical requirements

- The PC must be on with MT5 open and logged in **00:00–20:00 London on weekdays**, or the test runs on a small Windows VPS. Missed days are logged as gaps, never filled in afterwards.
- About 2–3 Claude calls per day (≈20k tokens/day) on the Pro plan.

## 6. Evaluation at the end (to pre-register before starting)

1. **Live = backtest?** Share of days where live decisions match the evening reconciliation (target: 100% on days without data gaps).
2. **Costs:** average live spread and slippage per trade vs the backtest's assumption.
3. **Bot A results** vs the 2026 backtest range, reported but not judged as an edge test (too few trades).
4. **Claude shadow:** were the trades Claude would have vetoed losers more often than chance? Compare the vetoed trades' win rate and average R with the kept trades. Use a permutation test (shuffle which trades count as vetoed, 10,000 times), and report the p-value with an honest note on low power at ~20 trades.

## 7. Decisions for Yash before building

1. VPS or home PC?
2. Start date and length (8 or 12 weeks)?
3. Run both timeframes, or pick one?
4. The pre-registered success criteria for points 1–4 above.
5. Whether to track A + with-trend alongside (only if Phase 4c confirms it).
