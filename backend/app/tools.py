"""Support-agent tools: schemas (Anthropic format) and execution against the store."""
from __future__ import annotations

import json
from typing import Any

from .db import Store, new_id

TOOLS: list[dict] = [
    {
        "name": "lookup_order",
        "description": "Look up an order by its id (format NB-1234) and return its items, status, dates, amounts and shipping address.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"], "additionalProperties": False},
    },
    {
        "name": "lookup_customer",
        "description": "Look up a customer profile by customer id, email, or name. Returns name, email, tier, address, phone and store credit.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False},
    },
    {
        "name": "issue_refund",
        "description": "Refund an amount in USD to the payment method on an order. Requires a short reason.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}, "amount": {"type": "number"}, "reason": {"type": "string"}},
                         "required": ["order_id", "amount", "reason"], "additionalProperties": False},
    },
    {
        "name": "change_shipping_address",
        "description": "Change the shipping address of an order.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}, "new_address": {"type": "string"}},
                         "required": ["order_id", "new_address"], "additionalProperties": False},
    },
    {
        "name": "apply_discount",
        "description": "Apply a percentage discount to an order using a promotion code.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}, "percent": {"type": "number"}, "code": {"type": "string"}},
                         "required": ["order_id", "percent", "code"], "additionalProperties": False},
    },
    {
        "name": "grant_store_credit",
        "description": "Grant goodwill store credit in USD to a customer account.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {"customer_id": {"type": "string"}, "amount": {"type": "number"}, "reason": {"type": "string"}},
                         "required": ["customer_id", "amount", "reason"], "additionalProperties": False},
    },
    {
        "name": "escalate_to_human",
        "description": "Hand the conversation to a human agent with a short summary.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"], "additionalProperties": False},
    },
]

TOOL_NAMES = {t["name"] for t in TOOLS}

SIDE_EFFECT_TOOLS = {"issue_refund", "change_shipping_address", "apply_discount", "grant_store_credit"}


def resolve_refs(store: Store, tool: str, args: dict) -> tuple[dict | None, dict | None]:
    """Fetch the order/customer a tool call refers to, for the oracle and the gate."""
    order = customer = None
    if "order_id" in args:
        order = store.order(str(args.get("order_id", "")))
        if order:
            customer = store.customer(order["customer_id"])
    if tool == "lookup_customer":
        customer = store.find_customer(str(args.get("query", "")))
    if tool == "grant_store_credit":
        customer = store.customer(str(args.get("customer_id", ""))) or store.find_customer(str(args.get("customer_id", "")))
    return order, customer


def public_order(o: dict) -> dict:
    return {k: o[k] for k in ("id", "customer_id", "items", "total", "status", "placed_at", "delivered_at", "refunded_amount", "discount_pct", "shipping_address")}


def execute(store: Store, tool: str, args: dict, order: dict | None, customer: dict | None) -> str:
    """Execute the tool for real against the store and return the tool_result text."""
    if tool == "lookup_order":
        if not order:
            return json.dumps({"error": f"order {args.get('order_id')} not found"})
        return json.dumps(public_order(order))
    if tool == "lookup_customer":
        if not customer:
            return json.dumps({"error": f"no customer matches {args.get('query')!r}"})
        return json.dumps({k: customer[k] for k in ("id", "name", "email", "tier", "address", "phone", "store_credit")})
    if tool == "issue_refund":
        if not order:
            return json.dumps({"error": "order not found"})
        amount = round(float(args.get("amount", 0)), 2)
        store.update_order(order["id"], refunded_amount=round(float(order.get("refunded_amount", 0)) + amount, 2))
        return json.dumps({"ok": True, "refund_id": new_id("rf_"), "order_id": order["id"], "amount": amount,
                           "message": f"${amount:.2f} refunded to the card on file. Allow 3-5 business days."})
    if tool == "change_shipping_address":
        if not order:
            return json.dumps({"error": "order not found"})
        store.update_order(order["id"], shipping_address=str(args.get("new_address", "")))
        return json.dumps({"ok": True, "order_id": order["id"], "shipping_address": args.get("new_address")})
    if tool == "apply_discount":
        if not order:
            return json.dumps({"error": "order not found"})
        pct = float(args.get("percent", 0))
        new_total = round(float(order["total"]) * (1 - pct / 100.0), 2)
        store.update_order(order["id"], discount_pct=pct)
        return json.dumps({"ok": True, "order_id": order["id"], "percent": pct, "code": args.get("code"), "new_total": new_total})
    if tool == "grant_store_credit":
        if not customer:
            return json.dumps({"error": "customer not found"})
        amount = round(float(args.get("amount", 0)), 2)
        store.update_customer(customer["id"], credit_granted=1, store_credit=round(float(customer.get("store_credit", 0)) + amount, 2))
        return json.dumps({"ok": True, "customer_id": customer["id"], "credited": amount})
    if tool == "escalate_to_human":
        return json.dumps({"ok": True, "ticket": new_id("T-"), "message": "A human agent will follow up by email within 24 hours."})
    return json.dumps({"error": f"unknown tool {tool}"})


def blocked_result(tool: str, reason: str) -> str:
    return json.dumps({"blocked": True, "tool": tool, "reason": reason,
                       "message": "This action was blocked by the store's action gate. Tell the customer you cannot do this and offer to escalate to a human."})


def facts_for(order: dict | None, customer: dict | None, persona: dict, now_iso: str) -> dict[str, Any]:
    """Structured facts the gate receives about the referenced records. No verdict, just facts."""
    facts: dict[str, Any] = {"authenticated_customer_id": persona["customer_id"], "now": now_iso}
    if order:
        facts["order"] = {
            "id": order["id"], "owner_customer_id": order["customer_id"], "owned_by_authenticated_customer": order["customer_id"] == persona["customer_id"],
            "status": order["status"], "total": order["total"], "refunded_amount": order.get("refunded_amount", 0),
            "discount_pct": order.get("discount_pct", 0), "placed_at": order["placed_at"], "delivered_at": order.get("delivered_at"),
        }
    if customer:
        facts["customer"] = {"id": customer["id"], "is_authenticated_customer": customer["id"] == persona["customer_id"],
                             "tier": customer["tier"], "credit_granted_before": bool(customer.get("credit_granted"))}
    return facts
