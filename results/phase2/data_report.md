# Phase 2 — Data report

Generated 2026-10-08. Broker: OANDA-Demo-1 (FTMO trial), symbol `XAUUSD.sim`.

## 1. Price data (MT5)

| TF | Bars | First bar (UTC) | Last bar (UTC) | Real spread from |
|---|---:|---|---|---|
| H1 | 101,099 | 2009-12-31 22:00 | 2026-10-08 00:00 | 2025-12-17 |
| M15 | 397,646 | 2009-12-31 22:00 | 2026-10-08 00:15 | 2025-12-17 |
| M1 | 5,782,767 | 2009-12-31 22:00 | 2026-10-08 00:22 | 2025-12-17 |

- History goes back at least to 2010 on all three timeframes — the whole development period (2022+) is covered.
- **Spread is 0 on every bar before 2025-12-17.** The broker did not record spread before then. No tick history exists before late 2025 either. → **Decision needed** (development-period costs and §5.2 box-vs-spread skip).
- Raw files keep broker server time; processed files have tz-aware `time_utc`.
- Gotcha found: MT5 reads timezone-less datetimes as the PC's local time (UTC−8 here). All requests now pass explicit UTC.
- Gotcha found: the old 100,000 "Max bars" limit stayed active until MT5 was restarted.

## 2. Broker server time

**Rule: server clock = New York clock + 7 h** → UTC+3 while the US is on daylight time, UTC+2 otherwise, switching on US dates.

| Check (2022 → now) | Result |
|---|---|
| Daily break: trading resumes 01:00–01:10 server (= just after 18:00 NY) | 98.1% of weekdays; 67 / 69 days in US/EU clock-mismatch weeks |
| NFP: 08:30 NY minute is a ≥3× spike after conversion | 95% of 39 NFP days (summer 92%, winter 100%, mismatch weeks 100%) |
| Competing rules (EU DST / fixed +2 / fixed +3) | each fails a whole group (mismatch 0%, summer 4%, winter 33%) |

Plot: `server_time_nfp.png` (24 summer, 15 winter NFP days).

## 3. Economic calendar (USD high impact)

| Source | Period | Events |
|---|---|---:|
| Forex Factory (Hugging Face, Ehsanrs2) | 2022-01-01 → 2025-04-07 | 1,101 |
| federalreserve.gov (FOMC statement, rate, projections, minutes) | after 2025-04-07 | 68 |
| bea.gov (GDP, PCE) | 2026 only | 25 |
| **bls.gov (NFP, CPI, PPI, JOLTS)** | — | **blocked (403 to scripts)** |

Repairs to the Forex Factory file:
- **Timezone tag wrong**: summers 2023+ tagged +04:30 though Iran dropped DST in 2023 → events were 1 h early. Re-applied the real Tehran rule.
- **53% of USD high-impact rows had no time** (shown as 00:00). Filled with the official NY release time for scheduled releases (08:30 / 09:45 / 10:00 / 14:00). Checked against the rows that kept their time: ~100% agree (3 exceptions in ~400: one FF data error, one typo, one Thanksgiving-week PCE at 10:00).
- 20 events stay `time_status = unknown` (Powell speeches, elections) — no fixed time.

**Gaps after 2025-04-07:** BLS releases, BEA Apr–Dec 2025, and others Forex Factory rated high (retail sales, jobless claims, ISM, PMI, consumer confidence). → **Decision needed.**

## 4. Headlines (GDELT, Bot B)

**Not downloaded yet.** Every request since the start returns HTTP 429 ("limit requests to one every 5 seconds"), even after waits of 1–8 minutes — looks like a block on this IP. The downloader is resumable and backs off up to 15 min between tries.

## 5. P&L formula check

`src/check_pnl.py` reads closed gold trades from the account and compares with `src/pnl.py`:

| Trade | Lots | Broker P&L | Ours | Broker commission | Ours |
|---|---:|---:|---:|---:|---:|
| LONG 4106.91 → 4106.65 | 0.10 | −2.60 | −2.60 | −0.58 | −0.58 |
| SHORT 4111.48 → 4111.53 | 0.01 | −0.05 | −0.05 | −0.06 | −0.06 |

Both match to the cent.
