# AI 智能体派单 Demo — 实现设计

> **For implementer:** 本文为实现设计（非产品 PRD）。产品 Spec 见知识库 `AI智能体派单需求文档.md`、`业务流程图-AI智能体派单.md`。  
> **Status:** ✅ 已批准 — Impl plan: `2026-07-03-ai-dispatch-demo-impl.md`  
> **Date:** 2026-07-03  
> **Project root:** `D:\ai-dispatch-demo`

---

## 1. Goal

在本地运行可演示的 **Guarded Agent 派单 Demo**：输入 `order_id` → ReAct Agent 调用工具 → 规则护栏 → 输出 Top3 推荐 + tool 时间轴 UI。

**非目标：** 生产部署、14 工具全量、真实 assign、Prompt 平台、完整五类订单分支。

---

## 2. 已确认决策

| 项 | 决策 |
|----|------|
| 数据来源 | **API + DB 混合**：**订单走测试 API**；**候选师傅池走只读 MySQL SQL** |
| 冲突优先级 | 订单字段以 **API 响应为准**；候选列表以 **DB 查询为准** |
| 架构 | **方案 A**：Python 3.11+ / FastAPI / SQLite 审计 / 静态 HTML |
| 安全 | `DRY_RUN=true`，`DISPATCH_PHASE=1`，DB **仅 SELECT**，禁止真实 assign |
| MVP 工具 | 4 个：`query_order_detail`、`query_candidate_masters`、`score_master_by_rule`、`log_decision` |
| Agent | ReAct，`MAX_STEPS=8`（Demo 收紧），`T_session=30s` |
| Spec | `@AI智能体派单需求文档.md` + `@业务流程图-AI智能体派单.md` |

---

## 3. Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│  Web UI (static/index.html)                                   │
│  POST /demo/dispatch { order_id }                             │
└────────────────────────────┬─────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────┐
│  FastAPI (app/main.py)                                        │
│  DispatchService → ReactLoop → ToolGateway                      │
└─────┬──────────────────┬──────────────────┬──────────────────┘
      │                  │                  │
┌─────▼─────┐    ┌───────▼───────┐   ┌──────▼──────┐
│ domain    │    │ adapters      │   │ persistence │
│ score     │    │ api_client    │   │ SQLite      │
│ guard     │    │ db_client     │   │ sessions    │
│ react     │    │ llm_client    │   │ tool_calls  │
└───────────┘    └───────┬───────┘   └─────────────┘
                         │
              ┌──────────┴──────────┐
              │                       │
       测试环境 HTTP API         只读 MySQL
       (订单详情)               (候选师傅 SQL)
```

### 3.1 Adapter 职责

| Adapter | 职责 | MVP |
|---------|------|-----|
| `api_client.ApiClient` | `get_order_detail(order_id)` → 订单 JSON | **必做** |
| `db_client.DbClient` | `list_candidate_masters(order)` → `[{master_id, ...}]` | **必做** |
| `llm_client.LlmClient` | ReAct 一步：thought + tool_call / finish | **必做**（单元测用 FakeLlm） |
| `distance` | 路线距离 km | MVP 用 DB 内经纬度 **Haversine**；标注与现网路线距离差异 |

### 3.2 混合数据流（单笔派单）

```text
1. API: query_order_detail(order_id)
      → biz_type, customer_type, category, lat/lng, address, urgent, enterprise_id
2. DB:  query_candidate_masters(order)
      → SQL 参数来自 order（品类、区域、工种等）
3. Domain: score_master_by_rule(order, candidates)
      → 双轨距离 + R-HARD-01/02 过滤
