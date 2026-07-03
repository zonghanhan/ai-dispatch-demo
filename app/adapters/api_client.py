from __future__ import annotations

import httpx

from app.config import Settings
from app.domain.mapping import map_api_order
from app.domain.models import Order


class ApiError(Exception):
    def __init__(self, msg: str) -> None:
        self.msg = msg
        super().__init__(msg)


def _is_api_success(code) -> bool:
    return code in (0, 200)


class ApiClient:
    def __init__(self, settings: Settings, http_client: httpx.Client) -> None:
        self._settings = settings
        self._http = http_client

    def get_order_detail(
        self,
        order_id: int | None = None,
        *,
        tenant_id: int,
        order_no: str | None = None,
    ) -> Order:
        if order_no:
            body: dict = {"orderNo": order_no}
        elif order_id is not None:
            body = {"id": order_id}
        else:
            raise ApiError("order_id or order_no required")

        url = f"{self._settings.api_base_url.rstrip('/')}{self._settings.api_order_path}"
        headers = {
            "Authorization": f"Bearer {self._settings.api_token}",
            self._settings.api_tenant_header: str(tenant_id),
        }
        response = self._http.post(
            url,
            json=body,
            headers=headers,
            timeout=self._settings.api_timeout_sec,
        )
        response.raise_for_status()
        payload = response.json()
        if not _is_api_success(payload.get("code")):
            raise ApiError(payload.get("msg") or "API error")
        data = payload.get("data")
        if not data:
            raise ApiError(payload.get("msg") or "Order not found")
        return map_api_order(data, self._settings)
