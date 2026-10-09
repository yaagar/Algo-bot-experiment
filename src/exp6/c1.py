"""C1 random direction for Experiment 6 (spec §7).

Per market, every time the real forecast changes sign (including to or from 0), a fresh coin decides
the sign for that stretch: f_C1 = coin x f. Magnitudes, timing, sizing and costs stay identical
(the C1 forecasts go through the same engine). Metric later: net total return; 1,000 seeds.
"""
import numpy as np


def c1_forecasts(signals, symbols, seed):
    rng = np.random.default_rng(seed)
    out = {}
    for sym, s in zip(symbols, signals):
        f = s.f.to_numpy()
        sign = np.sign(f)
        new_stretch = np.r_[True, sign[1:] != sign[:-1]]
        coins = rng.choice([-1.0, 1.0], size=int(new_stretch.sum()))
        out[sym] = f * coins[np.cumsum(new_stretch) - 1]
    return out
