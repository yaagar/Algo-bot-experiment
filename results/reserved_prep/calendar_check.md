# News calendar 2010-2021 (option a) — build and Forex Factory cross-check

Saved: `data/processed/calendar_usd_high_2010_2021.parquet` (1368 events, 2010-01-05 to 2021-12-23). The 2022+ calendar file is unchanged.

## Events per year

| event | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CPI | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 |
| FOMC decision | 9 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 9 | 10 | 8 |
| FOMC minutes | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 |
| FOMC press conference | 0 | 3 | 5 | 4 | 4 | 4 | 4 | 4 | 4 | 8 | 9 | 8 |
| GDP | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 11 | 12 | 12 |
| ISM manufacturing | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 |
| ISM services | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 |
| NFP | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 |
| PCE | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 11 | 12 | 12 |
| PPI | 13 | 13 | 13 | 12 | 12 | 12 | 12 | 13 | 12 | 13 | 13 | 12 |
| Retail sales | 0 | 0 | 0 | 8 | 12 | 12 | 12 | 12 | 12 | 11 | 12 | 12 |

## FOMC statement time source

| source | count |
|---|---|
| Fed statement page | 52 |
| Fed feed posting time, rounded down (approx.) | 28 |
| Fed press-conference page | 20 |

Fed pages list 120 meetings/calls/votes; 108 have a statement, 57 a press conference.

## Cross-check with Forex Factory (2010-2021, USD rows of any impact level)

| event | ours | in_FF | FF_not_ours | time_checked | time_match |
|---|---|---|---|---|---|
| FOMC decision | 100 | 96 | 1 | 84 | 69 |
| FOMC press conference | 57 | 57 | 0 | 57 | 55 |
| FOMC minutes | 96 | 96 | 0 | 94 | 91 |
| NFP | 144 | 144 | 0 | 32 | 32 |
| CPI | 144 | 144 | 0 | 54 | 54 |
| PPI | 150 | 144 | 0 | 43 | 42 |
| PCE | 143 | 143 | 1 | 46 | 40 |
| GDP | 143 | 143 | 0 | 68 | 67 |
| Retail sales | 103 | 103 | 41 | 51 | 50 |
| ISM manufacturing | 144 | 136 | 8 | 127 | 126 |
| ISM services | 144 | 134 | 10 | 115 | 114 |

time_checked = days where FF kept an exact time; ~half of FF rows lost their time.

## ISM in January: one business day later?

| year | event | FF | nth_business_day | one_later | rule_holds |
|---|---|---|---|---|---|
| 2010 | ISM manufacturing | 2010-01-04 | 2010-01-04 | 2010-01-05 | False |
| 2010 | ISM services | 2010-01-06 | 2010-01-06 | 2010-01-07 | False |
| 2011 | ISM manufacturing | 2011-01-03 | 2011-01-03 | 2011-01-04 | False |
| 2011 | ISM services | 2011-01-05 | 2011-01-05 | 2011-01-06 | False |
| 2012 | ISM manufacturing | 2012-01-03 | 2012-01-03 | 2012-01-04 | False |
| 2012 | ISM services | 2012-01-05 | 2012-01-05 | 2012-01-06 | False |
| 2013 | ISM manufacturing | 2013-01-02 | 2013-01-02 | 2013-01-03 | False |
| 2013 | ISM services | 2013-01-04 | 2013-01-04 | 2013-01-07 | False |
| 2014 | ISM manufacturing | 2014-01-02 | 2014-01-02 | 2014-01-03 | False |
| 2014 | ISM services | 2014-01-06 | 2014-01-06 | 2014-01-07 | False |
| 2015 | ISM manufacturing | 2015-01-02 | 2015-01-02 | 2015-01-05 | False |
| 2015 | ISM services | 2015-01-06 | 2015-01-06 | 2015-01-07 | False |
| 2016 | ISM manufacturing | 2016-01-04 | 2016-01-04 | 2016-01-05 | False |
| 2016 | ISM services | 2016-01-06 | 2016-01-06 | 2016-01-07 | False |
| 2017 | ISM manufacturing | 2017-01-03 | 2017-01-03 | 2017-01-04 | False |
| 2017 | ISM services | 2017-01-05 | 2017-01-05 | 2017-01-06 | False |
| 2018 | ISM manufacturing | 2018-01-03 | 2018-01-02 | 2018-01-03 | True |
| 2018 | ISM services | 2018-01-05 | 2018-01-04 | 2018-01-05 | True |
| 2019 | ISM manufacturing | 2019-01-03 | 2019-01-02 | 2019-01-03 | True |
| 2019 | ISM services | 2019-01-07 | 2019-01-04 | 2019-01-07 | True |
| 2020 | ISM manufacturing | 2020-01-03 | 2020-01-02 | 2020-01-03 | True |
| 2020 | ISM services | 2020-01-07 | 2020-01-06 | 2020-01-07 | True |
| 2021 | ISM manufacturing | 2021-01-05 | 2021-01-04 | 2021-01-05 | True |
| 2021 | ISM services | 2021-01-07 | 2021-01-06 | 2021-01-07 | True |

