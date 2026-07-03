# AI 智能体派单 Demo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `D:\ai-dispatch-demo` 实现可本地运行的 Guarded Agent 派单 Demo：输入 order_no/id → ReAct + 4 工具 → 规则护栏 → Top3 + 时间轴 UI。

**Architecture:** FastAPI 编排层；adapters 对接测试 API / 只读 MySQL；domain 纯函数做 score/guard；ToolGateway 白名单 4 工具；SQLite 审计；`MOCK_MODE` 用 fixture 跑通 CI。

**Tech Stack:** Python 3.11+, FastAPI, pydantic-settings, httpx, PyMySQL, SQLite3, pytest, pytest-asyncio（如需要）

**Spec / Design:** `docs/plans/2026-07-03-ai-dispatch-demo-design.md`, `CONTEXT.md`, `docs/sql/candidate_masters.sql`

---

## File Map（新建）

| 路径 | 职责 |
|------|------|
| `pyproject.toml` | 依赖与 pytest 配置 |
| `app/config.py` | `.env` 加载 |
| `app/domain/models.py` | Order, Master, Ranking DTO |
| `app/domain/distance.py` | Haversine km |
| `app/domain/score.py` | 双轨距离分 + 总分 |
| `app/domain/guard.py` | R-HARD-01/02/03/08, phase=1 |
| `app/domain/mapping.py` | API→Order, bizType→LX, tenant→customer_type, PII |
| `app/domain/order_resolver.py` | order_no→numeric id |
| `app/adapters/api_client.py` | POST publish-order/get |
| `app/adapters/db_client.py` | 候选师傅 SQL |
| `app/adapters/llm_client.py` | OpenAI-compatible ReAct 一步 |
| `app/tools/registry.py` | 4 工具 schema |
| `app/tools/gateway.py` | 白名单执行 |
| `app/domain/react_loop.py` | ReAct 循环 |
| `app/persistence/sqlite.py` | sessions / tool_calls |
| `app/services/dispatch_service.py` | 编排入口 |
| `app/routes/dispatch.py` | HTTP 路由 |
| `app/main.py` | FastAPI app |
| `web/static/index.html` | Demo UI |
| `web/static/app.js` | 调用 `/demo/dispatch` |
| `scripts/smoke_api.py` | 订单 API smoke |
| `scripts/smoke_db.py` | 候选 SQL smoke |

---

## Task 1: 项目脚手架与配置

**Files:**
- Create: `pyproject.toml`, `app/__init__.py`, `app/config.py`
- Test: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_config.py
from app.config import Settings


