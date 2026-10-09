"""Independent rebuild of Experiment 6's signals, sizing, fills, account and FTMO checks (spec §7).

Written from the spec and Change Log v1.1-v1.3 without importing any Experiment 6 engine, signal or
FTMO code: plain Python loops, zoneinfo clocks, its own daily bars, std, covariance, netting and
limit checks. Inputs are the same raw H1 frames and the recorded E6-0 tables. The runner compares
its per-day forecasts, targets, positions, equity and FTMO day records with the engine's.
"""
import json
import math
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

NY = ZoneInfo("America/New_York")
PRAGUE = ZoneInfo("Europe/Prague")
NS = 10**9
DAYNAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
USD_LEG = {"JPY": ("USDJPY.sim", True), "CAD": ("USDCAD.sim", True), "ZAR": ("USDZAR.sim", True),
           "PLN": ("USDPLN.sim", True), "NOK": ("USDNOK.sim", True), "SEK": ("USDSEK.sim", True),
           "CHF": ("USDCHF.sim", True), "NZD": ("NZDUSD.sim", False), "AUD": ("AUDUSD.sim", False),
           "GBP": ("GBPUSD.sim", False), "EUR": ("EURUSD.sim", False)}


def ints(times):
    return [int(x) for x in pd.Series(times).dt.tz_convert(None).astype("datetime64[ns]").astype("int64")]