## Every mismatch

| event | date | kind | ours_NY | FF_NY |
|---|---|---|---|---|
| FOMC decision | 2010-05-09 | ours only | 21:15 | - |
| FOMC decision | 2019-10-11 | ours only | 11:00 | - |
| FOMC decision | 2020-03-15 | ours only | 17:00 | - |
| FOMC decision | 2020-03-23 | ours only | 08:00 | - |
| FOMC decision | 2020-03-16 | FF only | - | no time |
| FOMC decision | 2010-01-27 | time differs | 14:15 | 14:16 |
| FOMC decision | 2010-03-16 | time differs | 14:15 | 14:13 |
| FOMC decision | 2010-04-28 | time differs | 14:15 | 14:14 |
| FOMC decision | 2011-03-15 | time differs | 14:15 | 14:14 |
| FOMC decision | 2011-04-27 | time differs | 12:30 | 12:32 |
| FOMC decision | 2011-06-22 | time differs | 12:30 | 12:27 |
| FOMC decision | 2011-08-09 | time differs | 14:15 | 14:19 |
| FOMC decision | 2011-09-21 | time differs | 14:15 | 14:23 |
| FOMC decision | 2011-11-02 | time differs | 12:30 | 12:32 |
| FOMC decision | 2011-12-13 | time differs | 14:15 | 14:13 |
| FOMC decision | 2012-01-25 | time differs | 12:20 | 12:28 |
| FOMC decision | 2012-04-25 | time differs | 12:35 | 12:30 |
| FOMC decision | 2012-06-20 | time differs | 12:35 | 12:32 |
| FOMC decision | 2012-08-01 | time differs | 14:15 | 14:13 |
| FOMC decision | 2012-09-13 | time differs | 12:35 | 12:30 |
| FOMC press conference | 2020-03-03 | time differs | 10:30 | 11:00 |
| FOMC press conference | 2020-03-15 | time differs | 17:30 | 18:30 |
| FOMC minutes | 2011-11-22 | time differs | 14:00 | 13:28 |
| FOMC minutes | 2013-04-10 | time differs | 14:00 | 09:00 |
| FOMC minutes | 2015-08-19 | time differs | 14:00 | 13:46 |
| PPI | 2010-02-16 | ours only | 08:30 | - |
| PPI | 2011-02-14 | ours only | 08:30 | - |
| PPI | 2012-02-14 | ours only | 08:30 | - |
| PPI | 2017-02-10 | ours only | 08:30 | - |
| PPI | 2019-02-12 | ours only | 08:30 | - |
| PPI | 2020-02-14 | ours only | 08:30 | - |
| PPI | 2021-04-09 | time differs | 08:30 | 08:56 |
| PCE | 2019-04-28 | FF only | - | 15:30 |
| PCE | 2012-10-29 | time differs | 08:30 | 08:32 |
| PCE | 2016-02-26 | time differs | 08:30 | 10:00 |
| PCE | 2016-12-22 | time differs | 08:30 | 10:00 |
| PCE | 2019-11-27 | time differs | 08:30 | 10:00 |
| PCE | 2019-12-20 | time differs | 08:30 | 10:00 |
| PCE | 2021-11-24 | time differs | 08:30 | 10:00 |
| GDP | 2020-04-29 | time differs | 08:30 | 08:32 |
| Retail sales | 2010-01-14 | FF only | - | no time |
| Retail sales | 2010-02-12 | FF only | - | no time |
| Retail sales | 2010-03-12 | FF only | - | 08:30 |
| Retail sales | 2010-04-14 | FF only | - | no time |
| Retail sales | 2010-05-14 | FF only | - | no time |
| Retail sales | 2010-06-11 | FF only | - | no time |
| Retail sales | 2010-07-14 | FF only | - | 08:30 |
| Retail sales | 2010-08-13 | FF only | - | no time |
| Retail sales | 2010-09-14 | FF only | - | no time |
| Retail sales | 2010-10-15 | FF only | - | no time |
| Retail sales | 2010-11-15 | FF only | - | no time |
| Retail sales | 2010-12-14 | FF only | - | no time |
| Retail sales | 2011-01-14 | FF only | - | no time |
| Retail sales | 2011-02-15 | FF only | - | no time |
| Retail sales | 2011-03-11 | FF only | - | 08:30 |
| Retail sales | 2011-04-13 | FF only | - | 08:30 |
| Retail sales | 2011-05-12 | FF only | - | no time |
| Retail sales | 2011-06-14 | FF only | - | no time |
| Retail sales | 2011-07-14 | FF only | - | 08:30 |
| Retail sales | 2011-08-12 | FF only | - | 08:30 |
| Retail sales | 2011-09-14 | FF only | - | no time |
| Retail sales | 2011-10-14 | FF only | - | no time |
| Retail sales | 2011-11-15 | FF only | - | no time |
| Retail sales | 2011-12-13 | FF only | - | 08:30 |
| Retail sales | 2012-01-12 | FF only | - | no time |
| Retail sales | 2012-02-14 | FF only | - | no time |
| Retail sales | 2012-03-13 | FF only | - | 08:30 |
| Retail sales | 2012-04-16 | FF only | - | no time |
| Retail sales | 2012-05-15 | FF only | - | no time |
| Retail sales | 2012-06-13 | FF only | - | 08:30 |
| Retail sales | 2012-07-16 | FF only | - | no time |
| Retail sales | 2012-08-14 | FF only | - | 08:30 |
| Retail sales | 2012-09-14 | FF only | - | no time |
| Retail sales | 2012-10-15 | FF only | - | 08:30 |
| Retail sales | 2012-11-14 | FF only | - | 08:30 |
| Retail sales | 2012-12-13 | FF only | - | no time |
| Retail sales | 2013-01-15 | FF only | - | 08:30 |
| Retail sales | 2013-02-13 | FF only | - | 08:30 |
| Retail sales | 2013-03-13 | FF only | - | 08:30 |
| Retail sales | 2013-04-12 | FF only | - | 08:30 |
| Retail sales | 2019-04-18 | FF only | - | no time |
| Retail sales | 2021-05-14 | time differs | 08:30 | 08:32 |
| ISM manufacturing | 2010-01-05 | ours only | 10:00 | - |
| ISM manufacturing | 2011-01-04 | ours only | 10:00 | - |
| ISM manufacturing | 2012-01-04 | ours only | 10:00 | - |
| ISM manufacturing | 2013-01-03 | ours only | 10:00 | - |
| ISM manufacturing | 2014-01-03 | ours only | 10:00 | - |
| ISM manufacturing | 2015-01-05 | ours only | 10:00 | - |
| ISM manufacturing | 2016-01-05 | ours only | 10:00 | - |
| ISM manufacturing | 2017-01-04 | ours only | 10:00 | - |
| ISM manufacturing | 2010-01-04 | FF only | - | 10:00 |
| ISM manufacturing | 2011-01-03 | FF only | - | 10:00 |
| ISM manufacturing | 2012-01-03 | FF only | - | 10:00 |
| ISM manufacturing | 2013-01-02 | FF only | - | 10:00 |
| ISM manufacturing | 2014-01-02 | FF only | - | 10:00 |
| ISM manufacturing | 2015-01-02 | FF only | - | 10:00 |
| ISM manufacturing | 2016-01-04 | FF only | - | 10:00 |
| ISM manufacturing | 2017-01-03 | FF only | - | 10:00 |
| ISM manufacturing | 2015-08-03 | time differs | 10:00 | 09:45 |
| ISM services | 2010-01-07 | ours only | 10:00 | - |
| ISM services | 2011-01-06 | ours only | 10:00 | - |
| ISM services | 2012-01-06 | ours only | 10:00 | - |
| ISM services | 2013-01-07 | ours only | 10:00 | - |
| ISM services | 2014-01-07 | ours only | 10:00 | - |
| ISM services | 2015-01-07 | ours only | 10:00 | - |
| ISM services | 2015-04-03 | ours only | 10:00 | - |
| ISM services | 2016-01-07 | ours only | 10:00 | - |
| ISM services | 2017-01-06 | ours only | 10:00 | - |
| ISM services | 2018-12-05 | ours only | 10:00 | - |
| ISM services | 2010-01-06 | FF only | - | 10:00 |
| ISM services | 2011-01-05 | FF only | - | 10:00 |
| ISM services | 2012-01-05 | FF only | - | no time |
| ISM services | 2013-01-04 | FF only | - | 10:00 |
| ISM services | 2014-01-06 | FF only | - | 10:00 |
| ISM services | 2015-01-06 | FF only | - | 10:00 |
| ISM services | 2015-04-06 | FF only | - | no time |
| ISM services | 2016-01-06 | FF only | - | 10:00 |
| ISM services | 2017-01-05 | FF only | - | 10:00 |
| ISM services | 2018-12-06 | FF only | - | no time |
| ISM services | 2014-03-05 | time differs | 10:00 | 09:57 |
