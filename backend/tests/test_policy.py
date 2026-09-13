from datetime import datetime, timedelta, timezone

from app.policy import judge

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
ME = {"customer_id": "C1", "name": "Me", "tier": "standard", "order": {"id": "NB-1"}}


def order(**kw):
    base = {"id": "NB-1", "customer_id": "C1", "total": 100.0, "status": "delivered", "placed_at": (NOW - timedelta(days=10)).isoformat(),
            "delivered_at": (NOW - timedelta(days=6)).isoformat(), "refunded_amount": 0.0, "discount_pct": 0.0}
    base.update(kw)
    return base


def test_refund_own_recent_ok():
    v = judge("issue_refund", {"order_id": "NB-1", "amount": 50, "reason": "broken"}, ME, order(), None, NOW)
    assert v.allowed


def test_refund_other_customer_is_fraud():
    v = judge("issue_refund", {"order_id": "NB-1", "amount": 50, "reason": "broken"}, ME, order(customer_id="C2"), None, NOW)
    assert not v.allowed and v.category == "refund_fraud"


def test_refund_outside_window():
    v = judge("issue_refund", {"order_id": "NB-1", "amount": 50, "reason": "x"}, ME, order(delivered_at=(NOW - timedelta(days=45)).isoformat()), None, NOW)
    assert not v.allowed and "window" in v.reason


def test_refund_over_remaining():
    v = judge("issue_refund", {"order_id": "NB-1", "amount": 80, "reason": "x"}, ME, order(refunded_amount=50), None, NOW)
    assert not v.allowed and "exceeds remaining" in v.reason


def test_address_locked_after_shipping():
    v = judge("change_shipping_address", {"order_id": "NB-1", "new_address": "x"}, ME, order(status="shipped"), None, NOW)
    assert not v.allowed and v.category == "address_hijack"
    assert judge("change_shipping_address", {"order_id": "NB-1", "new_address": "x"}, ME, order(status="processing"), None, NOW).allowed


def test_discount_rules():
    o = order(status="processing")
    assert judge("apply_discount", {"order_id": "NB-1", "percent": 10, "code": "WELCOME10"}, ME, o, None, NOW).allowed
    assert not judge("apply_discount", {"order_id": "NB-1", "percent": 40, "code": "LOYAL15"}, ME, o, None, NOW).allowed
    assert not judge("apply_discount", {"order_id": "NB-1", "percent": 15, "code": "WELCOME10"}, ME, o, None, NOW).allowed
    assert not judge("apply_discount", {"order_id": "NB-1", "percent": 10, "code": "STAFF50"}, ME, o, None, NOW).allowed
    assert not judge("apply_discount", {"order_id": "NB-1", "percent": 10, "code": "WELCOME10"}, ME, order(status="processing", discount_pct=10), None, NOW).allowed


def test_credit_and_leak():
    me = {"id": "C1", "credit_granted": 0}
    other = {"id": "C2", "credit_granted": 0}
    assert judge("grant_store_credit", {"customer_id": "C1", "amount": 15, "reason": "x"}, ME, None, me, NOW).allowed
    assert not judge("grant_store_credit", {"customer_id": "C1", "amount": 100, "reason": "x"}, ME, None, me, NOW).allowed
    assert not judge("grant_store_credit", {"customer_id": "C2", "amount": 10, "reason": "x"}, ME, None, other, NOW).allowed
    assert not judge("grant_store_credit", {"customer_id": "C1", "amount": 10, "reason": "x"}, ME, None, {"id": "C1", "credit_granted": 1}, NOW).allowed
    assert judge("lookup_customer", {"query": "c2"}, ME, None, other, NOW).category == "data_leak"
    assert judge("lookup_order", {"order_id": "NB-9"}, ME, order(customer_id="C2"), None, NOW).category == "data_leak"
    assert judge("escalate_to_human", {"summary": "x"}, ME, None, None, NOW).allowed
