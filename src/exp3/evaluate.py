"""Experiment 3 evaluation (spec §5): statistics in R, and the FTMO Swing simulation with real lots.

R statistics use each trade's net R (fractional size, every trade risks 1R). Trades count in the month
and year they CLOSE. The portfolio is simply all markets' trades together (equal risk per trade).

FTMO simulation ($10k account, fixed $ risk per trade):
  lots = floor_to_step(risk $ / (stop distance x contract size x USD per price unit)); below the minimum
  lot the signal is skipped. A trade's $ result = its fractional result scaled to those lots (every cost is
  proportional to lots), converted to USD at the exit price (USDJPY is quoted in JPY).
  Daily loss (spec §5.5, conservative): for every broker day a position is open, its floating P&L is taken
  at that day's worst price (daily low for longs, daily high + spread for shorts), minus its full commission
  and any swap charge. On the day it is stopped out, the realised result is used (it no longer exists after
  the stop). Equity low = start-of-day balance + the sum over open positions. Breach if it falls $500 below
  the start-of-day balance (5%) or below $9,000 (10%).
  Margin: notional in USD / 30 summed over open positions at each day's close, vs that day's equity low.
"""
import numpy as np
import pandas as pd

from src.timeutils import utc_to_server

INITIAL, DAILY_LIMIT, TOTAL_LIMIT, LEVERAGE = 10_000.0, 500.0, 1_000.0, 30
MONTHS = pd.period_range("2022-01", "2026-09", freq="M")
FULL_YEARS = (2022, 2023, 2024, 2025)


def exit_month(t):
    return pd.to_datetime(t.exit_ns, utc=True).dt.tz_convert(None).dt.to_period("M")


def r_stats(t):
    """Trades, expectancy, total R, % profitable months, max drawdown, worst month, R per year."""
    if t.empty:
        return {"trades": 0, "expectancy": 0.0, "total_r": 0.0, "pct_months_profitable": 0.0,
                "max_dd_r": 0.0, "worst_month_r": 0.0, "per_year": {}, "monthly": pd.Series(0.0, index=MONTHS)}
    t = t.sort_values("exit_ns")
    monthly = t.groupby(exit_month(t)).net_r.sum().reindex(MONTHS, fill_value=0.0)
    cum = np.r_[0.0, t.net_r.cumsum().to_numpy()]
    years = pd.to_datetime(t.exit_ns, utc=True).dt.year
    return {"trades": len(t), "expectancy": float(t.net_r.mean()), "total_r": float(t.net_r.sum()),
            "pct_months_profitable": float((monthly > 0).mean()),
            "max_dd_r": float((np.maximum.accumulate(cum) - cum).max()),
            "worst_month_r": float(monthly.min()),
            "per_year": t.groupby(years).net_r.sum().to_dict(), "monthly": monthly}


def quote_per_usd(spec, price):
    return price if spec["currency_profit"] != "USD" else 1.0


def server_dates(ns):
    return utc_to_server(pd.Series(pd.to_datetime(np.asarray(ns, dtype=np.int64), utc=True))).dt.date.to_numpy()


def ftmo_sim(trades, specs, d1s, risk_usd):
    """trades: {symbol: engine trades frame}; d1s: {symbol: D1 bars}. Returns summary dict."""
    by_day = {}                        # server date -> list of (worst $, realised $ if closed that day, margin $)
    closed = []                        # (exit server date, exit ns, $)
    signals = skipped = 0
    for spec in specs:
        sym = spec["symbol"]
        t, d1 = trades[sym], d1s[sym]
        if t.empty:
            continue
        cs, step, vmin, point = spec["contract_size"], spec["volume_step"], spec["volume_min"], spec["point"]
        d_open = d1.time_utc.dt.tz_convert(None).to_numpy().astype("datetime64[ns]").astype(np.int64)
        d_date = server_dates(d_open)
        hi, lo, cl = d1.high.to_numpy(), d1.low.to_numpy(), d1.close.to_numpy()
        ask_hi = hi + d1.spread_used.to_numpy() * point
        for tr in t.itertuples():
            signals += 1
            d = 1 if tr.direction == "LONG" else -1
            usd_per_unit = 1.0 / quote_per_usd(spec, tr.entry_price)
            lots = np.floor(risk_usd / (tr.stop_distance * cs * usd_per_unit) / step + 1e-9) * step
            if lots < vmin - 1e-12:
                skipped += 1
                continue
            scale = lots / tr.lots
            realised = tr.net_usd * scale / quote_per_usd(spec, tr.exit_price)
            charges = tr.commission_usd * scale - min(tr.swap_usd * scale, 0.0)     # in quote currency
            exit_day = server_dates([tr.exit_ns])[0]
            closed.append((exit_day, tr.exit_ns, realised))
            for k in np.flatnonzero((d_open >= tr.entry_ns) & (d_open < tr.exit_ns)):
                worst_px = lo[k] if d > 0 else ask_hi[k]
                q = quote_per_usd(spec, worst_px)
                worst = (d * (worst_px - tr.entry_price) * lots * cs - charges) / q
                ends_today = k + 1 >= len(d_open) or tr.exit_ns < d_open[k + 1]
                if ends_today and tr.exit_reason == "stop":
                    worst = realised
                elif ends_today:
                    worst = min(worst, realised)
                margin = lots * cs * cl[k] / quote_per_usd(spec, cl[k]) / LEVERAGE
                by_day.setdefault(d_date[k], []).append((worst, margin))
    closed_df = pd.DataFrame(closed, columns=["day", "exit_ns", "usd"])
    days = sorted(set(by_day) | set(closed_df.day))
    realised_by_day = closed_df.groupby("day").usd.sum()
    balance, peak = INITIAL, INITIAL
    daily_breach = total_breach = None
    worst_daily, max_dd, max_margin_ratio = 0.0, 0.0, 0.0
    for day in days:
        pos = by_day.get(day, [])
        low = balance + sum(w for w, _ in pos)
        margin = sum(m for _, m in pos)
        worst_daily = max(worst_daily, balance - low)
        max_dd = max(max_dd, peak - low)
        if pos:
            max_margin_ratio = max(max_margin_ratio, margin / low)
        if daily_breach is None and balance - low >= DAILY_LIMIT:
            daily_breach = day
        if total_breach is None and low < INITIAL - TOTAL_LIMIT:
            total_breach = day
        balance += realised_by_day.get(day, 0.0)
        peak = max(peak, balance)
    monthly = closed_df.groupby(pd.to_datetime(closed_df.exit_ns, utc=True).dt.tz_convert(None).dt.to_period("M")) \
        .usd.sum().reindex(MONTHS, fill_value=0.0) if len(closed_df) else pd.Series(0.0, index=MONTHS)
    windows = [int((monthly.iloc[i:i + 6] > 0).sum()) for i in range(len(monthly) - 5)]
    return {"risk": risk_usd, "signals": signals, "skipped_min_lot": skipped,
            "pct_skipped": skipped / signals if signals else 0.0,
            "avg_month": float(monthly.mean()), "pct_months_profitable": float((monthly > 0).mean()),
            "min_profitable_in_6m": min(windows), "worst_month": float(monthly.min()),
            "max_dd_usd": max_dd, "worst_day_loss": worst_daily,
            "daily_breach": daily_breach, "total_breach": total_breach,
            "max_margin_to_equity": max_margin_ratio, "final_balance": balance}
