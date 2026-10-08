"""Load config/settings.yaml and small helpers that read it."""
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"


def load_settings(path=SETTINGS_PATH):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def commission_usd(lots, price, contract_size, pct_per_side):
    """Commission for ONE side (one fill) of a trade, in USD.

    FTMO charges a percentage of the trade's value on every fill, so a full
    trade (entry + exit) pays this twice — once at each fill price.
    Example: 0.1 lot x 100 oz x $4,106.91 x 0.0007% = $0.29.
    """
    notional = lots * contract_size * price
    return notional * pct_per_side / 100