def server_date(t_ns):
    return (datetime.fromtimestamp(t_ns // NS, NY).replace(tzinfo=None) + timedelta(hours=7)).date()


def ny_at(d, hour):
    return int(datetime(d.year, d.month, d.day, hour, tzinfo=NY).timestamp()) * NS


def std(xs):
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def rebuild(cfg, frames, results_dir, last_day):
    meta = {s["symbol"]: s for s in json.loads((results_dir / "e6_0_symbols.json").read_text(encoding="utf-8"))["symbols"]}
    ticks = json.loads((results_dir / "e6_0_tick_spreads.json").read_text(encoding="utf-8"))["symbols"]
    swaps = {r["symbol"]: (r["swap_long_pct"], r["swap_short_pct"])
             for r in json.loads((results_dir / "e6_0_swaps_locked.json").read_text(encoding="utf-8"))}
    sc, ex = cfg["sizing"], cfg["execution"]
    syms = [s for cls in cfg["universe"] for s in cfg["universe"][cls]]
    n = len(syms)

    # bars, spreads, conversion
    bars = {}
    for s in syms + [v[0] for v in USD_LEG.values() if v[0] in frames]:
        fr = frames[s]
        t = ints(fr.time_utc)
        keep = [i for i in range(len(t)) if server_date(t[i]) <= last_day]
        bars[s] = {"t": [t[i] for i in keep], "o": [float(fr.open.iat[i]) for i in keep], "h": [float(fr.high.iat[i]) for i in keep],
                   "l": [float(fr.low.iat[i]) for i in keep], "c": [float(fr.close.iat[i]) for i in keep]}

    def usd_per(ccy, t_ns):
        if ccy == "USD":
            return 1.0
        sym, usd_base = USD_LEG[ccy]
        b = bars[sym]
        j = bisect_right(b["t"], t_ns - 3600 * NS) - 1                # bars closed by t
        px = b["c"][max(j, 0)]
        return 1 / px if usd_base else px

    spread = {}
    for s in syms:
        vals = ticks[s]["p75_price_by_server_hour"]
        worst = max(v for v in vals if v is not None)
        spread[s] = [worst if v is None else v for v in vals]

    def hour_server(t_ns):
        return (datetime.fromtimestamp(t_ns // NS, NY).hour + 7) % 24

    # daily closes per market (weekday server dates) and signals
    daily = {}
    for s in syms:
        closes = {}
        for t, c in zip(bars[s]["t"], bars[s]["c"]):
            d = server_date(t)
            if d.weekday() < 5:
                closes[d] = c
        days = sorted(closes)
        cl = [closes[d] for d in days]
        rows = []
        for k in range(len(days)):
            signs = {L: (math.copysign(1, cl[k] - cl[k - L]) if cl[k] != cl[k - L] else 0.0) if k >= L else None
                     for L in (21, 63, 252)}
            sig = std([cl[j] - cl[j - 1] for j in range(k - 59, k + 1)]) if k >= 60 else None
            ok = k >= 252 and sig is not None and sig > 0
            if cfg.get("long_only"):
                f = 1.0
            else:
                f = sum(signs[L] for L in cfg["signal"]["lookbacks"]) / len(cfg["signal"]["lookbacks"]) if ok else 0.0
            rows.append({"day": days[k], "f": f if ok else 0.0, "sigma": sig, "ok": ok, "close": cl[k], "signs": signs})
        daily[s] = rows

    all_days = sorted({r["day"] for s in syms for r in daily[s]})
    pos_of_day = {d: i for i, d in enumerate(all_days)}
    group = {s: cfg["classes"][meta[s]["class"]] for s in syms}

    # daily $ change per lot for the covariance
    dollar = [[0.0] * n for _ in all_days]
    for i, s in enumerate(syms):
        rows = daily[s]
        for k in range(1, len(rows)):
            d = rows[k]["day"]
            dollar[pos_of_day[d]][i] = (rows[k]["close"] - rows[k - 1]["close"]) * meta[s]["contract_size"] * \
                usd_per(meta[s]["currency_profit"], ny_at(d, 17))

    def row_on(s, d):
        rows = daily[s]
        lo, hi = 0, len(rows)
        while lo < hi:
            mid = (lo + hi) // 2
            if rows[mid]["day"] <= d:
                lo = mid + 1
            else:
                hi = mid
        return rows[max(lo - 1, 0)]

    # event loop
    dec_time = {ny_at(d, ex["rollover_hour_ny"]): d for d in all_days}
    times = sorted(set(dec_time) | {t for s in syms for t in bars[s]["t"]})
    idx = {s: {t: j for j, t in enumerate(bars[s]["t"])} for s in syms}
    lots, avg, swp = [0.0] * n, [0.0] * n, [0.0] * n
    balance = float(sc["capital"])
    last_c, last_h = [None] * n, [0] * n
    pending = {}
    out_days, fills, ftmo_days = [], [], {}
    pday, pbase = None, None
    initial = cfg["ftmo"]["initial"]

    def comm(s, q, notional):
        c = cfg["commission"][meta[s]["class"]]
        return (q * c["usd_per_lot"] if "usd_per_lot" in c else notional * c["pct"] / 100) * ex["commission_mult"]

    for t in times:
        pd_ = datetime.fromtimestamp(t // NS, timezone.utc).astimezone(PRAGUE).date()
        if pd_ != pday:
            pday, pbase = pd_, balance
            ftmo_days[pday] = {"start_balance": balance, "min_equity": None, "breaches": []}
        ppu = [meta[s]["contract_size"] * usd_per(meta[s]["currency_profit"], t) for s in syms]
        if t in dec_time:
            d = dec_time[t]
            for i, s in enumerate(syms):
                if lots[i] != 0:
                    pct = swaps[s][0] if lots[i] > 0 else swaps[s][1]
                    mult = 3 if DAYNAMES[d.weekday()] == cfg["triple_swap_day"][meta[s]["class"]] else 1
                    stress = ex["swap_charge_mult"] if pct < 0 else 1.0
                    swp[i] += abs(lots[i]) * last_c[i] * ppu[i] * pct / 100 / cfg["swap_days_per_year"] * mult * stress
            rows = [row_on(s, d) for s in syms]
            ok = [rows[i]["ok"] and last_c[i] is not None for i in range(n)]
            f = [rows[i]["f"] if ok[i] else 0.0 for i in range(n)]
            marks = [(last_c[i] + spread[s][last_h[i]] * ex["spread_mult"] if lots[i] < 0 else last_c[i]) if last_c[i] is not None else 0.0
                     for i, s in enumerate(syms)]
            equity = balance + sum((marks[i] - avg[i]) * lots[i] * ppu[i] for i in range(n)) + sum(swp)
            active = sorted({group[s] for i, s in enumerate(syms) if ok[i]})
            unit = []
            for i, s in enumerate(syms):
                if ok[i]:
                    members = sum(1 for j, x in enumerate(syms) if ok[j] and group[x] == group[s])
                    budget = sc["target_vol"] * sc["capital"] / math.sqrt(252) / len(active) / members
                    unit.append(budget / (rows[i]["sigma"] * ppu[i]))
                else:
                    unit.append(0.0)
            want = [f[i] * unit[i] for i in range(n)]
            k = pos_of_day[d]
            win = dollar[max(0, k - sc["cov_days"] + 1):k + 1]
            var = 0.0
            if len(win) >= sc["cov_days"]:
                means = [sum(r[i] for r in win) / len(win) for i in range(n)]
                for a in range(n):
                    if want[a] == 0:
                        continue
                    for b in range(n):
                        if want[b] == 0:
                            continue
                        cab = sum((r[a] - means[a]) * (r[b] - means[b]) for r in win) / (len(win) - 1)
                        var += want[a] * want[b] * cab
            daily_budget = sc["target_vol"] * sc["capital"] / math.sqrt(252)
            scale = min(daily_budget / math.sqrt(var), sc["max_scaler"]) if var > 0 else 0.0
            margin_per = sum(abs(want[i]) * abs(last_c[i] or 0.0) * ppu[i] for i in range(n)) / sc["leverage"]
            if margin_per > 0:
                scale = min(scale, equity / margin_per)
            target = [w * scale for w in want]
            full = [x * scale for x in unit]
            new = []
            for i in range(n):
                if full[i] <= 0:
                    new.append(0.0 if lots[i] != 0 else lots[i])
                elif abs(target[i] - lots[i]) > sc["buffer"] * full[i]:
                    new.append(target[i])
                else:
                    new.append(lots[i])
            nxt = d + timedelta(days=3 if d.weekday() == 4 else 1)
            for i in range(n):
                if new[i] != lots[i]:
                    pending[i] = (new[i], ny_at(nxt, ex["fill_hour_ny"]))
                else:
                    pending.pop(i, None)
            out_days.append({"day": d, "equity": equity, **{f"f_{s}": f[i] for i, s in enumerate(syms)},
                             **{f"target_{s}": target[i] for i, s in enumerate(syms)},
                             **{f"new_{s}": new[i] for i, s in enumerate(syms)}})

        worst, seen = [None] * n, False
        for i, s in enumerate(syms):
            j = idx[s].get(t)
            if j is None:
                if last_c[i] is not None:
                    worst[i] = last_c[i] + spread[s][last_h[i]] * ex["spread_mult"] if lots[i] < 0 else last_c[i]
                continue
            seen = True
            b = bars[s]
            hr = hour_server(t)
            sp = spread[s][hr] * ex["spread_mult"]
            if i in pending and t >= pending[i][1]:
                tgt = pending.pop(i)[0]
                q, dq = lots[i], tgt - lots[i]
                slip = ex["slippage_ticks"] * meta[s]["tick_size"]
                px = b["o"][j] + sp + slip if dq > 0 else b["o"][j] - slip
                balance -= comm(s, abs(dq), abs(dq) * px * ppu[i])
                if q != 0 and (dq > 0) != (q > 0):
                    closed = min(abs(dq), abs(q))
                    balance += (1 if q > 0 else -1) * closed * (px - avg[i]) * ppu[i]
                    part = swp[i] * closed / abs(q)
                    balance += part
                    swp[i] -= part
                if tgt == 0:
                    avg[i] = 0.0
                elif q == 0 or (tgt > 0) != (q > 0):
                    avg[i] = px
                elif abs(tgt) > abs(q):
                    avg[i] = (abs(q) * avg[i] + abs(dq) * px) / abs(tgt)
                lots[i] = tgt
                fills.append({"symbol": s, "t": t, "lots_after": tgt, "price": px})
            worst[i] = b["l"][j] if lots[i] > 0 else (b["h"][j] + sp if lots[i] < 0 else b["c"][j])
            last_c[i], last_h[i] = b["c"][j], hr
        if seen:
            eq_low = balance + sum((worst[i] - avg[i]) * lots[i] * ppu[i] for i in range(n) if lots[i] != 0) + sum(swp)
            rec = ftmo_days[pday]
            rec["min_equity"] = eq_low if rec["min_equity"] is None else min(rec["min_equity"], eq_low)
            for rule, limit in (("max daily loss 5%", pbase - initial * cfg["ftmo"]["daily_loss_pct"] / 100),
                                ("max loss 10%", initial * (1 - cfg["ftmo"]["max_loss_pct"] / 100))):
                if eq_low < limit and rule not in rec["breaches"]:
                    rec["breaches"].append(rule)
    return pd.DataFrame(out_days), pd.DataFrame(fills), ftmo_days
