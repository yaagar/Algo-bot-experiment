"""Trade profit/loss formula used by the backtester (spec §5)."""
from src.config import commission_usd


def gross_pnl_usd(direction, entry_price, exit_price, lots, contract_size):
    """direction +1 = long (bought at entry), -1 = short. Account currency is USD."""
    return direction * (exit_price - entry_price) * lots * contract_size


def trade_costs_usd(entry_price, exit_price, lots, contract_size, commission_pct_per_side):
    """Commission on both fills (spread is already inside the bid/ask fill prices)."""
    return (commission_usd(lots, entry_price, contract_size, commission_pct_per_side)
            + commission_usd(lots, exit_price, contract_size, commission_pct_per_side))
