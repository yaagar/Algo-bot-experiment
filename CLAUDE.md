# Gold Bot Experiment — instructions for Claude Code

- **Active spec: `docs/EXPERIMENT_4_SPEC.md`** (v1.0, locked 2026-10-08; source of truth; §refs mean this spec). Read the section you need. Exp 3 spec is finished (see LESSONS).
- **`docs/LESSONS.md`**: Exp 1–3 conclusions, rules still in force, archive pointers. Code map: `docs/CODE_GUIDE.md`.
- 2010–2021 is reserved: only via `src/data_access.py`, which refuses it without Yash's dated confirmation.

## Core modules (src/)
- Data: `data_access` (data lock), `data_mt5` (read-only MT5), `pull_prices`, `process_prices`, `spread_model`, `timeutils`, `verify_server_time`, `calendar_events`
- Engine/rules: `config`, `pnl`, `ftmo_rules`, `metrics`, `leak_test`, `controls`, `backtest`, `strategy_asian`
- `exp2/`: engine, market, strategies (S3 reused by Exp 3), c1, combo, regime, runners
- `exp3/`: markets, pull_data, fx_splice, data, evaluate, sanity, runners
- `exp4/`: Experiment 4 (signals, gates, combiner, config-driven runner) — being built

## Ground rules
- Spec is locked: never change a rule, number, period or pass/fail criterion. If something seems wrong, stop and ask Yash.
- No optimisation; no look-ahead (keep the scramble/leak tests passing).
- Work in phases; at each phase end give Yash a short summary: built, checked, what he must decide.
- Explain for Yash: plain-English behaviour first, logic second, non-obvious choices third. Simple, well-named code.
- Never place trades (no `order_send`). Never put credentials in code or git. `data/` stays out of git.

## Working rules (token budget)
- Don't read `archive/`, `data/`, `.venv/`, or results CSV/parquet files unless a task needs a specific one.
- Use targeted reads (line ranges) and Grep instead of reading whole files.
- Make small edits instead of rewriting whole files.
- Run tests with `.venv/Scripts/python -m pytest -q`; truncate long command output (`| tail -n 20`).
- Never print whole DataFrames: use `.head()`, `.shape`, or summaries.
- Don't leave scratch scripts in the repo; use the session scratchpad.
- Future experiments reuse one config-driven runner, not a new runner script per phase.
- Keep reports short, tables over prose.

## Environment
- Windows, VS Code, Python in `.venv`. MT5 terminal must be running and logged in for data pulls.