4. Agent: ReAct 编排上述工具 + log_decision + finish(Top3)
5. Guard: phase=1 拒绝 assign；DRY_RUN 下写工具仅模拟
6. SQLite: 持久化 session + tool_calls（决策回放）
```

---

## 4. MVP Scope

### 4.1 In Scope

- FastAPI 服务 + 健康检查
- 4 工具注册与 ToolGateway 白名单
- `check_rule_guard`：R-HARD-01/02/03/08 + phase=1 禁 assign
- `score_master_by_rule`：双轨距离（汇信昌/非汇信昌）+ 技能/空闲门槛（空闲可先简化字段）
- ReAct 循环 + FakeLlm 单元测试
- SQLite 审计表
- 静态页：order_id 输入、Top3、steps 时间轴、guard 日志
- `.env` + `MOCK_MODE`（无 API/DB 时用 fixture）
- Contract 测试：mock API；DB 测试：mock cursor 或 test DB

### 4.2 Out of Scope (YAGNI / Phase 2)

- 工具：`query_master_profile`、`query_route_distance`（独立 API）、`relax_rule`、`assign_order`、`escalate_to_human` 等
- 托管 Row5~7 完整策略路由
- 真实 assign / 消息推送
- Prompt 版本管理平台
- 完整 O1/O2 看板
- 生产级连接池、鉴权中间件

---

## 5. Directory Layout

```text
D:\ai-dispatch-demo\
  .env.example
  .gitignore
  README.md
  CONTEXT.md                 # 环境信息（用户填写，密钥不进 Git）
  pyproject.toml             # 或 requirements.txt
  docs\plans\
    2026-07-03-ai-dispatch-demo-design.md   # 本文件
  app\
    __init__.py
    main.py                  # FastAPI entry
    config.py                # pydantic-settings from .env
    routes\
      dispatch.py
    domain\
      score.py
      guard.py
      react_loop.py
      models.py              # Order, Master, Session DTOs
    adapters\
      api_client.py
      db_client.py
      llm_client.py
    tools\
      gateway.py
      registry.py            # 4 tools
    persistence\
      sqlite.py
  web\
    static\
      index.html
      app.js
  tests\
    unit\
      test_score.py
      test_guard.py
      test_react_loop.py
      test_tool_gateway.py
    contract\
      test_api_client.py
      test_db_client.py
    fixtures\
      order.json
      candidates.json
    integration\
      test_smoke_dispatch.py   # @pytest.mark.integration
  scripts\
    smoke_db.py
    smoke_api.py
```

---

## 6. Configuration

### 6.1 Environment variables

```env
# Safety (required)
DRY_RUN=true
DISPATCH_PHASE=1

# Mode
MOCK_MODE=false              # true: 全 fixture，不连 API/DB

# Test API — 订单（POST JSON）
API_BASE_URL=http://192.168.2.223:18080
API_TOKEN=                     # Bearer token → .env only
API_ORDER_PATH=/app-api/order/publish-order/get
API_TENANT_HEADER=tenant-id
API_TIMEOUT_SEC=10
# customer_type: data.tenantId == HX_TENANT_ID → 汇信昌
HX_TENANT_ID=1

# Read-only MySQL — 候选池（库名 hxc_cloud，与 MCP 同源）
DB_HOST=
DB_PORT=3306
DB_NAME=hxc_cloud
DB_USER=                       # 只读账号
DB_PASSWORD=

# LLM
LLM_BASE_URL=https://llm-tgefxsufbpuip2bt.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=
LLM_MODEL=qwen-plus
LLM_TIMEOUT_SEC=30

# Demo
TEST_ORDER_NO=DD20260702000005
TEST_ORDER_ID=               # numeric id, filled after smoke
MAX_STEPS=8
T_SESSION_SEC=30

# SQLite
SQLITE_PATH=./data/demo.db
```

### 6.2 CONTEXT.md（用户待填）

见 README 中「环境清单」；实现前至少需要：

1. API 订单接口 path + 成功 JSON 样例（脱敏）
2. 候选师傅 SQL 或表字段说明
3. `customer_type` / `biz_type` 字段映射
4. 1 个测试 `order_id`
5. LLM Base URL + Model

---

## 7. Tool Contracts (MVP)

### 7.1 query_order_detail

- **Input:** `{ "order_id": "string" }` — Demo 传入的 `order_id` 对应 API 请求体 `id`（int64）
- **Source:** `ApiClient.get_order_detail(order_id)`
- **HTTP:** `POST {API_BASE_URL}{API_ORDER_PATH}`，Body `{ "id": <int> }`
- **Headers:** `Authorization: Bearer …`，**`tenant-id: {data.tenantId}`**（必填）
- **order_no 解析：** UI 可传 `DD…` → DB 查 `order_order.id` 再调 API
- **Success:** `response.code === 0`，取 `response.data`

**ApiClient 映射（`data` → Order DTO）：**

| Order DTO | API 字段 | 说明 |
|-----------|----------|------|
| `order_id` | `id` | str |
| `order_no` | `orderNo` | |
| `biz_type` | `bizType` | 1/2/3/4 |
| `biz_type_name` | 枚举表或 `spuTypeName` | |
| `customer_type` | **推导** | `tenantId == 1` → `汇信昌`，否则 `非汇信昌` |
| `category` | `spuCategoryName` 或 `spuPath` | |
| `lat` / `lng` | `lat` / `lon` | **lon → lng** |
| `address_masked` | `address` + 省市区 | PII 脱敏后 |
| `urgent` | `emergencyFlag`, `isNightEmergency`, 商品 `isNightEmergency` | 任一为真则 urgent |
| `enterprise_id` | `tenantId` | 可选 |
| `status` | `status` | 0=待分派 |
| `hotel_name` | `hotelName` | MVP 仅透传，不做托管路由 |

- **Output（工具层，PII 已脱敏）：**

```json
{
  "order_id": "11409",
  "order_no": "ORD202507030001",
  "biz_type": 2,
  "biz_type_name": "安装",
  "customer_type": "非汇信昌",
  "category": "窗帘安装",
  "lat": 31.23,
  "lng": 121.47,
  "address_masked": "上海市浦东新区***",
  "urgent": false,
  "enterprise_id": "0",
  "status": 0
}
```

- **Contract 测试：** mock `httpx` 返回 `tests/fixtures/order.api.response.json`

### 7.2 query_candidate_masters

- **Input:** `{ "order_id": "string" }`（内部先拉 order 再 SQL）
- **Source:** `DbClient.list_candidate_masters(order)` → MySQL **`hxc_cloud`**
- **Output:**

```json
{
  "masters": [
    {
      "master_id": "ad71795f-ed1b-4d61-bfd7-5fa664337b18",
      "master_name": "师傅6746",
      "profession_type": "安装",
      "skill_match": true,
      "skill_codes": "PL010104,PL010105",
      "free_ratio": 0.5,
      "lat": 22.661156,
      "lng": 113.922561,
      "company": 2,
      "service_city": "深圳市",
      "active_orders": 95
    }
  ],
  "count": 1
}
```

**表关联（MCP 已验证）：**

```text
master_users.id
  ← master_service_type_category.master_id
  ← master_service_area.master_id
  ← master_attendance.user_id (位置)
  ← order_order_master.master_id (在手单)