def test_settings_loads_hx_tenant_and_safety_flags(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("DISPATCH_PHASE", "1")
    monkeypatch.setenv("HX_TENANT_ID", "1")
    monkeypatch.setenv("MOCK_MODE", "true")
    s = Settings()
    assert s.dry_run is True
    assert s.dispatch_phase == 1
    assert s.hx_tenant_id == 1
    assert s.mock_mode is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\ai-dispatch-demo && python -m pytest tests/unit/test_config.py -v`  
Expected: FAIL — `ModuleNotFoundError: app.config`

- [ ] **Step 3: Write minimal implementation**

`pyproject.toml`（核心片段）:

```toml
[project]
name = "ai-dispatch-demo"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.32.0",
  "pydantic-settings>=2.6.0",
  "httpx>=0.27.0",
  "pymysql>=1.1.0",
  "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-cov>=5.0.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["integration: live API/DB/LLM"]
```

`app/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    dry_run: bool = True
    dispatch_phase: int = 1
    mock_mode: bool = True

    api_base_url: str = "http://127.0.0.1:8000"
    api_token: str = ""
    api_order_path: str = "/app-api/order/publish-order/get"
    api_tenant_header: str = "tenant-id"
    api_timeout_sec: int = 10
    hx_tenant_id: int = 1

    db_host: str = ""
    db_port: int = 3306
    db_name: str = "hxc_cloud"
    db_user: str = ""
    db_password: str = ""

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    llm_timeout_sec: int = 30

    test_order_no: str = "DD20260702000005"
    test_order_id: str = ""
    max_steps: int = 8
    t_session_sec: int = 30
    sqlite_path: str = "./data/demo.db"
```

- [ ] **Step 4: Run test — Expected PASS**

- [ ] **Step 5: Install deps**

Run: `cd D:\ai-dispatch-demo && pip install -e ".[dev]"`

---

## Task 2: 领域模型与映射

**Files:**
- Create: `app/domain/models.py`, `app/domain/mapping.py`
- Test: `tests/unit/test_mapping.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_mapping.py
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
```

- [ ] **Step 2: Run — Expected FAIL**

- [ ] **Step 3: Implement**

`app/domain/models.py` — 使用 pydantic `BaseModel`:

```python
from pydantic import BaseModel, Field


class Order(BaseModel):
    order_id: str
    order_no: str = ""
    biz_type: int
    biz_type_name: str = ""
    customer_type: str
    tenant_id: int
    category: str = ""
    lat: float | None = None
    lng: float | None = None
    city: str = ""
    address_masked: str = ""
    urgent: bool = False
    status: int = 0
    erp_codes: list[str] = Field(default_factory=list)
    service_type_code: str = ""


class MasterCandidate(BaseModel):
    master_id: str
    master_name: str = ""
    profession_type: str = ""
    skill_match: bool = True
    skill_codes: str = ""
    free_ratio: float = 1.0
    lat: float | None = None
    lng: float | None = None
    company: int | None = None
    service_city: str = ""
    active_orders: int = 0


class RankingItem(BaseModel):
    master_id: str
    score: float
    breakdown: dict
    reason: str = ""
```

`app/domain/mapping.py`:

```python
BIZ_TYPE_SERVICE = {1: "LX001", 2: "LX002", 3: "LX003", 4: "LX003"}
BIZ_TYPE_NAME = {1: "测量", 2: "安装", 3: "单次维修", 4: "质保维修"}


def biz_type_to_service_code(biz_type: int) -> str:
    return BIZ_TYPE_SERVICE[biz_type]


def resolve_customer_type(tenant_id: int, settings) -> str:
    return "汇信昌" if tenant_id == settings.hx_tenant_id else "非汇信昌"


def mask_address(province: str, area: str, address: str) -> str:
    region = f"{province or ''}{area or ''}".strip()
    return f"{region}***" if region else "***"


def _urgent_from_data(data: dict) -> bool:
    if data.get("emergencyFlag", 0) not in (0, None):
        return True
    if data.get("isNightEmergency") is True:
        return True
    for g in data.get("goodsSaveReqVOList") or []:
        if g.get("isNightEmergency") in (1, 2):
            return True
    return False


def map_api_order(data: dict, settings) -> "Order":
    from app.domain.models import Order

    tenant_id = int(data.get("tenantId") or 0)
    biz_type = int(data.get("bizType") or 0)
    erp_codes = [
        g.get("erpCode")
        for g in (data.get("goodsSaveReqVOList") or [])
        if g.get("erpCode")
    ]
    return Order(
        order_id=str(data["id"]),
        order_no=data.get("orderNo") or "",
        biz_type=biz_type,
        biz_type_name=data.get("spuTypeName") or BIZ_TYPE_NAME.get(biz_type, ""),
        customer_type=resolve_customer_type(tenant_id, settings),
        tenant_id=tenant_id,
        category=data.get("spuCategoryName") or (data.get("spuPath") or "").split(">")[-1],
        lat=data.get("lat"),
        lng=data.get("lon"),
        city=data.get("city") or "",
        address_masked=mask_address(data.get("province", ""), data.get("area", ""), data.get("address", "")),
        urgent=_urgent_from_data(data),
        status=int(data.get("status") or 0),
        erp_codes=list(dict.fromkeys(erp_codes)),
        service_type_code=biz_type_to_service_code(biz_type),
    )
```

- [ ] **Step 4: Run — Expected PASS**

---

## Task 3: 距离与评分（双轨）

**Files:**
- Create: `app/domain/distance.py`, `app/domain/score.py`
- Test: `tests/unit/test_score.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_score.py
from app.domain.models import MasterCandidate, Order
from app.domain.score import distance_score, rank_masters


def _order(customer_type: str, lat=31.23, lng=121.47):
    return Order(
        order_id="1", biz_type=2, customer_type=customer_type,
        tenant_id=1 if customer_type == "汇信昌" else 2,
        lat=lat, lng=lng, service_type_code="LX002",
    )


def test_non_hxc_8km_distance_score():
    # 深圳附近两点约 8km 量级 — 用固定坐标验证公式
    score = distance_score(8.0, "非汇信昌")
    assert score == 1.25


def test_non_hxc_12km_distance_score():
    assert distance_score(12.0, "非汇信昌") == 0.0


def test_rank_excludes_low_free_ratio():
    order = _order("非汇信昌")
    masters = [
        MasterCandidate(master_id="m1", free_ratio=0.3, lat=31.23, lng=121.47, skill_match=True),
        MasterCandidate(master_id="m2", free_ratio=0.8, lat=31.24, lng=121.48, skill_match=True),
    ]
    ranked = rank_masters(order, masters)
    assert len(ranked) == 1
    assert ranked[0].master_id == "m2"
```

- [ ] **Step 2: Run — Expected FAIL**

- [ ] **Step 3: Implement**

`app/domain/distance.py`:

```python
import math

EARTH_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(a))
```

`app/domain/score.py`:

```python
from app.domain.distance import haversine_km
from app.domain.models import MasterCandidate, Order, RankingItem


