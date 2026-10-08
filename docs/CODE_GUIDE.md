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
| `data/raw/`, `data/processed/` | Downloaded prices etc. Not in git. *(empty until Phase 2)* |
| `prompts/` | Claude prompts for Bot B *(Phase 5)* |
| `results/` | Backtest output and final report *(Phase 3+)* |

## How to run

```
.venv\Scripts\python -m src.check_mt5     # check MT5 connection + gold symbol
.venv\Scripts\python -m pytest            # run all tests
```
MT5 (OANDA MetaTrader 5, logged in to the FTMO trial) must be open first.

## What each code file does

**`src/config.py`** — reads `settings.yaml`. Also holds `commission_usd()`:
commission = lots × 100 oz × price × 0.0007%, paid on entry and again on exit.

**`src/data_mt5.py`** — the only file that talks to MT5. Read-only.
- `connect()` attaches to the already-open terminal (no passwords in code).
- `pick_gold_symbol()` finds gold among the broker's symbols (here: `XAUUSD.sim`).
- `symbol_specs()` returns contract size, lot step, min lot, etc.
- `server_time_estimate()` compares the latest price's timestamp with real UTC
  to guess the broker's clock offset (currently UTC+3).

**`src/check_mt5.py`** — Phase 1 check. Connects, picks gold, prints the above.

**`tests/test_phase1.py`** — checks gold detection, that config numbers match the
spec, that the commission formula reproduces your real FTMO trial fills, and that
no trading function (`order_send` …) ever appears in `src/`.

## Flow so far

```
settings.yaml ──> check_mt5 ──> data_mt5.connect ──> MT5 terminal (read-only)
                                 └─ pick gold ─ print specs ─ print server time
```

## Coming next (Phase 2)
Download M1/M15/H1 gold prices, verify the server clock against NFP releases,
load the economic calendar and news headlines.
