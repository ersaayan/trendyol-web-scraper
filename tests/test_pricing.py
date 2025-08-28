from __future__ import annotations

from src.analysis.pricing import (
    ShippingTier,
    normalize_tiers,
    break_even,
    shipping_fee,
    profit,
)


def test_break_even_two_tiers():
    tiers = normalize_tiers([(150.0, 42.70), (300.0, 72.20)])
    # cost 100, commission 10%
    be = break_even(cost=100.0, commission_rate_percent=10.0, tiers=tiers)
    # In tier2: (100 + 72.20) / 0.9 = 191.333...
    assert 191.0 < be < 192.0


def test_shipping_fee_edges():
    tiers = normalize_tiers([(150.0, 42.70), (300.0, 72.20)])
    assert shipping_fee(149.99, tiers) == 42.70
    assert shipping_fee(150.0, tiers) == 72.20
    assert shipping_fee(299.99, tiers) == 72.20
    assert shipping_fee(300.0, tiers) == 72.20


def test_profit_sign():
    tiers = normalize_tiers([(150.0, 42.70), (300.0, 72.20)])
    p = profit(price=200.0, cost=100.0, commission_rate_percent=10.0, tiers=tiers)
    assert round(p, 2) == round(200 - 72.20 - 20 - 100, 2)
