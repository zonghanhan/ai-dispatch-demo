"""Smoke test: candidate master SQL (mock fixture count or live DB query)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.adapters.db_client import DbClient
from app.config import Settings
from app.domain.models import Order


def _fixture_order() -> Order:
    return Order(
        order_id="11409",
        biz_type=2,
        customer_type="汇信昌",
        tenant_id=1,
        city="深圳市",
        erp_codes=["PL010104"],
        service_type_code="LX002",
    )


def main() -> int:
    settings = Settings()
    client = DbClient(settings)
    order = _fixture_order()

    print(f"MOCK_MODE={settings.mock_mode}")
    print(f"Sample order: city={order.city!r}, erp_codes={order.erp_codes}")

    if settings.mock_mode:
        count = len(client.list_candidate_masters(order))
        print(f"Fixture candidate count: {count}")
        return 0

    if not settings.db_host or not settings.db_user:
        print("DB credentials missing (DB_HOST / DB_USER); set MOCK_MODE=true to use fixtures.", file=sys.stderr)
        return 1

    try:
        masters = client.list_candidate_masters(order)
    except Exception as exc:
        print(f"DB query failed: {exc}", file=sys.stderr)
        return 1

    print(f"Live candidate count: {len(masters)}")
    if masters:
        sample = masters[0]
        print(
            f"  first: master_id={sample.master_id}, "
            f"name={sample.master_name!r}, city={sample.service_city!r}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
