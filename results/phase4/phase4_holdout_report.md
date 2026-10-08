# Phase 4 — HOLDOUT run (one time): 2026-01-01 → 2026-09-30

Window (UTC): 2026-01-01 00:00:00+00:00 → 2026-09-30 23:00:00+00:00. Phase 3 code and rules unchanged, kill switch included. Real broker spreads throughout (recorded since 2025-12-17). Run once.

## M15 entry timeframe — official

| Metric | base | spread ×1.5 | commission 0.0025% |
|---|---:|---:|---:|
| Trades | 62 | 62 | 62 |
| Win rate | 61.3% | 61.3% | 61.3% |
| Average R | +0.228 | +0.226 | +0.228 |
| Expectancy / trade | $+9.23 | $+9.15 | $+9.07 |
| Net profit | $572 | $567 | $562 |
| Average month | $64 | $63 | $62 |
| % months profitable | 89% | 89% | 89% |
| Fewest profitable months in any 6-month window | 5 / 6 | 5 / 6 | 5 / 6 |
| Worst month | $-75 (2026-01) | $-76 (2026-01) | $-76 (2026-01) |
| Worst day | $-49 | $-49 | $-49 |
| Max drawdown | $147 (1.5%) | $148 (1.5%) | $148 (1.5%) |
| Longest losing streak | 4 | 4 | 4 |
| FTMO breach | no | no | no |
| FTMO-flagged exits (±2 min of news) | 2 | 2 | 2 |
| Kill switch triggered | no | no | no |
| C1 net profit: 5% / median / 95% | $-477 / $-68 / $337 | $-479 / $-75 / $331 | $-501 / $-78 / $327 |
| **A beats % of C1 runs** | **99.5%** | **99.5%** | **99.5%** |
| **Official verdict (§11)** | **FAIL** | **FAIL** | **FAIL** |

Checks per cost case:

| Check | base | spread ×1.5 | commission 0.0025% |
|---|---|---|---|
| avg net profit >= $100/month | ❌ | ❌ | ❌ |
| >= 4 profitable months in every 6-month window | ✅ | ✅ | ✅ |
| no FTMO breach | ✅ | ✅ | ✅ |
| beats >= 90% of C1 runs | ✅ | ✅ | ✅ |

Monthly net P&L (official run):

| Month | base | spread ×1.5 | commission 0.0025% |
|---|---:|---:|---:|
| 2026-01 | $-75 | $-76 | $-76 |
| 2026-02 | $10 | $10 | $9 |
| 2026-03 | $118 | $117 | $117 |
| 2026-04 | $116 | $116 | $115 |
| 2026-05 | $109 | $108 | $107 |
| 2026-06 | $32 | $31 | $31 |
| 2026-07 | $112 | $111 | $110 |
| 2026-08 | $24 | $23 | $22 |
| 2026-09 | $128 | $126 | $126 |

## H1 entry timeframe — official

| Metric | base | spread ×1.5 | commission 0.0025% |
|---|---:|---:|---:|
| Trades | 49 | 49 | 49 |
| Win rate | 61.2% | 61.2% | 61.2% |
| Average R | +0.245 | +0.243 | +0.245 |
| Expectancy / trade | $+10.90 | $+10.81 | $+10.74 |
| Net profit | $534 | $530 | $526 |
| Average month | $59 | $59 | $58 |
| % months profitable | 89% | 89% | 89% |
| Fewest profitable months in any 6-month window | 5 / 6 | 5 / 6 | 5 / 6 |
| Worst month | $-66 (2026-01) | $-66 (2026-01) | $-66 (2026-01) |
| Worst day | $-49 | $-49 | $-49 |
| Max drawdown | $98 (0.9%) | $99 (0.9%) | $99 (0.9%) |
| Longest losing streak | 3 | 3 | 3 |
| FTMO breach | no | no | no |
| FTMO-flagged exits (±2 min of news) | 2 | 2 | 2 |
| Kill switch triggered | no | no | no |
| C1 net profit: 5% / median / 95% | $-432 / $1 / $352 | $-453 / $-3 / $348 | $-440 / $-7 / $344 |
| **A beats % of C1 runs** | **98.0%** | **98.0%** | **98.0%** |
| **Official verdict (§11)** | **FAIL** | **FAIL** | **FAIL** |

Checks per cost case:

| Check | base | spread ×1.5 | commission 0.0025% |
|---|---|---|---|
| avg net profit >= $100/month | ❌ | ❌ | ❌ |
| >= 4 profitable months in every 6-month window | ✅ | ✅ | ✅ |
| no FTMO breach | ✅ | ✅ | ✅ |
| beats >= 90% of C1 runs | ✅ | ✅ | ✅ |

Monthly net P&L (official run):

| Month | base | spread ×1.5 | commission 0.0025% |
|---|---:|---:|---:|
| 2026-01 | $-66 | $-66 | $-66 |
| 2026-02 | $51 | $51 | $51 |
| 2026-03 | $140 | $140 | $139 |
| 2026-04 | $67 | $66 | $66 |
| 2026-05 | $110 | $110 | $109 |
| 2026-06 | $81 | $81 | $81 |
| 2026-07 | $68 | $67 | $67 |
| 2026-08 | $73 | $72 | $72 |
| 2026-09 | $10 | $9 | $8 |

## Information only — kill switch disabled (NOT a verdict)

Same rules and base costs, but the 6% kill switch never stops the strategy (C1 likewise).

| TF | Trades | Net profit | Avg month | Fewest profitable in a 6-mo window | Max DD | FTMO breach | FTMO-flagged exits | A beats % of C1 | C1 median |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|
| M15 | 62 | $572 | $64 | 5 / 6 | $147 (1.5%) | no | 2 | 99.5% | $-68 |
| H1 | 49 | $534 | $59 | 5 / 6 | $98 (0.9%) | no | 2 | 98.0% | $1 |

Monthly net P&L, information-only run:

| Month | M15 | H1 |
|---|---:|---:|
| 2026-01 | $-75 | $-66 |
| 2026-02 | $10 | $51 |
| 2026-03 | $118 | $140 |
| 2026-04 | $116 | $67 |
| 2026-05 | $109 | $110 |
| 2026-06 | $32 | $81 |
| 2026-07 | $112 | $68 |
| 2026-08 | $24 | $73 |
| 2026-09 | $128 | $10 |

## Bot A, Jul–Sep 2026 (Bot B comparison window), base costs

*Slice* = these months of the official holdout run (carries the kill-switch state from earlier in 2026). *Fresh* = a standalone run starting 2026-07-01 with a new $10,000 account — the setup Phase 5 compares B against.

| TF | Version | Trades | Net P&L | Max drawdown | Worst month | FTMO breach | FTMO-flagged exits |
|---|---|---:|---:|---:|---|---|---:|
| M15 | slice | 33 | $263 | $89 | $24 (2026-08) | no | 0 |
| M15 | fresh | 33 | $263 | $89 | $24 (2026-08) | no | 0 |
| H1 | slice | 26 | $151 | $98 | $10 (2026-09) | no | 0 |
| H1 | fresh | 26 | $151 | $98 | $10 (2026-09) | no | 0 |
