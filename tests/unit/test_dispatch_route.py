import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.routes.dispatch import get_settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    db_path = tmp_path / "route_test.db"
    settings = Settings(
        mock_mode=True,
        dry_run=True,
        dispatch_phase=1,
        sqlite_path=str(db_path),
        hx_tenant_id=1,
    )

    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_dispatch_returns_success_with_steps(client):
    response = client.post("/demo/dispatch", json={"order_id": "11409"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert body["status_label"] == "推荐完成"
    assert body["dry_run"] is True
    assert body["phase"] == 1
    assert body["session_id"]
    assert body["order_summary"]
    assert body["order_summary"]["order_no"]
    assert len(body["steps"]) >= 3
    assert body["steps"][0]["tool"] == "query_order_detail"
    assert body["steps"][0]["title"] == "查看订单信息"
    assert body["steps"][1]["tool"] == "query_candidate_masters"
    assert body["steps"][2]["tool"] == "score_master_by_rule"
    assert body["guard_logs"] == []
    assert len(body["top3"]) >= 1
    assert body["top3"][0]["master_name"]
    assert body["top3"][0]["nbs_id"]
    assert body["top3"][0]["reason"]


def test_get_session_after_dispatch(client):
    dispatch = client.post("/demo/dispatch", json={"order_id": "11409"}).json()
    session_id = dispatch["session_id"]

    response = client.get(f"/demo/sessions/{session_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["order_id"] == "11409"
    assert body["status"] == "SUCCESS"
    assert len(body["steps"]) >= 3


def test_get_session_not_found(client):
    response = client.get("/demo/sessions/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
