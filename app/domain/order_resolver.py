from __future__ import annotations

from typing import Protocol


class OrderNoLookup(Protocol):
    def lookup_order_by_no(self, order_no: str) -> tuple[int, int]: ...


def is_order_no(s: str) -> bool:
    return s.startswith("DD")


def parse_order_key(key: str) -> tuple[str, int | None]:
    if key.isdigit():
        return ("numeric", int(key))
    if is_order_no(key):
        return ("order_no", None)
    raise ValueError(f"Invalid order key: {key}")


def resolve_order_key(key: str) -> tuple[int, int | None]:
    kind, value = parse_order_key(key)
    if kind == "numeric":
        return (value, None)
    raise ValueError("Order number requires database lookup; use resolve_order_no")


def resolve_order_no(db: OrderNoLookup, order_no: str) -> tuple[int, int]:
    if not is_order_no(order_no):
        raise ValueError(f"Not an order number: {order_no}")
    return db.lookup_order_by_no(order_no)
