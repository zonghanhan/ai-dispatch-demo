"""Smoke test: order detail API (read .env, resolve order_no, print summary)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.adapters.api_client import ApiClient, ApiError
from app.adapters.db_client import DbClient
from app.config import Settings
from app.domain.mapping import map_api_order
from app.domain.models import Order
from app.domain.order_resolver import is_order_no, resolve_order_no


def _order_summary(order: Order) -> dict:
    return {
        "order_id": order.order_id,
        "order_no": order.order_no,
        "biz_type": order.biz_type,
        "biz_type_name": order.biz_type_name,
        "customer_type": order.customer_type,
        "tenant_id": order.tenant_id,
        "city": order.city,
        "category": order.category,
        "service_type_code": order.service_type_code,
        "erp_codes": order.erp_codes,
        "urgent": order.urgent,
        "status": order.status,
        "address_masked": order.address_masked,
    }


def _load_fixture_order(settings: Settings) -> Order:
    fixture_path = ROOT / "tests" / "fixtures" / "order.api.response.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return map_api_order(payload["data"], settings)


def _resolve_ids(settings: Settings) -> tuple[int, int]:
    if settings.test_order_id.strip():
        return int(settings.test_order_id), settings.hx_tenant_id

    order_no = settings.test_order_no.strip()
    if is_order_no(order_no):
        db = DbClient(settings)
        order_id, tenant_id = resolve_order_no(db, order_no)
        print(f"Resolved {order_no} -> id={order_id}, tenant_id={tenant_id}")
        return order_id, tenant_id

    raise ValueError(
        f"Set TEST_ORDER_ID or a DD-prefixed TEST_ORDER_NO (got {order_no!r})"
    )


def main() -> int:
    settings = Settings()
    print(f"MOCK_MODE={settings.mock_mode}")

    if settings.mock_mode:
        order = _load_fixture_order(settings)
        print("[mock] Loaded order from tests/fixtures/order.api.response.json")
    else:
        try:
            order_id, tenant_id = _resolve_ids(settings)
        except Exception as exc:
            print(f"Order resolve failed: {exc}", file=sys.stderr)
            return 1

        http = httpx.Client()
        try:
            api = ApiClient(settings, http)
            order_no = settings.test_order_no.strip() if is_order_no(settings.test_order_no.strip()) else None
            try:
                order = api.get_order_detail(order_id=order_id, tenant_id=tenant_id)
            except ApiError:
                if order_no:
                    order = api.get_order_detail(order_no=order_no, tenant_id=tenant_id)
                else:
                    raise
        except (ApiError, httpx.HTTPError) as exc:
            print(f"API call failed: {exc}", file=sys.stderr)
            return 1
        finally:
            http.close()

    summary = _order_summary(order)
    print("\n--- Order Summary ---")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    if not settings.test_order_id.strip():
        print(f"\nTip: add TEST_ORDER_ID={order.order_id} to .env to skip DB lookup.")
    else:
        print(f"\nTEST_ORDER_ID already set ({settings.test_order_id}).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
