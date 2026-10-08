"""The Experiment 3 markets (docs/EXPERIMENT_3_SPEC.md §3) and their base commission (§4).

Symbols are matched by name stem, so a broker suffix such as ".sim" is detected, not assumed.
A market with no matching symbol is skipped and reported — never substituted (§3).
"""
from dataclasses import dataclass

from src.config import PROJECT_ROOT

RAW = PROJECT_ROOT / "data" / "raw" / "exp3"
PROCESSED = PROJECT_ROOT / "data" / "processed" / "exp3"
RESULTS = PROJECT_ROOT / "results" / "exp3"
SPECS_PATH = RESULTS / "market_specs.json"        # symbol info + costs recorded in E3-1 (in git)


@dataclass(frozen=True)
class MarketDef:
    name: str
    stems: tuple                      # broker name stems to look for, in order of preference
    asset_class: str
    commission_pct: float = 0.0       # % of notional per side
    commission_per_lot_usd: float = 0.0   # $ per lot per side


# Spec §4 base commission: metals 0.0007% of notional, FX $2.50/lot, indices $0, oil 0.001% (all per side)
MARKETS = [
    MarketDef("Gold", ("XAUUSD", "GOLD"), "Metals", commission_pct=0.0007),
    MarketDef("Silver", ("XAGUSD", "SILVER"), "Metals", commission_pct=0.0007),
    MarketDef("WTI crude oil", ("USOIL", "WTI", "XTIUSD", "USOUSD", "CL"), "Oil", commission_pct=0.001),
    MarketDef("S&P 500", ("US500", "SPX500", "SP500", "USA500"), "Indices"),
    MarketDef("Nasdaq 100", ("US100", "NAS100", "USTEC", "NDX100"), "Indices"),
    MarketDef("Germany 40", ("GER40", "DE40", "DAX40", "GER30", "DE30"), "Indices"),
    MarketDef("Japan 225", ("JP225", "JPN225", "NIKKEI", "N225"), "Indices"),
    MarketDef("EURUSD", ("EURUSD",), "FX", commission_per_lot_usd=2.50),
    MarketDef("USDJPY", ("USDJPY",), "FX", commission_per_lot_usd=2.50),
    MarketDef("AUDUSD", ("AUDUSD",), "FX", commission_per_lot_usd=2.50),
]


def find_symbol(market, broker_names):
    """The broker symbol for a market: exact stem first, then stem + suffix (e.g. 'US500.sim'). None if absent."""
    for stem in market.stems:
        exact = [n for n in broker_names if n.upper() == stem]
        suffixed = sorted(n for n in broker_names if n.upper().startswith(stem + "."))
        if exact or suffixed:
            return (exact + suffixed)[0]
    return None
