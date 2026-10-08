# Phase 2 — Data report

Generated 2026-10-08 (spec v1.2). Broker: OANDA-Demo-1 (FTMO trial), symbol `XAUUSD.sim`.

## 1. Price data (MT5)

| TF | Bars | First bar (UTC) | Last bar (UTC) | Real spread from |
|---|---:|---|---|---|
| H1 | 101,099 | 2009-12-31 22:00 | 2026-10-08 00:00 | 2025-12-17 |
| M15 | 397,646 | 2009-12-31 22:00 | 2026-10-08 00:15 | 2025-12-17 |
| M1 | 5,782,767 | 2009-12-31 22:00 | 2026-10-08 00:22 | 2025-12-17 |

- History reaches at least 2010 on all three timeframes (search started there) — the development period (2022+) is fully covered.
- Raw files keep broker server time; processed files have tz-aware `time_utc`, `spread_used` and `spread_estimated`.
- Gotchas found: MT5 reads timezone-less datetimes as the PC's local time (UTC−8) — all requests pass explicit UTC; the old 100,000 "Max bars" limit stayed active until MT5 was restarted.

## 2. Spread (spec v1.2)

The broker recorded spread = 0 on every bar before 2025-12-17 (no older ticks either). Those bars — about 95% of all bars since 2010, and all of 2022 → mid-Dec 2025 — use the **75th-percentile real spread per London hour, from 2026 M1 data**, flagged `spread_estimated = True`.

| London hour | 00 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08–16 | 17–18 | 19 | 20 | 21 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Spread ($) | 0.46 | 0.34 | 0.30 | 0.31 | 0.35 | 0.35 | 0.30 | 0.26 | 0.25–0.26 | 0.28 | 0.30 | 0.31 | 0.41 | 0.81 | 0.55 |

22:00 London is the daily rollover (17:00 New York). Full table: `data/processed/spread_model_p75.json`.

## 3. Broker server time

**Rule: server clock = New York clock + 7 h** → UTC+3 while the US is on daylight time, UTC+2 otherwise, switching on US dates.

| Check (2022 → now) | Result |
|---|---|
| Daily break: trading resumes 01:00–01:10 server (= just after 18:00 NY) | 98.1% of weekdays; 67 / 69 days in US/EU clock-mismatch weeks |
| NFP: 08:30 NY minute is a ≥3× spike after conversion | 93% of 55 NFP days 2022–2026 (summer 91%, winter 95%, mismatch weeks 100%) |
| Competing rules (EU DST / fixed +2 / fixed +3) | each fails a whole group (mismatch 0%, summer 3%, winter 35%) |

Plot: `server_time_nfp.png` (35 summer, 20 winter NFP days).

## 4. Economic calendar (spec v1.2 fixed list)

594 USD events, 2022-01 → 2026-12, in `data/processed/calendar_usd_high.parquet`.

| Event | Time (NY) | Source |
|---|---|---|
| FOMC decision / press conference / minutes | 14:00 / 14:30 / 14:00 | federalreserve.gov |
| NFP, CPI, PPI, PCE, GDP, retail sales | 08:30 (BEA time where published) | FRED release dates |
| ISM manufacturing / services | 10:00 | rule: 1st / 3rd business day (+1 in January) |

- **FRED clean-up:** FRED also lists revision-only days (CPI/PPI seasonal factors in February, NFP benchmark preview, annual retail revision, odd GDP dates). Kept only days when the unadjusted key series (PAYNSA, CPIAUCNS, PPIACO, PCEPI, GDPC1, RSXFSN) got new data; retail sales also limited to the first release in a month. Future dates kept as scheduled.
- **Cross-check vs Forex Factory, 2022 → Apr 2025:** every FF release of these events is in our list (0 missing). Times agree on every FF row that kept its time (25/25 FOMC, 32/32 CPI, 38/38 ISM mfg, …), except one PCE released at 10:00 in Thanksgiving week 2024. Our extra GDP days are real third estimates FF rated below "high".
- **ISM January:** ISM published one business day later in all four Januaries 2022–2025 → rule adds +1 in January.
- 2025 counts are lower (10–11) because the Oct–Nov 2025 government shutdown cancelled releases.
- Forex Factory file faults (documented, now cross-check only): wrong +04:30 summer timezone tag 2023+ (events 1 h early), 53% of USD high-impact rows lost their time.
- **Phase 5 note:** official sources give no *forecast* values, which §6.1 shows Claude for events released earlier in the day.

## 5. Headlines (GDELT, Bot B)

- **Primary: GDELT raw 15-minute GKG files** (kept permanently, so no aging-out). Title match on the five spec topics, English sources, one file per UTC day in `data/raw/gdelt_gkg/`. ~150–600 matching headlines per day; no missing 15-min files so far.
- Backup: DOC API downloader — still HTTP 429 on every request from this network.
- Coverage: see the final count in the Phase 2 summary.

## 6. P&L formula check

`src/check_pnl.py` reads closed gold trades from the account and compares with `src/pnl.py`:

| Trade | Lots | Broker P&L | Ours | Broker commission | Ours |
|---|---:|---:|---:|---:|---:|
| LONG 4106.91 → 4106.65 | 0.10 | −2.60 | −2.60 | −0.58 | −0.58 |
| SHORT 4111.48 → 4111.53 | 0.01 | −0.05 | −0.05 | −0.06 | −0.06 |

Both match to the cent.
