from __future__ import annotations

import json
import re
from pathlib import Path

import pymysql
from pymysql.cursors import DictCursor

from app.config import Settings
from app.domain.models import MasterCandidate, Order

_PARAM_RE = re.compile(r":(\w+)")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _strip_sql_comments(sql: str) -> str:
    return "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))


def _bind_named_sql(sql: str, params: dict[str, object]) -> tuple[str, tuple]:
    executable = _strip_sql_comments(sql)
    names: list[str] = []

    def repl(match: re.Match[str]) -> str:
        names.append(match.group(1))
        return "%s"

    bound = _PARAM_RE.sub(repl, executable)
    return bound, tuple(params[name] for name in names)


def _row_to_candidate(row: dict) -> MasterCandidate:
    skill_codes = row.get("skill_codes") or ""
    if isinstance(skill_codes, list):
        skill_codes = ",".join(skill_codes)
    return MasterCandidate(
        master_id=str(row["master_id"]),
        master_name=row.get("master_name") or "",
        nbs_id=str(row.get("nbs_id") or ""),
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


class DbClient:
    def __init__(self, settings: Settings, connection=None) -> None:
        self._settings = settings
        self._connection = connection

    def _get_connection(self):
        if self._connection is not None:
            return self._connection
        return pymysql.connect(
            host=self._settings.db_host,
            port=self._settings.db_port,
            user=self._settings.db_user,
            password=self._settings.db_password,
            database=self._settings.db_name,
            cursorclass=DictCursor,
        )

    def lookup_order_by_no(self, order_no: str) -> tuple[int, int]:
        sql = (
            "SELECT id, tenant_id FROM order_order "
            "WHERE order_no=%s AND deleted=0 LIMIT 1"
        )
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql, (order_no,))
            row = cursor.fetchone()
        if row is None:
            raise LookupError(f"Order not found: {order_no}")
        return int(row["id"]), int(row["tenant_id"])

    def lookup_order_by_id(self, order_id: int) -> tuple[str, int]:
        sql = (
            "SELECT order_no, tenant_id FROM order_order "
            "WHERE id=%s AND deleted=0 LIMIT 1"
        )
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql, (order_id,))
            row = cursor.fetchone()
        if row is None:
            raise LookupError(f"Order not found: id={order_id}")
        return str(row["order_no"]), int(row["tenant_id"])

    def _load_candidate_sql(self) -> str:
        sql_path = _project_root() / "docs" / "sql" / "candidate_masters.sql"
        return sql_path.read_text(encoding="utf-8")

    def _load_mock_candidates(self) -> list[MasterCandidate]:
        fixture_path = _project_root() / "tests" / "fixtures" / "candidates.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        return [_row_to_candidate(row) for row in payload.get("masters", [])]

    def _query_candidates_for_erp(self, cursor, sql: str, order: Order, erp_code: str) -> list[dict]:
        bound_sql, params = _bind_named_sql(
            sql,
            {
                "service_type_code": order.service_type_code,
                "erp_code": erp_code,
                "city_name": order.city,
                "limit": 50,
            },
        )
        cursor.execute(bound_sql, params)
        return list(cursor.fetchall())

    def list_candidate_masters(self, order: Order) -> list[MasterCandidate]:
        if self._settings.mock_mode:
            return self._load_mock_candidates()

        if not order.erp_codes:
            return []

        sql = self._load_candidate_sql()
        conn = self._get_connection()
        seen: dict[str, MasterCandidate] = {}

        with conn.cursor() as cursor:
            for erp_code in order.erp_codes:
                for row in self._query_candidates_for_erp(cursor, sql, order, erp_code):
                    master_id = str(row["master_id"])
                    if master_id not in seen:
                        seen[master_id] = _row_to_candidate(row)

        return list(seen.values())