master_service_type_category.service_type_id → erp_service_type.code (LX001/002/003)
master_service_type_category.service_category_id → erp_service_category.id/code
master_service_area.service_city_id → master_service_area_tree.service_area_id
```

**订单 → SQL 参数：**

| Order 字段 | SQL 参数 | 示例 |
|------------|----------|------|
| `biz_type` | `:service_type_code` | 2 → `LX002` |
| 商品 `erpCode` | `:erp_code` | `PL010104` 精确匹配 |
| `city` | `:city_name` | `深圳市` |

**候选 SQL：** 见 `docs/sql/candidate_masters.sql`

**free_ratio MVP：** `clamp(1 - active_orders*0.01, 0, 1)`，`active_orders` 来自 `order_order_master` status∈{1,2,3,4}

**lat/lng：** 最新 `master_attendance_detail`；无打卡则 NULL

### 7.3 score_master_by_rule

- **Input:** `{ "order_id", "master_ids": [] }` 或全量候选
- **Source:** `domain.score`（纯计算）
- **Output:** `{ "rankings": [{ "master_id", "score", "breakdown": {} }] }`

**规则（MVP）：**

- R-HARD-01：skill_match 否则排除
- R-HARD-02：free_ratio >= 0.5 否则排除
- R-HARD-03：非汇信昌距离 >10km → 距离分 0
- 双轨距离公式见 Spec §6.2
- 可测：8km → 1.25；12km → 0

### 7.4 log_decision

- **Input:** `{ "session_id", "summary", "top3": [] }`
- **Source:** 写 SQLite + 返回 ack

**MVP 白名单仅此 4 工具**；Agent 若调用其他名称 → `invalid_tool_call`。

---

## 8. Guard Rules (MVP)

| Code | Rule | MVP |
|------|------|-----|
| R-HARD-01 | 技能完全匹配 | skill_match 字段 |
| R-HARD-02 | 空闲 ≥50% | free_ratio >= 0.5 |
| R-HARD-03 | 非汇信昌 >10km 距离分 0 | Haversine km |
| R-HARD-08 | master_id ∈ 白名单 | 当次 candidates 集合 |
| R-PHASE-01 | phase=1 禁止 assign | 无 assign 工具 in MVP |

`assign_order` 不在 MVP 工具列表；若 LLM 幻觉调用 → gateway 拒绝。

---

## 9. ReAct Loop

```text
state = { order_id, steps[], candidates[], rankings[] }
loop while step < MAX_STEPS and elapsed < T_SESSION:
  llm_out = LlmClient.next(state, tool_schemas, system_prompt)
  if llm_out.finish:
    return { top3, steps, session_id }
  tool = llm_out.tool_name
  if tool not in WHITELIST: observation = invalid_tool_call
  else: observation = ToolGateway.execute(tool, input, adapters)
  append step to SQLite
  state.update(observation)
