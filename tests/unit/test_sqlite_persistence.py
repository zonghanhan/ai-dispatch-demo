from app.config import Settings
from app.persistence.sqlite import SessionStore


def test_session_store_round_trip(tmp_path):
    db_path = tmp_path / "test.db"
    settings = Settings(sqlite_path=str(db_path))
    store = SessionStore(settings)
    store.init_db()

    session_id = store.create_session("11409", "SUCCESS")
    assert session_id
    assert len(session_id) == 36

    store.append_tool_call(
        session_id,
        1,
        "query_order_detail",
        120,
        {"order_id": "11409", "biz_type": 1},
    )
    store.append_tool_call(
        session_id,
        2,
        "query_candidate_masters",
        85,
        {"count": 3},
    )

    replay = store.get_session(session_id)
    assert replay is not None
    assert replay["session_id"] == session_id
    assert replay["order_id"] == "11409"
    assert replay["status"] == "SUCCESS"
    assert replay["created_at"]
    assert replay["payload"] == {}
    assert len(replay["steps"]) == 2
    assert replay["steps"][0] == {
        "step": 1,
        "tool": "query_order_detail",
        "duration_ms": 120,
        "observation": {"order_id": "11409", "biz_type": 1},
    }
    assert replay["steps"][1] == {
        "step": 2,
        "tool": "query_candidate_masters",
        "duration_ms": 85,
        "observation": {"count": 3},
    }


def test_init_db_is_idempotent(tmp_path):
    db_path = tmp_path / "nested" / "demo.db"
    settings = Settings(sqlite_path=str(db_path))
    store = SessionStore(settings)

    store.init_db()
    store.init_db()

    session_id = store.create_session("DD20260702000005", "ESCALATED")
    replay = store.get_session(session_id)
    assert replay is not None
    assert replay["order_id"] == "DD20260702000005"
    assert replay["status"] == "ESCALATED"
    assert replay["steps"] == []


def test_get_session_returns_none_for_unknown_id(tmp_path):
    settings = Settings(sqlite_path=str(tmp_path / "empty.db"))
    store = SessionStore(settings)
    store.init_db()

    assert store.get_session("00000000-0000-0000-0000-000000000000") is None
