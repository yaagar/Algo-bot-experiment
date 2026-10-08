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
.venv\Scripts\python -m src.verify_server_time  # prove the server-clock rule (+ plot)
.venv\Scripts\python -m src.calendar_events     # build the USD news calendar
.venv\Scripts\python -m src.headlines           # download GDELT headlines (slow, resumable)
.venv\Scripts\python -m src.check_pnl           # MT5: compare our P&L maths with real trades
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

**`verify_server_time.py`** — proves the clock rule two ways: the daily trading break
always ends at 18:00 New York, and the NFP price spike always lands on 08:30 New York.

**`calendar_events.py`** — builds the list of US high-impact news times. Uses the
Forex Factory file up to April 2025 (after fixing its timezone label and filling
missing times), then the Fed and BEA official schedules.

**`headlines.py`** — downloads news headlines from GDELT, oldest days first, one file
per topic per day, so it can stop and resume. Waits politely when GDELT says "too many requests".

**`pnl.py`** — profit/loss of a trade and its commission (used by the backtester later).
**`check_pnl.py`** — reads your closed demo trades and checks `pnl.py` gives the same numbers as the broker.

## Flow so far

```
MT5 ──pull_prices──> raw bars (server time) ──process_prices──> UTC bars
                                   timeutils (NY+7h) ┘   verified by verify_server_time
Forex Factory + Fed + BEA ──calendar_events──> calendar_usd_high.parquet (UTC)
GDELT ──headlines──> data/raw/gdelt/<topic>/<day>.json
```

## Coming next (Phase 3)
Backtester + Bot A + random-entry control (C1) on the development period.
