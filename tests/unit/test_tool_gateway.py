import json
from pathlib import Path

import httpx
import pytest

from app.adapters.api_client import ApiClient
from app.adapters.db_client import DbClient
from app.config import Settings
from app.domain.models import MasterCandidate, Order
from app.tools.gateway import ToolGateway


@pytest.fixture
def settings_mock():
    return Settings(mock_mode=True, dry_run=True, dispatch_phase=1, hx_tenant_id=1)


class FakeDb:
    def lookup_order_by_no(self, order_no: str) -> tuple[int, int]:
        return (11409, 1)

    def list_candidate_masters(self, order: Order) -> list[MasterCandidate]:
        fixture_path = Path("tests/fixtures/candidates.json")
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        masters = []
        for row in payload.get("masters", []):
            skill_codes = row.get("skill_codes") or ""
            if isinstance(skill_codes, list):
                skill_codes = ",".join(skill_codes)
            masters.append(
                MasterCandidate(
                    master_id=str(row["master_id"]),
                    master_name=row.get("master_name") or "",
                    profession_type=row.get("profession_type") or "",
                    skill_match=bool(row.get("skill_match", True)),
                    skill_codes=str(skill_codes),
                    free_ratio=float(row.get("free_ratio", 1.0)),
                    lat=row.get("lat"),
                    lng=row.get("lng"),
                    company=row.get("company"),
                    service_city=row.get("service_city") or "",
                    active_orders=int(row.get("active_orders") or 0),
                )
            )
        return masters


def _make_gateway(settings: Settings, db=None) -> ToolGateway:
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    api = ApiClient(settings, httpx.Client(transport=transport))
    return ToolGateway(settings, api_client=api, db_client=db or FakeDb())


def test_query_order_detail_mock_mode(settings_mock):
    gw = _make_gateway(settings_mock)
    session_state: dict = {}
    out = gw.execute("query_order_detail", {"order_id": "11409"}, session_state)
    assert "order_id" in out
    assert out["order_id"] == "11409"
    assert session_state["order"]["order_id"] == "11409"


def test_unknown_tool_returns_invalid_tool_call(settings_mock):
    gw = _make_gateway(settings_mock)
    out = gw.execute("relax_rule", {"order_id": "11409"}, session_state={})
    assert out.get("error") == "invalid_tool_call"
    assert "INVALID_TOOL" in out.get("codes", [])


def test_score_after_order_and_candidates_returns_rankings(settings_mock):
    gw = _make_gateway(settings_mock)
    session_state: dict = {}

    order_out = gw.execute("query_order_detail", {"order_id": "11409"}, session_state)
    assert "order_id" in order_out

    candidates_out = gw.execute(
        "query_candidate_masters", {"order_id": "11409"}, session_state
    )
    assert candidates_out["count"] > 0

    score_out = gw.execute("score_master_by_rule", {"order_id": "11409"}, session_state)
    assert "rankings" in score_out
    assert len(score_out["rankings"]) > 0
    assert "master_id" in score_out["rankings"][0]
    assert "score" in score_out["rankings"][0]


def test_log_decision_returns_ack(settings_mock):
    gw = _make_gateway(settings_mock)
    out = gw.execute(
        "log_decision",
        {"session_id": "s1", "summary": "done", "top3": []},
        session_state={},
    )
    assert out == {"logged": True}


def test_query_candidate_masters_requires_order(settings_mock):
    gw = _make_gateway(settings_mock)
    out = gw.execute("query_candidate_masters", {"order_id": "11409"}, session_state={})
    assert out.get("error") == "order_not_loaded"
