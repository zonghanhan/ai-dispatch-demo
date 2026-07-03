from __future__ import annotations

import json
from pathlib import Path

from app.adapters.api_client import ApiClient, ApiError
from app.adapters.db_client import DbClient
from app.config import Settings
from app.domain.guard import assert_tool_allowed
from app.domain.mapping import map_api_order
from app.domain.models import MasterCandidate, Order
from app.domain.order_resolver import is_order_no, resolve_order_key, resolve_order_no
from app.domain.score import rank_masters


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _order_tool_output(order: Order) -> dict:
    return {
        "order_id": order.order_id,
        "order_no": order.order_no,
        "biz_type": order.biz_type,
        "biz_type_name": order.biz_type_name,
        "customer_type": order.customer_type,
        "category": order.category,
        "lat": order.lat,
        "lng": order.lng,
        "address_masked": order.address_masked,
        "urgent": order.urgent,
        "status": order.status,
    }


def _invalid_tool_response(codes: list[str]) -> dict:
    return {"error": "invalid_tool_call", "codes": codes}


class ToolGateway:
    def __init__(
        self,
        settings: Settings,
        api_client: ApiClient,
        db_client: DbClient,
    ) -> None:
        self._settings = settings
        self._api = api_client
        self._db = db_client

    def execute(self, tool_name: str, tool_input: dict, session_state: dict) -> dict:
        ok, codes = assert_tool_allowed(tool_name, self._settings.dispatch_phase)
        if not ok:
            return _invalid_tool_response(codes)

        handlers = {
            "query_order_detail": self._query_order_detail,
            "query_candidate_masters": self._query_candidate_masters,
            "score_master_by_rule": self._score_master_by_rule,
            "log_decision": self._log_decision,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return _invalid_tool_response(["INVALID_TOOL"])
        return handler(tool_input, session_state)

    def _load_mock_order(self) -> Order:
        fixture_path = _project_root() / "tests" / "fixtures" / "order.api.response.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        return map_api_order(payload["data"], self._settings)

    def _resolve_order_ids(self, order_key: str) -> tuple[int, int | None]:
        if is_order_no(order_key):
            order_id, tenant_id = resolve_order_no(self._db, order_key)
            return order_id, tenant_id
        order_id, tenant_id = resolve_order_key(order_key)
        return order_id, tenant_id

    def _fetch_live_order(self, order_key: str) -> Order:
        tenant_id = self._settings.hx_tenant_id

        if is_order_no(order_key):
            try:
                _, tenant_id = resolve_order_no(self._db, order_key)
            except LookupError:
                pass
            try:
                return self._api.get_order_detail(
                    order_no=order_key,
                    tenant_id=tenant_id,
                )
            except ApiError:
                raise LookupError(f"Order not found: {order_key}") from None

        order_id, resolved_tenant = resolve_order_key(order_key)
        if resolved_tenant is not None:
            tenant_id = resolved_tenant

        try:
            return self._api.get_order_detail(order_id=order_id, tenant_id=tenant_id)
        except ApiError:
            order_no, tenant_id = self._db.lookup_order_by_id(order_id)
            return self._api.get_order_detail(order_no=order_no, tenant_id=tenant_id)

    def _query_order_detail(self, tool_input: dict, session_state: dict) -> dict:
        order_key = str(tool_input.get("order_id", "")).strip()
        if not order_key:
            return {"error": "missing_order_id"}

        if self._settings.mock_mode:
            order = self._load_mock_order()
        else:
            order = self._fetch_live_order(order_key)

        session_state["order"] = order.model_dump()
        session_state["order_id"] = order.order_id
        return _order_tool_output(order)

    def _get_order_from_state(self, session_state: dict) -> Order | None:
        raw = session_state.get("order")
        if raw is None:
            return None
        return Order.model_validate(raw)

    def _query_candidate_masters(self, tool_input: dict, session_state: dict) -> dict:
        order = self._get_order_from_state(session_state)
        if order is None:
            return {"error": "order_not_loaded", "message": "Call query_order_detail first"}

        candidates = self._db.list_candidate_masters(order)
        session_state["candidates"] = [c.model_dump() for c in candidates]
        return {
            "masters": [c.model_dump() for c in candidates],
            "count": len(candidates),
        }

    def _score_master_by_rule(self, tool_input: dict, session_state: dict) -> dict:
        order = self._get_order_from_state(session_state)
        if order is None:
            return {"error": "order_not_loaded", "message": "Call query_order_detail first"}

        raw_candidates = session_state.get("candidates")
        if not raw_candidates:
            return {"error": "candidates_not_loaded", "message": "Call query_candidate_masters first"}

        candidates = [MasterCandidate.model_validate(c) for c in raw_candidates]
        master_ids = tool_input.get("master_ids")
        if master_ids:
            allowed = {str(mid) for mid in master_ids}
            candidates = [c for c in candidates if c.master_id in allowed]

        rankings = rank_masters(order, candidates)
        session_state["rankings"] = [r.model_dump() for r in rankings]
        return {"rankings": [r.model_dump() for r in rankings]}

    def _log_decision(self, tool_input: dict, session_state: dict) -> dict:
        return {"logged": True}
