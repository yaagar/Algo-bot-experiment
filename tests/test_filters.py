import datetime as dt

import pandas as pd

from src.filters import narrow_box_tags, trend_up_tags


def test_narrow_uses_only_prior_days():
    dates = [dt.date(2022, 1, 3) + dt.timedelta(days=i) for i in range(22)]
    widths = pd.Series([10.0] * 20 + [5.0, 50.0], index=dates)
    tags = narrow_box_tags(widths)
    assert tags.iloc[19] is None                 # only 19 prior days
    assert tags.iloc[20] == True                  # 5 < median(10s)
    assert tags.iloc[21] == False                 # today's 50 doesn't affect its own median


def test_trend_uses_completed_days_only():
    days = [dt.date(2022, 2, 1) + dt.timedelta(days=i) for i in range(21)]
    closes = pd.Series([100.0] * 20 + [1000.0], index=days)   # huge close ON the trade date
    trade_day = days[20]
    # the trade-date close is not complete at 07:00 London -> must not be used
    assert trend_up_tags([trade_day], closes)[trade_day] == False   # 100 is not > avg 100
    next_day = trade_day + dt.timedelta(days=1)
    assert trend_up_tags([next_day], closes)[next_day] == True      # now 1000 is completed
