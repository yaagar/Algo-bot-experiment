"""Experiment 7 exit variant M1-TS (spec v1.1 §6): break-even, then a trailing stop, no target.

Plain English: entries are exactly M1's. After each M15 bar closes while a trade is open,
`TrailRule.update` looks at that close:
  * not yet at break-even: if the trade shows >= +1R at the exit-side price, the stop jumps to
    entry +/- commission for both sides (true break-even) and the trail switches on;
  * trail on: stop = max(stop, best bid close since entry - 1.5 x ATR(14, M15)) for longs (mirror
    for shorts) — it only ever tightens.
The new stop is used from the next bar (the engine checks M1 bars of bar i before the close of
bar i is looked at). Exits: the stop on M1 bars (stop first, gap = bar open) or 20:00 London.
Results stay in R of the INITIAL risk: TSEngine records the initial stop and fixes net R after
the base engine's close (which would otherwise divide by the moved stop).

The same rule drives the C1 / C2 control trades through `simulate_one` (one trade on its own).
"""
from src.exp2.engine import Costs
from src.exp2.market import to_ns
from src.exp4.system import NO_SWAP, E4Engine
from src.exp7.pattern import M15, wilder_atr
from src.exp7.system import Exp7Strategy, find_setups


class TrailRule:
    def __init__(self, data, cfg, spread_mult=1.0):
        b = data.m15
        self.t_open = to_ns(b.time_utc)
        self.open = b.open.to_numpy(float)
        self.close = b.close.to_numpy(float)
        self.atr = wilder_atr(b.high.to_numpy(float), b.low.to_numpy(float), self.close, cfg["atr_bars"])
        self.base_spread = data.spread(b)                # the engine applies its own spread multiplier
        self.spread = self.base_spread * spread_mult
        self.trigger = cfg["ts"]["be_trigger_r"]
        self.trail = cfg["ts"]["trail_atr"]
        self.comm = cfg["commission_pct_per_side"] / 100
        self.paths = {}                                  # entry_ns -> [(bar close ns, stop)] for the rebuild check

    def start(self, pos):
        info = pos.order.info
        info.update(initial_stop=pos.stop, stop_kind="initial", best_close=None)
        self.paths[pos.entry_ns] = [(pos.entry_ns, pos.stop)]

    def update(self, pos, i):
        """Bar i has closed with the trade still open: move the stop for bar i+1 onwards."""
        info, d = pos.order.info, pos.order.direction
        c = self.close[i]
        info["best_close"] = c if info["best_close"] is None else (max if d > 0 else min)(info["best_close"], c)
        r0 = abs(pos.entry_price - info["initial_stop"])
        if info["stop_kind"] == "initial":
            exit_side = c if d > 0 else c + self.spread[i]
            if d * (exit_side - pos.entry_price) >= self.trigger * r0:
                be = pos.entry_price + d * 2 * self.comm * pos.entry_price
                pos.stop = max(pos.stop, be) if d > 0 else min(pos.stop, be)
                info["stop_kind"] = "breakeven"
        if info["stop_kind"] != "initial":
            trail = info["best_close"] - d * self.trail * self.atr[i]
            if d * (trail - pos.stop) > 0:
                pos.stop = trail
                info["stop_kind"] = "trailing"
        self.paths[pos.entry_ns].append((int(self.t_open[i] + M15.value), pos.stop))


class TSStrategy(Exp7Strategy):
    """M1's setups and entries; no target; the stop is managed by TrailRule at each M15 close."""

    def __init__(self, data, setups, cfg, rule):
        super().__init__(data, setups, cfg)
        self.rule = rule

    def signal(self, i):
        order = super().signal(i)
        if order is not None:
            order.target_r = None
        return order

    def exit_signal(self, i, pos):
        if "initial_stop" not in pos.order.info:
            self.rule.start(pos)
        self.rule.update(pos, i)
        return False


class TSEngine(E4Engine):
    """E4Engine whose trades report R of the initial risk (the stop moves during the trade)."""

    def close(self, pos, exit_ns, price, reason, res):
        super().close(pos, exit_ns, price, reason, res)
        t = res.trades[-1]
        init = pos.order.info.get("initial_stop", pos.stop)
        risk = abs(pos.entry_price - init) * pos.lots * self.cs
        t["net_r"], t["gross_r"] = t["net_usd"] / risk, t["gross_usd"] / risk
        t["initial_stop"], t["stop_distance"] = init, abs(pos.entry_price - init)
        kind = pos.order.info.get("stop_kind", "initial")
        t["exit_type"] = {"initial": "initial stop", "breakeven": "break-even",
                          "trailing": "trailing stop"}[kind] if reason == "stop" else "time exit" if reason == "time" else reason


def make_ts_engine(data, cfg, spread_mult=1.0, slippage_ticks=0):
    costs = Costs(spread_mult, cfg["commission_pct_per_side"])
    return TSEngine(data.m1, data.events, costs, NO_SWAP, risk_usd=cfg["risk_usd"], contract=cfg["contract_size"],
                    blackout_min=cfg["news_blackout_min"], weekend_rule=False, slippage=slippage_ticks * cfg["tick_size"])


def run_ts_system(data, cfg, spread_mult=1.0, slippage_ticks=0, setups=None):
    """M1-TS on the M1 setups. Returns (engine Result, trades, setups, rule). Trades hold outcomes."""
    from src.exp2.engine import trades_frame
    if setups is None:
        setups = find_setups(data, cfg)[1]
    engine = make_ts_engine(data, cfg, spread_mult, slippage_ticks)
    rule = TrailRule(data, cfg, spread_mult)
    res = engine.run(TSStrategy(data, setups, cfg, rule))
    return res, trades_frame(res), setups, rule


def simulate_one(engine, rule, order, fill_bar, res):
    """One control trade on its own: fill at M15 bar `fill_bar`'s open, then bar by bar: M1 exits
    inside the bar, stop update at its close (same TrailRule as the real system)."""
    t_open = rule.t_open
    pos = engine.open_position(order, int(t_open[fill_bar]), float(rule.open[fill_bar]),
                               float(rule.base_spread[fill_bar]), res)
    if pos is None:
        return
    rule.start(pos)
    for i in range(fill_bar, len(t_open)):
        nxt = int(t_open[i + 1]) if i + 1 < len(t_open) else int(t_open[i] + M15.value)
        ex = engine.walk(pos, int(t_open[i]), nxt)
        if ex:
            engine.close(pos, *ex, res)
            return
        rule.update(pos, i)
    engine.close(pos, *engine.end_of_data(pos), res)
