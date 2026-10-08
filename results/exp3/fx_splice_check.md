# FX history splice check (Change Log v1.1)

MetaQuotes-Demo server clock = European summer time (UTC+2/+3); converted to UTC with that rule. Daily bars rebuilt from its H1 at the New York 17:00 boundary. Overlap = every full broker day to 2026-09-30.

| Symbol | Overlap days | H1 closes matched | H1 close diff median / max (pips) | Daily O/H/L/C diff median (pips) | Daily O/H/L/C diff max (pips) | MetaQuotes native D1 = NY 17:00 rebuild | Splice: broker from (UTC) | MetaQuotes days used |
|---|---:|---:|---|---|---|---:|---|---:|
| EURUSD.sim | 354 | 8475 / 8498 | 0.2 / 16.5 | 2.0 / 0.2 / 0.2 / 0.7 | 70.2 / 8.4 / 15.5 / 16.5 | 1159 / 1240 | 2025-05-20 21:00 | 880 |
| USDJPY.sim | 354 | 8475 / 8498 | 0.2 / 16.0 | 3.0 / 0.2 / 0.4 / 1.0 | 62.3 / 16.8 / 35.1 / 12.4 | 1157 / 1241 | 2025-05-20 21:00 | 881 |
| AUDUSD.sim | 354 | 8475 / 8498 | 0.2 / 12.4 | 2.3 / 0.2 / 0.3 / 0.7 | 24.6 / 4.4 / 17.8 / 12.4 | 1157 / 1241 | 2025-05-20 21:00 | 881 |

Days where MetaQuotes' native D1 differs from the NY 17:00 rebuild are the weeks when Europe and the US are on different summer-time settings (its day then ends at 18:00 New York); the rebuild is what is used.
