"""Experiment 7 meta-labeling layer M2 (spec v1.0 §5).

Plain English: before each year 2021..2025 we fit a logistic regression on the M1 trades that had
closed before 1 January of that year (label: net R > 0), then score that year's M1 trades. M2 keeps
a trade only if the predicted chance of a win is >= 0.40. Inputs are standardized with the training
trades' mean and standard deviation. L2 penalty C = 1.0 on the slopes (not the intercept), fitted by
Newton's method: the same objective as scikit-learn's default LogisticRegression, no tuning.
"""
import numpy as np
import pandas as pd

FEATURES = ["tstat", "box_height_atr_h1", "box_bars", "level_dist_r"]


def features(trades):
    """The four M2 inputs, all known at the setup. `trades` = engine trades (info_* columns)."""
    entry, stop_dist = trades.entry_price, trades.stop_distance
    level = (entry / 10).round() * 10
    return pd.DataFrame({"tstat": trades.info_tstat,
                         "box_height_atr_h1": (trades.info_box_high - trades.info_box_low) / trades.info_atr_h1,
                         "box_bars": trades.info_box_bars.astype(float),
                         "level_dist_r": (entry - level).abs() / stop_dist}, index=trades.index)


def fit_logistic(x, y, c=1.0, iters=100):
    """Weights [intercept, slopes...] minimising 0.5 * |slopes|^2 + C * sum(log-loss)."""
    X = np.column_stack([np.ones(len(x)), x])
    w = np.zeros(X.shape[1])
    pen = np.r_[0.0, np.ones(X.shape[1] - 1)] / c
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ w))
        grad = X.T @ (p - y) + pen * w
        hess = X.T @ (X * (p * (1 - p))[:, None]) + np.diag(pen)
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.abs(step).max() < 1e-10:
            break
    return w


def predict(w, x):
    return 1 / (1 + np.exp(-(w[0] + x @ w[1:])))


def walk_forward(trades, label, cfg):
    """P(win) for every trade entered in first_year..last_year (NaN before), each year fitted only on
    trades that closed before 1 January of that year. `label`: 1 = win, 0 = not (same index)."""
    m2 = cfg["m2"]
    x_all = features(trades)
    entry_year = trades.entry_utc.dt.tz_convert("Europe/London").dt.year
    prob = pd.Series(np.nan, index=trades.index)
    for year in range(m2["first_year"], m2["last_year"] + 1):
        jan1 = pd.Timestamp(f"{year}-01-01", tz="Europe/London").tz_convert("UTC")
        train = trades.exit_utc < jan1
        if train.sum() < len(FEATURES) + 2 or label[train].nunique() < 2:
            continue                                  # nothing to learn from yet: no prediction
        mu, sd = x_all[train].mean(), x_all[train].std(ddof=0).replace(0, 1.0)
        w = fit_logistic(((x_all[train] - mu) / sd).to_numpy(), label[train].to_numpy(float), m2["l2_c"])
        now = entry_year == year
        prob[now] = predict(w, ((x_all[now] - mu) / sd).to_numpy())
    return prob


def keep(prob, cfg):
    """M2's decision for trades with a prediction (NaN prob -> not part of the M2 comparison)."""
    return prob >= cfg["m2"]["threshold"]