def distance_score(km: float, customer_type: str) -> float:
    if km <= 0.5:
        return 5.0
    if customer_type == "汇信昌":
        if km > 100.5:
            return 0.0
        return max(0.0, 5.0 - (km - 0.5) * 0.05)
    if km > 10.0:
        return 0.0
    return max(0.0, 5.0 - (km - 0.5) * 0.5)


def rank_masters(order: Order, masters: list[MasterCandidate]) -> list[RankingItem]:
    items: list[RankingItem] = []
    for m in masters:
        if not m.skill_match:
            continue
        if m.free_ratio < 0.5:
            continue
        if order.lat is None or order.lng is None or m.lat is None or m.lng is None:
            km = 999.0
        else:
            km = haversine_km(order.lat, order.lng, m.lat, m.lng)
        d_score = distance_score(km, order.customer_type)
        if order.customer_type == "非汇信昌" and km > 10:
            d_score = 0.0
        total = d_score + m.free_ratio
        items.append(RankingItem(
            master_id=m.master_id,
            score=round(total, 2),
            breakdown={"distance_km": round(km, 2), "distance_score": d_score, "free_ratio": m.free_ratio},
            reason=f"距离{km:.1f}km，空闲{m.free_ratio:.0%}",
        ))
    items.sort(key=lambda x: x.score, reverse=True)
    return items
```

- [ ] **Step 4: Run — Expected PASS**

---

## Task 4: 护栏规则

**Files:**
- Create: `app/domain/guard.py`
- Test: `tests/unit/test_guard.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_guard.py
from app.domain.guard import assert_tool_allowed, reject_assign_in_phase1


def test_reject_assign_in_phase1():
    ok, codes = reject_assign_in_phase1("assign_order", phase=1)
    assert ok is False
    assert "R-PHASE-01" in codes


def test_whitelist_tool_ok():
    ok, codes = assert_tool_allowed("query_order_detail", phase=1)
    assert ok is True
    assert codes == []


def test_unknown_tool_rejected():
    ok, codes = assert_tool_allowed("relax_rule", phase=1)
    assert ok is False
    assert "INVALID_TOOL" in codes
```

- [ ] **Step 2–4: Implement `guard.py` with WHITELIST=frozenset(4 tools), run PASS**

```python
WHITELIST = frozenset({
    "query_order_detail",
    "query_candidate_masters",
    "score_master_by_rule",
    "log_decision",
})


def reject_assign_in_phase1(tool_name: str, phase: int):
    if phase == 1 and tool_name in {"assign_order", "reassign_order"}:
        return False, ["R-PHASE-01"]
    return True, []


def assert_tool_allowed(tool_name: str, phase: int):
    if tool_name not in WHITELIST:
        return False, ["INVALID_TOOL"]
    return reject_assign_in_phase1(tool_name, phase)
