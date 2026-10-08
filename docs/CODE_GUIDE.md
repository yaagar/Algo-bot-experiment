# Code Guide (plain English)

Short map of what exists and what it does. Updated at the end of every phase.
The rules live in `docs/EXPERIMENT_SPEC.md` — this file only explains the code.

## Folders

| Folder | What's in it |
|---|---|
| `docs/` | The spec (the rules) and this guide |
| `config/settings.yaml` | Every number the code uses (account size, risk, times, costs). Copied from the spec. |
| `src/` | The Python code |
| `tests/` | Automatic checks (`pytest`) |
| `data/raw/` | Downloads exactly as received (prices in broker server time, calendar files, headlines). Not in git. |
| `data/processed/` | Cleaned data, all times in UTC. Not in git. |
| `prompts/` | Claude prompts for Bot B *(Phase 5)* |
| `results/` | Reports and plots (`results/phase2/data_report.md`) |

## How to run

MT5 (OANDA MetaTrader 5, logged in to the FTMO trial) must be open for anything that says *MT5*.

```
.venv\Scripts\python -m src.check_mt5           # MT5: connection + gold symbol info
.venv\Scripts\python -m src.pull_prices         # MT5: download all M1/M15/H1 bars
.venv\Scripts\python -m src.process_prices      # convert bars to UTC
.venv\Scripts\python -m src.spread_model        # fill estimated spreads (run after process_prices)
.venv\Scripts\python -m src.verify_server_time  # prove the server-clock rule (+ plot)
.venv\Scripts\python -m src.calendar_events     # build the USD news calendar (needs FRED key in .env)
.venv\Scripts\python -m src.headlines_gkg       # headlines from GDELT raw files (main source, ~1 h)
.venv\Scripts\python -m src.headlines           # headlines from GDELT DOC API (backup)
.venv\Scripts\python -m src.check_pnl           # MT5: compare our P&L maths with real trades
.venv\Scripts\python -m src.run_phase3          # Bot A + C1 + nudges + leak test, 2022-2025 (~5 min)
.venv\Scripts\python -m src.run_phase4          # ONE-TIME holdout run 2026-01..09 — already used, do not re-run
.venv\Scripts\python -m pytest                  # run all tests
```

## What each code file does

**`config.py`** — reads `settings.yaml`; `commission_usd()` = lots × 100 oz × price × 0.0007%, per fill.

**`data_mt5.py`** — the only file that talks to MT5, read-only. Connects, finds gold,
reads its specs, and `pull_rates()` downloads bars one month at a time.

**`timeutils.py`** — time conversions. The broker clock is **New York + 7 hours**
(UTC+3 in US summer, UTC+2 in US winter). `server_to_utc()` turns broker times into UTC.

**`pull_prices.py`** → `data/raw/XAUUSD.sim_{M1,M15,H1}.parquet` + metadata JSON.
**`process_prices.py`** → same bars with a `time_utc` column in `data/processed/`.

**`spread_model.py`** — the broker has no spread before Dec 2025. For those bars it uses the
75th-percentile 2026 spread for the same London hour, and marks the bar `spread_estimated`.

**`verify_server_time.py`** — proves the clock rule two ways: the daily trading break
always ends at 18:00 New York, and the NFP price spike always lands on 08:30 New York.

**`calendar_events.py`** — builds the fixed list of US news times for the whole period:
FOMC (Fed website), NFP/CPI/PPI/PCE/GDP/retail sales (FRED release dates, revision-only
days removed), ISM (business-day rule). Cross-checks everything against Forex Factory.
The FRED key is read from `.env` (never in code or git).

**`headlines_gkg.py`** — main headline source. Streams GDELT's 15-minute raw files, keeps
articles whose title mentions gold / Federal Reserve / US dollar / inflation / geopolitical
conflict, one file per day (resumable). The file's timestamp = when the headline became available.

**`headlines.py`** — backup: GDELT DOC API, one request per 6 s, backs off on "too many requests".

**`pnl.py`** — profit/loss of a trade and its commission (used by the backtester later).
**`check_pnl.py`** — reads your closed demo trades and checks `pnl.py` gives the same numbers as the broker.

**`strategy_asian.py`** — Bot A's rules. `compute_box()` builds the 00:00-07:00 London box from
M1 bars (or skips the day: data hole > 30 min, or box < 5x spread). `find_breakout()` checks
candles one by one and returns the first that closes outside the box.

**`backtest.py`** — the engine. Loads 2022-2025 only (refuses anything reaching the 2026 holdout),
splits data into London days, and walks forward day by day: box -> entry -> exit -> account.
`simulate_exit()` follows M1 bars after the fill: long stops/targets trigger on bid, short ones on
ask (bid + spread); if one bar hits both, stop wins; 20:00 London closes anything left.
Our kill switch (equity $600 below peak) stops the strategy for good. Every decision is logged
with the newest data it saw.

**`controls.py`** — C1: same days as A's trades, random direction at a random M15 bar,
A's stop distance, same exits. **`ftmo_rules.py`** — FTMO daily-loss / max-loss / profit targets.
**`metrics.py`** — spec §10 numbers and the §11 pass/fail checks.
**`leak_test.py`** — shuffles all data after a random time T and checks no decision before T changes.
**`run_phase3.py`** — runs it all and writes `results/phase3/`.
**`run_phase4.py`** — the one-time holdout run (same engine, 2026-01-01 → 2026-09-30); results in `results/phase4/`.
**`phase4_skip_reasons.py`** — read-only: re-runs the holdout unchanged and counts why days had no trade.
**`filters.py`** — Phase 4b tags for each trade: narrow box (below the prior-20-day median width),
daily trend (yesterday's broker close vs its 20-day average), FOMC/CPI/NFP day. History only, no look-ahead.
**`run_phase4b.py`** — tags every 2022-2025 Bot A trade and checks the three candidate filters
against the ≥ 3-of-4-years rule; results in `results/phase4b/`.

## Flow so far

```
MT5 ──pull_prices──> raw bars (server time) ──process_prices──> UTC bars ──spread_model──> + spread_used
                                   timeutils (NY+7h) ┘   verified by verify_server_time
Fed + FRED + ISM rule (+ BEA times) ──calendar_events──> calendar_usd_high.parquet (UTC)
GDELT raw GKG files ──headlines_gkg──> data/raw/gdelt_gkg/<day>.jsonl

UTC bars + calendar ──backtest (strategy_asian / controls)──> trades ──metrics + ftmo_rules──> results/phase3/
```

## Coming next (Phase 4c)
One-time confirmation on 2010–2021 of the filter(s) Yash adopts, plus C1, all three cost cases.
