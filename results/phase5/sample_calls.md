# Phase 5 — sample calls and run estimate

| Call | Decision | Input tokens (new / cache write / cache read) | Output tokens | API-equivalent $ | Seconds |
|---|---|---|---:|---:|---:|
| morning {'date': '2026-07-08'} | TRADE_DAY | 2 / 6751 / 0 | 367 | 0.066102 | 5.6 |
| morning {'date': '2026-08-26'} | TRADE_DAY | 2 / 5486 / 1353 | 300 | 0.055008600000000005 | 5.2 |
| veto {'date': '2026-07-10', 'tf': 'M15'} | TAKE | 2 / 6997 / 0 | 703 | 0.074933 | 9.4 |
| veto {'date': '2026-09-24', 'tf': 'M15'} | TAKE | 2 / 6248 / 1468 | 890 | 0.0735236 | 10.2 |
| veto {'date': '2026-09-01', 'tf': 'H1'} | TAKE | 2 / 5177 / 1468 | 765 | 0.061765600000000004 | 9.6 |

Planned calls: 71 morning + up to 64 veto (fewer if NO_TRADE_DAYs) = 135, +20% recheck ≈ **162 calls**.
Average per call: 7,597 tokens, $0.066 API-equivalent, 8s.
**Estimated total: ≈ 1.23M tokens, ≈ $11 API-equivalent, ≈ 22 minutes of calls.**