```

---

## Task 5: ApiClient（Contract）

**Files:**
- Create: `app/adapters/api_client.py`
- Test: `tests/contract/test_api_client.py`

- [ ] **Step 1: Write failing contract test**（httpx mock）

```python
# tests/contract/test_api_client.py
import json
from pathlib import Path

import httpx
import pytest

from app.adapters.api_client import ApiClient
from app.config import Settings


@pytest.mark.asyncio
async def test_get_order_detail_maps_fixture(respx_mock):  # 若无 respx，用 httpx.MockTransport
    fixture = json.loads(Path("tests/fixtures/order.api.response.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request):
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
```

- [ ] **Step 3: Implement ApiClient**

要点：
- `POST {base}{path}` body `{"id": int}`
- Headers: `Authorization: Bearer`, `{api_tenant_header}: tenant_id`
- `code != 0` → raise `ApiError`
- `map_api_order(data, settings)`

- [ ] **Step 4: Contract test PASS**

---

## Task 6: OrderResolver + DbClient

**Files:**
- Create: `app/domain/order_resolver.py`, `app/adapters/db_client.py`
- Test: `tests/unit/test_order_resolver.py`, `tests/contract/test_db_client.py`

- [ ] **Step 1: order_resolver test**

```python
def test_resolve_numeric_id_passthrough():
    from app.domain.order_resolver import resolve_order_key
    assert resolve_order_key("11409") == (11409, None)


def test_resolve_order_no_prefix():
    from app.domain.order_resolver import is_order_no
    assert is_order_no("DD20260702000005") is True
```

- [ ] **Step 2: DbClient contract test** — mock PyMySQL cursor 返回 1 行，验证 SQL 参数 `:erp_code` 精确匹配

- [ ] **Step 3: Implement DbClient.list_candidate_masters(order: Order)**

逻辑：
1. 读取 `docs/sql/candidate_masters.sql`
2. 对每个 `order.erp_codes` 执行查询（精确 `esc.code = :erp_code`）
3. 按 `master_id` 去重合并
4. `MOCK_MODE` → 读 `tests/fixtures/candidates.json`

`resolve_order_key`:
- 纯数字 → `(int, None)`
- `DD*` → DB `SELECT id, tenant_id FROM order_order WHERE order_no=%s AND deleted=0`

---

## Task 7: ToolGateway

**Files:**
- Create: `app/tools/registry.py`, `app/tools/gateway.py`
- Test: `tests/unit/test_tool_gateway.py`

- [ ] **Step 1: Test gateway executes 4 tools in mock mode**

```python
def test_query_order_detail_mock_mode(settings_mock):
    gw = ToolGateway(settings_mock, api=FakeApi(), db=FakeDb())
    out = gw.execute("query_order_detail", {"order_id": "11409"}, session_state={})
    assert "order_id" in out
```

- [ ] **Step 3: Implement registry schemas + gateway routing**

`score_master_by_rule` 从 session_state 取 order + candidates，调 `rank_masters`。

---

## Task 8: ReAct Loop（FakeLlm）

**Files:**
- Create: `app/domain/react_loop.py`
- Test: `tests/unit/test_react_loop.py`

- [ ] **Step 1: Test fixed FakeLlm sequence**

```python
class FakeLlm:
    def __init__(self, steps):
        self.steps = iter(steps)

    def next(self, state, tool_schemas, system_prompt):
        return next(self.steps)


def test_react_loop_success_with_fake_llm():
    fake = FakeLlm([
        {"tool_name": "query_order_detail", "tool_input": {"order_id": "11409"}},
        {"tool_name": "query_candidate_masters", "tool_input": {"order_id": "11409"}},
        {"tool_name": "score_master_by_rule", "tool_input": {"order_id": "11409"}},
        {"finish": True, "top3": []},
    ])
    result = run_react_loop(order_key="11409", llm=fake, gateway=gw, settings=s, max_steps=8)
    assert result["status"] == "SUCCESS"
    assert len(result["steps"]) >= 3
```

- [ ] **Step 3: Implement loop** — 超时 `T_session_SEC`，非法 tool 写 observation error，超步 ESCALATED

---

## Task 9: SQLite 持久化

**Files:**
- Create: `app/persistence/sqlite.py`
- Test: `tests/unit/test_sqlite_persistence.py`

- [ ] **Tables:** `sessions(id, order_id, status, created_at, payload_json)`, `tool_calls(id, session_id, step, tool, duration_ms, observation_json)`

- [ ] **Test:** 写入 1 session + 2 tool_calls 后可读回

---

## Task 10: LlmClient（OpenAI-compatible）

**Files:**
- Create: `app/adapters/llm_client.py`
- Test: `tests/contract/test_llm_client.py`（mock httpx；不默认打真实 LLM）

- [ ] **Implement** `chat.completions` with `tools` param；解析 tool_calls 或 finish message

- [ ] **Integration 时才用真实 qwen-plus**（见 Task 14）

---

## Task 11: FastAPI 路由与服务

**Files:**
- Create: `app/services/dispatch_service.py`, `app/routes/dispatch.py`, `app/main.py`
- Test: `tests/unit/test_dispatch_route.py`（TestClient + MOCK_MODE）

- [ ] **POST /demo/dispatch** body `{"order_id": "DD20260702000005"}`

- [ ] **GET /health**, **GET /demo/sessions/{id}**, static mount `/` → `web/static`

`DispatchService.run(order_id)`:
1. resolve order key
2. run react loop
3. persist session
4. return `{session_id, status, top3, steps, guard_logs, dry_run, phase}`

---

## Task 12: 静态 UI

**Files:**
- Create: `web/static/index.html`, `web/static/app.js`

- [ ] 输入框默认 `TEST_ORDER_NO`
- [ ] 按钮调用 `POST /demo/dispatch`
- [ ] 渲染 Top3 卡片 + steps 时间轴 + DRY_RUN/phase 标签
- [ ] 内联 CSS，无 CDN

---

## Task 13: Smoke Scripts

**Files:**
- Create: `scripts/smoke_api.py`, `scripts/smoke_db.py`

- [ ] **smoke_api.py:** 读 `.env`，resolve order_no，打印 numeric id + order DTO 摘要，提示回填 `TEST_ORDER_ID`

Run: `python scripts/smoke_api.py`

- [ ] **smoke_db.py:** 用 fixture order 的 city/erpCode 查候选数

Run: `python scripts/smoke_db.py`

---

## Task 14: Integration Test

**Files:**
- Create: `tests/integration/test_smoke_dispatch.py`
- Modify: `README.md`

- [ ] **Marker `@pytest.mark.integration`**

Run: `cd D:\ai-dispatch-demo && set INTEGRATION=1 && pytest tests/integration -m integration -v`

断言：
- `status` in (`SUCCESS`, `ESCALATED`)
- `steps` 含 `query_order_detail`
- 若 API/DB 可用则 `top3` 非空或 reason=`NO_CANDIDATES`

---

## Task 15: 设计文档状态更新

**Files:**
- Modify: `docs/plans/2026-07-03-ai-dispatch-demo-design.md`

- [ ] Status → **Approved / Impl plan generated**
- [ ] Acceptance checklist 勾选设计批准项

---

## Self-Review Checklist

| Spec 要求 | 对应 Task |
|-----------|-----------|
| API+DB 混合 | Task 5, 6 |
| tenantId 汇信昌 | Task 2 |
| erpCode 精确匹配 | Task 6 |
| order_no 解析 | Task 6 |
| 4 工具白名单 | Task 4, 7 |
| R-HARD-01/02/03 | Task 3, 4 |
| 双轨距离 8km/12km | Task 3 |
| ReAct + FakeLlm | Task 8 |
| SQLite 审计 | Task 9 |
| UI 时间轴 | Task 12 |
| MOCK_MODE fixture | Task 5–7 |
| DRY_RUN phase=1 | Task 1, 4, 11 |
| PII 脱敏 | Task 2 |

**无 TBD / TODO 占位。**

---

## 执行顺序建议

```text
Task 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15
```

每 Task 内严格：**failing test → implement → green**（Superpowers TDD Iron Law）。

---

## Revision

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-07-03 | 自 design v0.4 生成；15 Tasks；TDD 逐步 |
