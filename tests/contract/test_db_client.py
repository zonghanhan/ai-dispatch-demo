from unittest.mock import MagicMock

from app.adapters.db_client import DbClient
from app.config import Settings
from app.domain.models import MasterCandidate, Order


def _sample_order(**overrides) -> Order:
    base = {
        "order_id": "11409",
        "biz_type": 2,
        "customer_type": "汇信昌",
        "tenant_id": 1,
        "city": "深圳市",
        "erp_codes": ["PL010104"],
        "service_type_code": "LX002",
    }
    base.update(overrides)
    return Order(**base)


def test_list_candidate_masters_mock_mode():
    settings = Settings(mock_mode=True)
    client = DbClient(settings)
    masters = client.list_candidate_masters(_sample_order())

    assert len(masters) == 3
    assert all(isinstance(m, MasterCandidate) for m in masters)
    assert masters[0].master_id == "ad71795f-ed1b-4d61-bfd7-5fa664337b18"


def test_list_candidate_masters_sql_with_exact_erp_code():
    settings = Settings(
        mock_mode=False,
        db_host="localhost",
        db_user="user",
        db_password="pass",
        db_name="hxc_cloud",
    )

    row = {
        "master_id": "m1",
        "master_name": "Test Master",
        "company": 1,
        "profession_type": "安装",
        "service_city": "深圳市",
        "lat": 22.66,
        "lng": 113.92,
        "active_orders": 0,
        "free_ratio": 1.0,
        "skill_codes": "PL010104",
        "skill_match": 1,
    }

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [row]
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    client = DbClient(settings, connection=mock_conn)
    masters = client.list_candidate_masters(_sample_order())

    assert len(masters) == 1
    assert masters[0].master_id == "m1"
    assert masters[0].skill_codes == "PL010104"

    mock_cursor.execute.assert_called_once()
    sql, params = mock_cursor.execute.call_args[0]
    assert "esc.code = %s" in sql
    assert params == ("LX002", "深圳市", "PL010104", 50)


def test_list_candidate_masters_dedupes_by_master_id():
    settings = Settings(
        mock_mode=False,
        db_host="localhost",
        db_user="user",
        db_password="pass",
        db_name="hxc_cloud",
    )

    row = {
        "master_id": "same-master",
        "master_name": "Dup",
        "company": 1,
        "profession_type": "安装",
        "service_city": "深圳市",
        "lat": 22.66,
        "lng": 113.92,
        "active_orders": 0,
        "free_ratio": 1.0,
        "skill_codes": "PL010104",
        "skill_match": 1,
    }

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [row]
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    client = DbClient(settings, connection=mock_conn)
    order = _sample_order(erp_codes=["PL010104", "PL010289"])
    masters = client.list_candidate_masters(order)

    assert len(masters) == 1
    assert mock_cursor.execute.call_count == 2
    for call in mock_cursor.execute.call_args_list:
        assert call[0][1][2] in {"PL010104", "PL010289"}
