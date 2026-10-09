# Gold Bot Project — What We Learned

*Yash, October 2026. Six experiments, all tested honestly with real costs. None found a strategy worth trading.*

## The goal
Build a trading bot for an FTMO $10k prop account that makes **at least $100 a month**, is profitable in most months, and never breaks FTMO's loss limits (5% in a day, 10% in total).

## How we tested (so the results can be trusted)
- **Rules written before results.** Every rule and pass mark was fixed in advance and never changed after seeing a number.
- **Real costs.** Spread (the gap between buy and sell price), commission, and swap (the nightly fee for holding a position).
- **A coin-flip test.** Each bot was compared with 1,000 copies that trade at the same times but pick buy/sell randomly. A real strategy should beat almost all of them.
- **Counting every try.** We tried 77 strategy versions in total. The more you try, the more likely one looks good by luck, so the bar was raised to match.
- **Cheating checks.** Tests confirmed no bot could "see the future" in the data.
- **A locked final exam.** 2010–2021 data was kept untouched for one final test. No strategy got far enough to use it.

**"R" in the results** means "units of risk": +1R is winning what you risked, −1R is losing it.

## What we tested

| # | Idea | Result |
|---|---|---|
| 1 | **Asian breakout on gold**: trade the break of the quiet overnight range. Plus a version where Claude vetoed risky days. | 2022–25: about +$13/month at best, with a drawdown of up to 18% of the account. 2026 looked good (+$60/month), but costs were later found to be 2.2× too low. Claude's filter didn't help in any of 6 tests. |
| 2 | **Five other gold day-trading strategies** | Best one made +0.014R per trade, effectively zero. None passed. |
| 3 | **Trend-following on 8 markets**, holding for weeks | −5.3R in total. Profitable before costs, but **swap ate all of it**. |
| 4 | **Four signals combined**, with filters for trending and choppy markets, on gold and the S&P 500 | 2,333 trades, −113R. Lost money **every year** and was **worse than 95% of coin-flip bots**. |
| 5 | Night-time currency trading | Skipped: evidence too weak to spend a test on. |
| 6 | **Trend portfolio across 18 FTMO markets** on a Swing account | Before costs +4.7%; **costs −10.3% (swap alone −8.1%)**; net **−5.6%**. Barely beat coin flips (55%). Drawdown 19%, almost double FTMO's 10% limit. |

## The main lessons

**1. Costs are the real enemy.** Every experiment hit one of two walls:
- *Trade short-term* (Exp 1, 2, 4): moves are small, so spread eats them.
- *Hold for days or weeks* (Exp 3, 6): FTMO charges swap every night, roughly like paying 4–6% a year in interest. It ate all the trend profit.

**2. Most "edges" are tiny or zero, even before costs.** The best intraday strategies made about 1–2% of their risk per trade before costs. Nothing that small survives costs.

**3. Famous strategies stop working once they are famous.** Research shows published patterns earn about half as much after publication, because everyone trades them. Textbook patterns on gold and the S&P 500, the most traded markets in the world, had nothing left.

**4. Combining weak signals doesn't make a strong one.** Four zero-edge signals averaged together gave a zero-edge (actually losing) system.

**5. Good stretches fool you.** The Asian breakout looked great for 9 months of 2026 after four flat years. We also tested "switch to whichever strategy won last month": it did no better than picking at random.

**6. Check the data, not just the code.** MT5's saved spreads are the *smallest* spread in each bar, not the normal one. Real spreads were 1.3–11× higher. This made Experiments 1–4 look cheaper than they really were.

**7. FTMO's rules shape what's possible.** The 10% loss limit forces small positions, which caps returns (roughly 4–6% a year at best for a good trend system). Small accounts ($10k–$25k) also can't place the small trades a multi-market portfolio needs.

**8. Simply holding was better.** In 2023–25, just buying and holding the same markets made +26.6%, while the trend system lost money. Over long periods, owning the market has beaten most active trading.

## What worked
- The **testing process**: fixed rules, coin-flip comparison, counting every try, cheating checks. It caught every losing idea **before any real money or challenge fee was spent**.
- Honest reporting: every mistake (a too-quick rule fix, a glimpse at results while debugging, too-low spreads) was written down, not hidden.

## Conclusion
With FTMO CFDs, free tools and public price patterns, **we found no strategy that beats its costs**. The problem is not one bad strategy. It is that the account's costs are bigger than the edges a retail bot can find. Searching further on the same data would only raise the risk of fooling ourselves.

**If returning to this later**, start only with an idea that has a clear reason to work *and* low costs: for example, futures (no swap) on a broker with cheap fees, or plain low-cost ETF investing for long-term growth with your own money.
