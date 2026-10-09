# Code Guide (plain English)

Map of the code still in `src/`. Rules live in `docs/EXPERIMENT_4_SPEC.md`; lessons and archive pointers in `docs/LESSONS.md`.

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

## Experiment 4 (`src/exp4/`, numbers in `config/exp4.yaml`)
| Module | What it does |
|---|---|
| `pull_data.py` | MT5: US500 M1 from 2022 (spreads estimated as for gold). |
| `data.py` | Config + variants, market clocks/trading days, H1 (gold broker; US500 :30 from M1) and H4 bars. |
| `signals.py` | Signals A-D, σ scaling, regime and shock gates, forecast F per H1 bar. |
| `system.py` | Entry/exit/size rules on the Exp 2 engine (`E4Engine` adds forecast sizing, no fill after flat-by). |
| `rebuild.py` | Independent rebuild of signals, gates and F (no shared code); must match every bar. |
| `run.py` | The one runner: `python -m src.exp4.run e4_1` (later phases add steps here). |

## Experiment 6 (`src/exp6/`, numbers in `config/exp6.yaml`)
| Module | What it does |
|---|---|
| `pull_data.py` | MT5: symbol inventory, FTMO D1/H1 2022+, MetaQuotes FX 2022+, 2026 tick-spread table. |
| `costs.py` | Locked swap table and the §3 cost screen. |
| `data.py` | Universe for a period: H1 bars, broker-day closes, USD conversion, tick spreads per server hour. |
| `signals.py` | Trend signs 21/63/252, forecast, class-split sizing, portfolio scaler, buffer. |
| `engine.py` | Portfolio account: fills at 10:00 NY, swaps, netting, hourly FTMO checks (`ftmo_rules.PortfolioLimits`). |
| `c1.py` / `rebuild.py` | C1 random-sign forecasts; independent rebuild (no shared engine code). |
| `run.py` | The one runner: `screen`, `e6_1` (later phases add steps). |

## Experiment 7 (`src/exp7/`, numbers in `config/exp7.yaml`)
| Module | What it does |
|---|---|
| `spreads.py` | MT5 (read-only): 2026 gold tick-p75 spread as a fraction of price, per server hour. |
| `pattern.py` | Swings, H1 trend + t-stat, M15 box (gap-limited), messy rules, stop; `scan()` = every candidate breakout with block flags. |
| `system.py` | Setups traded on the Exp 2 engine via `E4Engine`: one position, $50 = 1R, 2R target, 20:00 London exit; `entry_view()` hides outcomes. |
| `controls.py` | C1 random direction at real times; C2 random trend-direction bars (same $ stop). |
| `meta.py` | M2 logistic regression (L2, C=1), yearly expanding walk-forward from 2021. |
| `rebuild.py` | Independent rebuild of setups, one-position rule, entries, stops, targets (no shared code). |
| `run.py` | The one runner: `e7_1` (later phases add steps). Data via standing grant `exp7`. |
