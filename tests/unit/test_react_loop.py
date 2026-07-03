import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.adapters.api_client import ApiClient
from app.config import Settings
from app.domain.models import MasterCandidate, Order
from app.domain.react_loop import run_react_loop
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


class FakeLlm:
    def __init__(self, steps):
        self.steps = iter(steps)

    def next(self, state, tool_schemas, system_prompt):
        return next(self.steps)


def test_react_loop_success_with_fake_llm(settings_mock):
    gw = _make_gateway(settings_mock)
    fake = FakeLlm(
        [
            {"tool_name": "query_order_detail", "tool_input": {"order_id": "11409"}},
            {"tool_name": "query_candidate_masters", "tool_input": {"order_id": "11409"}},
            {"tool_name": "score_master_by_rule", "tool_input": {"order_id": "11409"}},
            {"finish": True, "top3": [{"master_id": "M001", "score": 90.0}]},
        ]
    )
    result = run_react_loop(
        order_key="11409",
        llm=fake,
        gateway=gw,
        settings=settings_mock,
        session_id="test-session-1",
    )
    assert result["status"] == "SUCCESS"
    assert result["session_id"] == "test-session-1"
    assert len(result["steps"]) >= 3
    assert result["steps"][0]["tool"] == "query_order_detail"
    assert result["steps"][1]["tool"] == "query_candidate_masters"
    assert result["steps"][2]["tool"] == "score_master_by_rule"
    assert "duration_ms" in result["steps"][0]
    assert "observation" in result["steps"][0]
    assert result["top3"][0]["master_id"] == "M001"
    assert result["top3"][0]["score"] == 90.0
    assert result["top3"][0]["rank"] == 1
    assert "master_name" in result["top3"][0]


def test_react_loop_escalated_on_max_steps(settings_mock):
    gw = _make_gateway(settings_mock)
    settings_mock.max_steps = 2
    fake = FakeLlm(
        [
            {"tool_name": "query_order_detail", "tool_input": {"order_id": "11409"}},
            {"tool_name": "query_candidate_masters", "tool_input": {"order_id": "11409"}},
            {"tool_name": "score_master_by_rule", "tool_input": {"order_id": "11409"}},
        ]
    )
    result = run_react_loop(
        order_key="11409",
        llm=fake,
        gateway=gw,
        settings=settings_mock,
    )
    assert result["status"] == "ESCALATED"
    assert len(result["steps"]) == 2
    assert "session_id" in result


def test_react_loop_invalid_tool_continues(settings_mock):
    gw = _make_gateway(settings_mock)
    fake = FakeLlm(
        [
            {"tool_name": "relax_rule", "tool_input": {"order_id": "11409"}},
            {"tool_name": "query_order_detail", "tool_input": {"order_id": "11409"}},
            {"finish": True, "top3": []},
        ]
    )
    result = run_react_loop(
        order_key="11409",
        llm=fake,
        gateway=gw,
        settings=settings_mock,
    )
    assert result["status"] == "SUCCESS"
    assert len(result["steps"]) == 2
    assert "error=" in result["steps"][0]["observation"]
    assert result["steps"][1]["tool"] == "query_order_detail"


def test_react_loop_escalated_on_timeout(settings_mock):
    gw = _make_gateway(settings_mock)
    settings_mock.t_session_sec = 0
    fake = FakeLlm(
        [
            {"tool_name": "query_order_detail", "tool_input": {"order_id": "11409"}},
            {"finish": True, "top3": []},
        ]
    )
    with patch("app.domain.react_loop.time.monotonic", side_effect=[0.0, 1.0]):
        result = run_react_loop(
            order_key="11409",
            llm=fake,
            gateway=gw,
            settings=settings_mock,
        )
    assert result["status"] == "ESCALATED"
    assert result["steps"] == []
