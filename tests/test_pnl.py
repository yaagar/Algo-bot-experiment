from src.pnl import gross_pnl_usd, trade_costs_usd


def test_long_loss_matches_real_demo_trade():
    # 0.10 lot long 4106.91 -> 4106.65, broker booked -2.60
    assert round(gross_pnl_usd(+1, 4106.91, 4106.65, 0.10, 100), 2) == -2.60


def test_short_loss_matches_real_demo_trade():
    # 0.01 lot short 4111.48 -> 4111.53, broker booked -0.05
    assert round(gross_pnl_usd(-1, 4111.48, 4111.53, 0.01, 100), 2) == -0.05


def test_one_r_loss_is_fifty_dollars():
    # $50 risk: 0.25 lot with a $2.00 stop on 100 oz contracts
    assert gross_pnl_usd(+1, 2000.00, 1998.00, 0.25, 100) == -50


def test_costs_charge_both_sides():
    # 0.10 lot at ~4106.8: each side ~0.29 at 0.0007%
    assert round(trade_costs_usd(4106.91, 4106.65, 0.10, 100, 0.0007), 2) == 0.57
