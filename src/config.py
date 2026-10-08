"""Load config/settings.yaml."""
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"


def load_settings(path=SETTINGS_PATH):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def commission_per_lot(settings):
    """Round-turn commission in USD per lot. Refuses to guess if it is still a placeholder."""
    value = settings["costs"]["commission_per_lot_round_turn_usd"]
    if value is None:
        raise ValueError(
            "Commission is still a placeholder in config/settings.yaml "
            "(costs.commission_per_lot_round_turn_usd). Ask Yash for FTMO's real value."
        )
    return float(value)
