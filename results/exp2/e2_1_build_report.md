# Phase E2-1 — build and verify (no performance numbers)

Data: 2022-01-01 → 2026-01-01 (UTC), through `src/data_access.py`; nothing before 2022-01-01 loaded. Indicators start from the first 2022 bar.

## What each strategy did (counts only)

| Strategy | Trades | Signals skipped while in a trade | Blocked at entry (reason: count) | Exits by reason | Held across a >2 h break | Overnight rollovers held |
|---|---:|---:|---|---|---:|---:|
| S1 H1 | 877 | 0 | {'news blackout': 48, 'after Friday 16:00 London': 7} | {'time': 450, 'stop': 275, 'target': 150, 'friday close (market closed early)': 2} | 19 | 23 |
| S1 M15 | 932 | 0 | {'news blackout': 33} | {'time': 418, 'stop': 336, 'target': 176, 'friday close (market closed early)': 2} | 20 | 24 |
| S2 | 142 | 0 | {'news blackout': 23, 'after Friday 16:00 London': 4} | {'stop': 77, 'target': 49, 'time': 16} | 1 | 1 |
| S3 | 243 | 465 | {'after Friday 16:00 London': 16, 'news blackout': 18} | {'friday close': 97, 'stop': 91, 'exit signal': 47, 'friday close (market closed early)': 7, 'end of data': 1} | 13 | 629 |
| S4 | 621 | 428 | {'news blackout': 56, 'after Friday 16:00 London': 13} | {'exit signal': 370, 'stop': 182, 'time': 68, 'friday close (market closed early)': 1} | 4 | 3 |
| S5 | 1022 | 0 | {'no price within 60 min of entry time': 20} | {'time': 824, 'stop': 198} | 1 | 0 |

## S1 re-wire check against Experiment 1

- **S1 H1:** 832 of 838 Experiment 1 trades found at the same entry time (the 6 not found are Friday entries at 16:00 London, which Experiment 2's weekend rule forbids; Experiment 1 had 6 such trades); 814 identical in direction, stop, target, exit reason and exit price. The other 18 are all holiday early closes (18 confirmed): Experiment 1 exited at the last price before the halt, Experiment 2 holds to the reopen and flags the trade (spec §3). S1 now has 877 trades: the extra 45 are signals Experiment 1 skipped because the size was below 0.01 lots (fractional sizing trades every signal, spec §3).
- **S1 M15:** 891 of 891 Experiment 1 trades found at the same entry time (the 0 not found are Friday entries at 16:00 London, which Experiment 2's weekend rule forbids; Experiment 1 had 0 such trades); 873 identical in direction, stop, target, exit reason and exit price. The other 18 are all holiday early closes (18 confirmed): Experiment 1 exited at the last price before the halt, Experiment 2 holds to the reopen and flags the trade (spec §3). S1 now has 932 trades: the extra 41 are signals Experiment 1 skipped because the size was below 0.01 lots (fractional sizing trades every signal, spec §3).

## Future-scramble test (20 random cut times, all data after the cut shuffled)

| Strategy | Cuts with every decision before the cut identical | Decisions changed after the cut (min / median) |
|---|---:|---|
| S1 H1 | **20 / 20** | 229 / 2702 |
| S1 M15 | **20 / 20** | 245 / 2941 |
| S2 | **20 / 20** | 24 / 262 |
| S3 | **20 / 20** | 43 / 639 |
| S4 | **20 / 20** | 118 / 1320 |
| S5 | **20 / 20** | 194 / 2296 |

Every decision is also checked to be logged with data no newer than its decision time.

## C1 (random direction) smoke test — one seed per strategy, no results reported

- S1 H1: 877 C1 trades for 877 real; same entry times: True; same stop distance: True; 125 stopped out earlier than the real exit; 0 exited later (only where no M1 bar exists at the real exit minute — a data gap — so C1 takes the next available price).
- S1 M15: 932 C1 trades for 932 real; same entry times: True; same stop distance: True; 166 stopped out earlier than the real exit; 0 exited later (only where no M1 bar exists at the real exit minute — a data gap — so C1 takes the next available price).
- S2: 142 C1 trades for 142 real; same entry times: True; same stop distance: True; 33 stopped out earlier than the real exit; 0 exited later (only where no M1 bar exists at the real exit minute — a data gap — so C1 takes the next available price).
- S3: 243 C1 trades for 243 real; same entry times: True; same stop distance: True; 44 stopped out earlier than the real exit; 1 exited later (only where no M1 bar exists at the real exit minute — a data gap — so C1 takes the next available price).
- S4: 621 C1 trades for 621 real; same entry times: True; same stop distance: True; 34 stopped out earlier than the real exit; 1 exited later (only where no M1 bar exists at the real exit minute — a data gap — so C1 takes the next available price).
- S5: 1022 C1 trades for 1022 real; same entry times: True; same stop distance: True; 103 stopped out earlier than the real exit; 0 exited later (only where no M1 bar exists at the real exit minute — a data gap — so C1 takes the next available price).

## Monthly regime labels (market description, 2022–2025)

Median efficiency 0.174. Months per regime: {'trending up': 17, 'ranging up': 13, 'ranging down': 11, 'trending down': 7}. File: `regime_months.csv`.

## Hand-check file

`handcheck_5_trades_per_strategy.csv`: 5 random trades each for S2–S5 with UTC and MT5 server times, levels, entry, stop, target and exit. No P&L. MT5 charts show BID prices: long entries pay bid + spread; shorts exit at ask = bid + spread.
