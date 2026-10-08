# Code Guide (plain English)

Map of the code still in `src/`. Rules live in `docs/EXPERIMENT_3_SPEC.md`; lessons and archive pointers in `docs/LESSONS.md`.

## How to run
MT5 (logged in to the FTMO trial) must be open for anything marked *MT5*.
```
.venv\Scripts\python -m src.check_mt5            # MT5: connection + symbol info
.venv\Scripts\python -m src.pull_prices          # MT5: gold M1/M15/H1 bars (data lock applies)
.venv\Scripts\python -m src.process_prices       # bars -> UTC
.venv\Scripts\python -m src.spread_model         # estimated spreads before 2025-12-17
.venv\Scripts\python -m src.verify_server_time   # prove the NY+7h clock rule
.venv\Scripts\python -m src.calendar_events      # USD news calendar (FRED key in .env)
.venv\Scripts\python -m src.exp3.run_e3_2        # Exp 3 run and report
.venv\Scripts\python -m pytest -q
```

## Data and clock
| Module | What it does |
|---|---|
| `data_access.py` | The ONLY reader of price data. Pre-2022 refused without `--purpose` + dated `--confirm`; every use logged in `results/data_access_log.md`. `tests/test_data_lock.py` enforces it. |
| `data_mt5.py` | Only file that talks to MT5, read-only; `pull_rates()` downloads month by month. |
| `timeutils.py` | Broker clock = New York + 7 h. `server_to_utc()`. |
| `pull_prices.py` / `process_prices.py` | Raw gold bars (server time) -> `data/processed/` with `time_utc`. |
| `spread_model.py` | No broker spread before Dec 2025: uses the 75th-pct 2026 spread for the same London hour, flags `spread_estimated`. |
| `verify_server_time.py` | Checks the clock: daily break ends 18:00 NY; NFP spike lands 08:30 NY. |
| `calendar_events.py` | US news times: FOMC (Fed site), NFP/CPI/PPI/PCE/GDP/retail (FRED, revision-only days dropped), ISM (business-day rule); cross-checked vs Forex Factory. |
| `calendar_events.build_reserved()` | Same calendar for 2010-2021 from the Fed historical pages (per-meeting statement time, press-conference status), FRED and the ISM rule -> its own file `calendar_usd_high_2010_2021.parquet`. |
| `reserved_prep.py` | 2010-2021 data preparation only (needs `--purpose`/`--confirm`): `calendar`, `gold` and `symbols` integrity checks (bars, gaps, server clock per year), `download` (via `exp3/pull_data.pull_reserved`), `login`. Reports in `results/reserved_prep/`. |

## Engine and rules
| Module | What it does |
|---|---|
| `config.py` | Reads `config/settings.yaml`; `commission_usd()`. |
| `pnl.py` / `check_pnl.py` | Trade P&L and commission; check against real demo trades. |
| `ftmo_rules.py` | FTMO daily-loss / max-loss / targets. |
| `metrics.py` | Report numbers and pass/fail checks. |
| `leak_test.py` | Scrambles data after a random time T; no decision before T may change. |
| `backtest.py`, `strategy_asian.py`, `controls.py` | Exp 1 engine, Asian-box rule and C1 control; kept because the leak test, Exp 2 code and tests use them. |

## Experiment 2 (`src/exp2/`)
`market.py` loads bars via the data lock, builds H4/broker-day bars and causal ATR/RSI/SMA. `engine.py`: one position, decide at bar close, fill next open with spread, M1 stops (stop wins ties), forced exits, news blackout, swap per rollover. `strategies.py` S1–S5 (S3 = Donchian, reused by Exp 3). `c1.py` random-direction control. `combo.py` one-account combination. `regime.py` monthly regime labels. `run_e2_*.py` phase runners.

## Experiment 3 (`src/exp3/`)
| Module | What it does |
|---|---|
| `markets.py` | The 8 markets and base commission; symbols matched by name stem. |
| `pull_data.py` | MT5: D1/H1 bars from 2022 + cost table. |
| `fx_splice.py` | FX history before the broker's first full day from MetaQuotes-Demo (Change Log v1.1). |
| `data.py` | Loads one market, builds the Exp 2 engine on D1 bars. |
| `evaluate.py` | R statistics, C1, cost stresses, FTMO Swing simulation with real lots. |
| `sanity.py` | Independent recomputation of signals and trades (shares no code). |
| `run_e3_1.py` / `run_e3_2.py` | Build-and-verify; run and report -> `results/exp3/`. |
