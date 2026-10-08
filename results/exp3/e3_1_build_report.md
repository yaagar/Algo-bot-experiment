# Phase E3-1 — data and build (no performance numbers)

Broker: OANDA Corporation (OANDA-Demo-1), pulled 2026-10-08T18:23 UTC. Window 2022-01-01 → 2026-09-30, read through `src/data_access.py`; nothing before 2022 loaded.

## Market availability and history

| Market | Broker symbol | First daily bar (UTC) | Daily bars in window |
|---|---|---|---:|
| Gold | XAUUSD.sim | 2022-01-02 | 1224 |
| Silver | XAGUSD.sim | 2022-01-02 | 1225 |
| WTI crude oil | USOIL.sim | 2022-01-02 | 1222 |
| S&P 500 | US500.sim | 2022-01-02 | 1224 |
| Nasdaq 100 | US100.sim | 2022-01-02 | 1225 |
| EURUSD | EURUSD.sim | 2025-05-19 | 355 |
| USDJPY | USDJPY.sim | 2025-05-19 | 355 |
| AUDUSD | AUDUSD.sim | 2025-05-19 | 355 |
| Germany 40 | not offered | — | — |
| Japan 225 | not offered | — | — |

## Costs and swap (recorded from MT5 `symbol_info`)

Spread estimate = 75th percentile of real spread on the first H1 bar of each broker day (the daily-bar open). Used wherever the broker recorded 0. Swap = current values applied to all history (estimate).

| Symbol | Contract | Min lot / step | Commission per side | Open-hour spread p75 (price) | Real spreads from | Daily bars with estimated spread | Swap long / short (%/yr) | Triple swap |
|---|---:|---|---|---:|---|---:|---|---|
| XAUUSD.sim | 100 | 0.01 / 0.01 | 0.0007% of notional | 0.250 | 2025-12-17 | 83.3% | -5.66 / -3.02 | Wednesday (broker field 7 = invalid; provisional) |
| XAGUSD.sim | 5000 | 0.01 / 0.01 | 0.0007% of notional | 0.01700 | 2022-01-02 | 19.4% | -5.85 / 3.61 | Wednesday (broker field 7 = invalid; provisional) |
| USOIL.sim | 100 | 0.1 / 0.1 | 0.001% of notional | 0.060 | 2025-12-17 | 83.1% | -0.2 / -4.8 | Friday |
| US500.sim | 1 | 0.1 / 0.1 | $0 | 0.5 | 2025-12-17 | 83.0% | -5.97 / 0.97 | Wednesday (broker field 7 = invalid; provisional) |
| US100.sim | 1 | 0.1 / 0.1 | $0 | 1.8 | 2025-12-17 | 83.0% | -5.58 / 0.58 | Wednesday (broker field 7 = invalid; provisional) |
| EURUSD.sim | 100000 | 0.01 / 0.01 | $2.50/lot | 0.00009 | 2025-05-20 | 21.6% | -3.51 / 1.49 | Wednesday (broker field 7 = invalid; provisional) |
| USDJPY.sim | 100000 | 0.01 / 0.01 | $2.50/lot | 0.021 | 2025-05-20 | 10.8% | 3.19 / -5.2 | Wednesday (broker field 7 = invalid; provisional) |
| AUDUSD.sim | 100000 | 0.01 / 0.01 | $2.50/lot | 0.00011 | 2025-05-20 | 8.9% | -1.78 / -0.27 | Wednesday (broker field 7 = invalid; provisional) |

## Day boundary (broker D1 = H1 grouped by broker day, New York 17:00)

- XAUUSD.sim: 1224 / 1224 daily bars identical; weekend-dated bars: 0
- XAGUSD.sim: 1225 / 1225 daily bars identical; weekend-dated bars: 0
- USOIL.sim: 1222 / 1222 daily bars identical; weekend-dated bars: 0
- US500.sim: 1224 / 1224 daily bars identical; weekend-dated bars: 0
- US100.sim: 1225 / 1225 daily bars identical; weekend-dated bars: 0
- EURUSD.sim: 355 / 355 daily bars identical; weekend-dated bars: 0
- USDJPY.sim: 355 / 355 daily bars identical; weekend-dated bars: 0
- AUDUSD.sim: 355 / 355 daily bars identical; weekend-dated bars: 0

## Independent sanity check (src/exp3/sanity.py, no shared code)

| Symbol | Engine trades | Independent trades | Identical (entry, direction, exit, reason) | Engine signals agreeing | Worst stop difference | Pass |
|---|---:|---:|---:|---|---:|---|
| XAUUSD.sim | 17 | 17 | 17 | 17 / 17 | 0.00e+00 | yes |
| XAGUSD.sim | 19 | 19 | 19 | 19 / 19 | 0.00e+00 | yes |
| USOIL.sim | 18 | 18 | 18 | 18 / 18 | 0.00e+00 | yes |
| US500.sim | 18 | 18 | 18 | 18 / 18 | 0.00e+00 | yes |
| US100.sim | 19 | 19 | 19 | 19 / 19 | 0.00e+00 | yes |
| EURUSD.sim | 7 | 7 | 7 | 7 / 7 | 0.00e+00 | yes |
| USDJPY.sim | 7 | 7 | 7 | 7 / 7 | 0.00e+00 | yes |
| AUDUSD.sim | 6 | 6 | 6 | 6 / 6 | 0.00e+00 | yes |

## Future-scramble test (portfolio, 20 random cut times per market inside its own history, all its data after the cut shuffled)

| Symbol | Cuts with every decision before the cut identical | Decisions before the cut (min / median) | Decisions changed after the cut (min / median) |
|---|---:|---|---|
| XAUUSD.sim | **20 / 20** | 2 / 43 | 0 / 44 |
| XAGUSD.sim | **20 / 20** | 0 / 32 | 0 / 63 |
| USOIL.sim | **20 / 20** | 0 / 39 | 7 / 51 |
| US500.sim | **20 / 20** | 10 / 41 | 7 / 38 |
| US100.sim | **20 / 20** | 2 / 36 | 13 / 72 |
| EURUSD.sim | **20 / 20** | 0 / 7 | 0 / 30 |
| USDJPY.sim | **20 / 20** | 0 / 5 | 0 / 23 |
| AUDUSD.sim | **20 / 20** | 0 / 5 | 0 / 23 |

Every decision is also checked to be logged with data no newer than its decision time.

## Notes and open questions for Yash

- Germany 40 and Japan 225 are not offered by this broker: skipped (spec §3).
- EURUSD, USDJPY, AUDUSD history starts 2025-05-19 on this broker (MT5 returns nothing earlier; max-bars is unlimited). They miss 2022-2024 entirely. Spec §3 says skip a market with 'too little history' but does not define it — Yash to decide before E3-2.
- Commission: FX $2.50/lot/side and gold 0.0007% confirmed from deals on Yash's trial account. MT5 `symbol_info` has no commission field; oil and indices have no trial deals, so spec values are used unverified.
- Triple swap: only USOIL gives a valid day (Friday). The others read 7 (invalid), as gold did in Experiment 2; Wednesday is used provisionally (Experiment 2 clarification 3) — Yash to confirm.
- USDJPY P&L, commission and swap are computed in JPY (its profit currency); results in R are unaffected. The $ conversion for FTMO sizing is an E3-2 task.
- Fills: entries and 20-day exits at the daily open, paying that day's open-hour spread; stops are checked on H1 bars (longs on bid lows, shorts on ask highs; a gap through the stop fills at the open).
