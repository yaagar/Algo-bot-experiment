# Gold Bot Experiment — instructions for Claude Code

Two specs. Read the active one before doing anything; it is the source of truth.

- **Active: `docs/EXPERIMENT_2_SPEC.md`** — Experiment 2, strategy comparison (S1–S5 and combination). Its phases (E2-1 … E2-5) are the current work.
- **Finished: `docs/EXPERIMENT_SPEC.md`** — Experiment 1 (Asian breakout + Claude filter). Everything Experiment 2 doesn't restate (data pipeline, clock conversion, costs, FTMO simulation, news calendar, leak tests, data lock) is inherited from it unchanged. Its pending Phase 4c is folded into the single future 2010–2021 run.
- 2010–2021 is reserved: data goes only through `src/data_access.py`, which refuses it without Yash's dated confirmation.

Section references below (§10, §12) refer to whichever spec is active.

## Ground rules
- **The spec is locked.** Never change a rule, number, data period or pass/fail criterion. If something seems wrong, missing or impossible, stop and ask Yash. Never "fix" a result by changing rules.
- **No optimisation.** Do not tune parameters to improve results. Robustness nudges in spec §10 are reported, never selected.
- **No look-ahead.** Every decision may only use data available at that moment. Keep the future-scramble test passing at all times.
- **Work in phases** (spec §12). At the end of each phase, stop and give Yash a short summary: what was built, what was checked, what he needs to do or decide next.
- **Explain for Yash:** plain-English behaviour first, logic second, non-obvious choices third. No file-by-file changelogs. He reads Python but is not a full-time coder, so keep code simple and well-named over clever.
- **Never place trades.** This project only reads market data from MT5. Do not call `order_send` or any trading function.
- **Never put credentials in code or git.** MT5 login comes from the already-logged-in terminal.
- Data files (`data/`) stay out of git.

## Claude filter calls (Bot B)
- Only via `src/claude_filter.py`, following spec §6.4 exactly: empty sandbox folder, all tools disabled, pinned model, JSON schema, caching, default-to-TAKE on failure.
- Prompts in `prompts/` are locked once Yash approves them.

## Environment
- Windows, VS Code, Python 3.11+ in a `.venv`.
- MT5 terminal must be running and logged in for data pulls.
