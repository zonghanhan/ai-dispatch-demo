import json
from pathlib import Path

from app.config import Settings
from app.domain.mapping import (
    biz_type_to_service_code,
    map_api_order,
    mask_address,
    resolve_customer_type,
)


def test_biz_type_to_service_code():
    assert biz_type_to_service_code(2) == "LX002"
    assert biz_type_to_service_code(4) == "LX003"


def test_resolve_customer_type():
    s = Settings(hx_tenant_id=1)
    assert resolve_customer_type(1, s) == "汇信昌"
    assert resolve_customer_type(2, s) == "非汇信昌"


def test_map_api_order_from_fixture():
    raw = json.loads(
        Path("tests/fixtures/order.api.response.json").read_text(encoding="utf-8")
    )
    s = Settings(hx_tenant_id=1)
    order = map_api_order(raw["data"], s)
    assert order.order_id == "11409"
    assert order.customer_type == "汇信昌"
    assert order.lng == raw["data"]["lon"]
    assert "erp_codes" in order.model_dump()


def test_mask_address():
    assert mask_address("上海市", "浦东新区", "示例路100号") == "上海市浦东新区***"
