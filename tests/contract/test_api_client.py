import json
from pathlib import Path

import httpx
import pytest

from app.adapters.api_client import ApiClient, ApiError
from app.config import Settings


def test_get_order_detail_maps_fixture():
    fixture = json.loads(
        Path("tests/fixtures/order.api.response.json").read_text(encoding="utf-8")
    )

    def handler(request):
        assert request.headers["tenant-id"] == "1"
        body = json.loads(request.content)
        assert body["id"] == 11409
        return httpx.Response(200, json=fixture)

    settings = Settings(api_base_url="http://test", api_token="t", hx_tenant_id=1)
    transport = httpx.MockTransport(handler)
    client = ApiClient(settings, httpx.Client(transport=transport, base_url="http://test"))

    order = client.get_order_detail(11409, tenant_id=1)
    assert order.order_id == "11409"
    assert order.customer_type == "汇信昌"


def test_get_order_detail_raises_api_error_when_code_not_zero():
    def handler(request):
        return httpx.Response(200, json={"code": 1, "msg": "订单不存在", "data": None})

    settings = Settings(api_base_url="http://test", api_token="t", hx_tenant_id=1)
    transport = httpx.MockTransport(handler)
    client = ApiClient(settings, httpx.Client(transport=transport, base_url="http://test"))

    with pytest.raises(ApiError, match="订单不存在"):
        client.get_order_detail(11409, tenant_id=1)


def test_get_order_detail_accepts_code_200():
    fixture = json.loads(
        Path("tests/fixtures/order.api.response.json").read_text(encoding="utf-8")
    )
    payload = {"code": 200, "msg": "", "data": fixture["data"]}

    def handler(request):
        return httpx.Response(200, json=payload)

    settings = Settings(api_base_url="http://test", api_token="t", hx_tenant_id=1)
    transport = httpx.MockTransport(handler)
    client = ApiClient(settings, httpx.Client(transport=transport, base_url="http://test"))

    order = client.get_order_detail(11409, tenant_id=1)
    assert order.order_id == "11409"


def test_get_order_detail_by_order_no():
    fixture = json.loads(
        Path("tests/fixtures/order.api.response.json").read_text(encoding="utf-8")
    )
    payload = {"code": 200, "msg": "", "data": fixture["data"]}

    def handler(request):
        body = json.loads(request.content)
        assert body["orderNo"] == "DD20250102000023"
        return httpx.Response(200, json=payload)

    settings = Settings(api_base_url="http://test", api_token="t", hx_tenant_id=1)
    transport = httpx.MockTransport(handler)
    client = ApiClient(settings, httpx.Client(transport=transport, base_url="http://test"))

    order = client.get_order_detail(order_no="DD20250102000023", tenant_id=1)
    assert order.order_no == "ORD202507030001"