escalate: return { status: ESCALATED, last_rankings, steps }
```

- **System Prompt：** 摘自 Spec §9.2，裁剪为 MVP 4 工具说明
- **单元测试：** `FakeLlm` 固定序列：`query_order_detail` → `query_candidate_masters` → `score_master_by_rule` → `finish`

---

## 10. API Surface (Demo)

| Method | Path | 说明 |
|--------|------|------|
| GET | `/health` | 200 OK |
| POST | `/demo/dispatch` | Body: `{ "order_id": "..." }` |
| GET | `/demo/sessions/{session_id}` | 决策回放 JSON |
| GET | `/` | 静态 UI |

**Response 示例：**

```json
{
  "session_id": "uuid",
  "status": "SUCCESS",
  "top3": [
    { "master_id": "M001", "score": 82.5, "reason": "距离近、空闲充足" }
  ],
  "steps": [
    { "step": 1, "tool": "query_order_detail", "duration_ms": 120, "guard": null }
  ],
  "guard_logs": [],
  "dry_run": true,
  "phase": 1
}
```

---

## 11. UI (Minimal)

- 输入框：`order_id`（默认 `TEST_ORDER_ID`）
- 按钮：「运行 Agent」
- 区域：
  - **Top3 推荐卡**（分数、理由）
  - **Tool 时间轴**（step / tool / ms / 摘要）
  - **Guard 日志**（若有）
  - **DRY_RUN / phase 标签**
- 样式：内联 CSS，无 Tailwind CDN

---

## 12. Testing Strategy (Superpowers TDD)

| 层 | 范围 | 命令 |
|----|------|------|
| Unit | score, guard, react_loop, gateway | `pytest tests/unit -v` |
| Contract | api_client mock httpx；db_client mock SQL | `pytest tests/contract -v` |
| Integration | 真实 API+DB+LLM | `INTEGRATION=1 pytest tests/integration -m integration` |

**Iron law：** 每个行为先 failing test → minimal impl → green → commit。

**Fake vs Real：**

- CI / 默认：`MOCK_MODE=true` 或 unit+contract only
- 本地联调：`.env` 填真实 API/DB，`INTEGRATION=1` smoke

---

## 13. Error Handling

| 场景 | 行为 |
|------|------|
| API 超时/4xx | observation 含 error；Agent 可 finish 或 escalate |
| DB 连接失败 | 503 + 明确 message；MOCK_MODE 可降级 fixture |
| LLM 超时 | session ESCALATED，附最后 score 结果 |
| 非法 tool | invalid_tool_call，计入 step |
| 无候选 | top3 空，status ESCALATED，reason `NO_CANDIDATES` |

---

## 14. Security

- `.env` / `CONTEXT.md` 不进 Git（`.gitignore`）
- 外发 LLM 前 PII 脱敏（地址/姓名/手机）
- DB 连接串只读用户；代码层禁止 INSERT/UPDATE/DELETE
- `DRY_RUN=true` 硬编码检查，写工具若 Phase 2 加入须双重开关

---

## 15. Phase 2 Backlog (Post-MVP)

1. `query_master_realtime` / presence API
2. `search_nearby_masters`（5km 托管场景）
3. `relax_rule` L2/L3
4. `escalate_to_human` + 归因码
5. 更多 R-HARD 与订单类型路由
6. 真实路线距离 API 替换 Haversine

---

## 16. Acceptance Criteria (Design Sign-off)

- [x] 用户确认 **API+DB 混合** 与本 MVP 边界
- [x] `CONTEXT.md` 已填 API 路径 + 候选 SQL + test order_id + LLM
- [x] 设计批准 → 生成 `docs/plans/2026-07-03-ai-dispatch-demo-impl.md`（Writing Plans）
- [x] TDD 实现后：`MOCK_MODE=true` 下 `pytest` 全绿 + 浏览器可演示
- [ ] `INTEGRATION=1` 下指定 `order_id` 可跑通 API+DB+LLM

---

## 17. Open Questions (待 CONTEXT 关闭)

| ID | 问题 | 状态 | 阻塞 |
|----|------|------|------|
| Q1 | 订单 API | **已关闭** | Base URL + Bearer + tenant-id Header |
| Q2 | 候选 SQL | **已关闭** | `docs/sql/candidate_masters.sql` |
| Q3 | customer_type | **已关闭** | `tenantId==1` → 汇信昌 |
| Q4 | lat/lng | **已关闭** | 最新打卡 |
| Q5 | LLM | **已关闭** | qwen-plus + DashScope URL；`LLM_API_KEY` 已填 `.env` |
| — | 联调 | 待 smoke | `DD20260702000005` → numeric id |

---

## Revision

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-07-03 | 初稿；确认 API+DB 混合 |
| v0.2 | 2026-07-03 | 填入订单详情 API：POST `/app-api/order/publish-order/get`；Order DTO 字段映射；fixture |
| v0.3 | 2026-07-03 | MCP 探测候选师傅：`hxc_cloud` 表关联 + `candidate_masters.sql` + candidates fixture |
| v0.4 | 2026-07-03 | 环境闭环：tenantId 汇信昌判定、测试 API/LLM、erpCode 精确匹配、order_no 解析 |
