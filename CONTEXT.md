# AI 智能体派单 Demo — 环境上下文

> **密钥（Bearer Token、LLM API Key、DB 密码）只写在 `.env`**（已 gitignore）。本文件可提交，不含敏感值。

## 已确认

- **数据来源：** API + DB 混合 — **订单走 API**，**候选师傅池走只读 MySQL SQL**
- **冲突优先级：** 订单字段以 API 为准；候选列表以 DB 为准
- **约束：** DRY_RUN=true，DISPATCH_PHASE=1，DB 只读

---

## 已填写 — 订单详情 API（Q1 关闭）

### 接口契约

| 项 | 值 |
|----|-----|
| Base URL | `http://192.168.2.223:18080` |
| Path | `/app-api/order/publish-order/get` |
| Method | **POST** |
| Content-Type | `application/json` |
| 鉴权 | `Authorization: Bearer <API_TOKEN>`（见 `.env`） |
| 租户 Header | **`tenant-id: <data.tenantId>`**（必填；缺省报「租户标识未传递」） |
| Request Body | `{ "id": <numeric_id> }` — **integer(int64)**，非 orderNo |
| 成功判定 | `code === 0` |
| Fixture | `tests/fixtures/order.api.response.json` |

### 测试订单

| 项 | 值 |
|----|-----|
| 测试 order_no（UI 输入） | `DD20260702000005` |
| 解析策略 | 若输入以 `DD` 开头 → DB `order_order.order_no` 查 `id` + `tenant_id` → 再调 API |
| numeric `id` | 联调时写入 `.env` 的 `TEST_ORDER_ID`（首次 smoke 后回填） |

> MCP 库 `hxc_cloud` 当前**未查到**该 order_no，订单应存在于 `192.168.2.223` 测试环境。Demo 实现需支持 order_no → id 解析。

### 响应 → Demo Order DTO 映射

| Demo 字段 | API 字段 | 转换规则 |
|-----------|----------|----------|
| `order_id` | `data.id` | `str(data.id)` |
| `order_no` | `data.orderNo` | |
| `biz_type` | `data.bizType` | 1测量 / 2安装 / 3单次维修 / 4质保维修 |
| `biz_type_name` | 枚举或 `data.spuTypeName` | |
| `category` | `data.spuCategoryName` 或 `data.spuPath` | |
| `lat` / `lng` | `data.lat` / `data.lon` | |
| `customer_type` | `data.tenantId` | **`tenantId == 1` → 汇信昌；否则 → 非汇信昌** |
| `tenant_id` | `data.tenantId` | 同时用于 API `tenant-id` Header |
| `erp_codes` | `goodsSaveReqVOList[].erpCode` | 候选 SQL **精确匹配**（见下） |
| `urgent` | `emergencyFlag` + `isNightEmergency` + 商品紧急度 | 复合 |
| `status` | `data.status` | 0=待分派 |

### customer_type（Q3 已关闭）

```python
customer_type = "汇信昌" if tenant_id == 1 else "非汇信昌"
```

配置项：`HX_TENANT_ID=1`（`.env`）

### PII 脱敏（外发 LLM 前）

| 字段 | 处理 |
|------|------|
| `contacts` / `phone` | 掩码 |
| `address` | 省市区 + `***` |

---

## 已填写 — 候选师傅 DB（Q2/Q4 关闭）

> 库名 **`hxc_cloud`**（MySQL MCP 已验证）

### 关键表

| 用途 | 表名 |
|------|------|
| 师傅 | `master_users` |
| 技能 | `master_service_type_category` → `erp_service_category` / `erp_service_type` |
| 区域 | `master_service_area` + `master_service_area_tree` |
| 位置 | `master_attendance` + `master_attendance_detail` |
| 在手单 | `order_order_master` |

### 技能匹配（已确认）

- **粒度：erpCode 精确匹配**
- 来源：订单 API `goodsSaveReqVOList[].erpCode`
- SQL：`erp_service_category.code = :erp_code`（见 `docs/sql/candidate_masters.sql`）
- 多商品：对每个 `erpCode` 查候选后 **union 去重**（按 `master_id`）

### bizType → service_type_code

| bizType | code |
|---------|------|
| 1 | LX001 |
| 2 | LX002 |
| 3 | LX003 |
| 4 | LX003 |

### free_ratio（MVP）

`clamp(1.0 - active_orders * 0.01, 0, 1)`，`active_orders` 来自 `order_order_master` status∈{1,2,3,4}

Fixture：`tests/fixtures/candidates.json`

---

## 已填写 — LLM（Q5 关闭）

| 项 | 值 |
|----|-----|
| Base URL | `https://llm-tgefxsufbpuip2bt.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` |
| Model | `qwen-plus` |
| API Key | 已写入 `.env` 的 `LLM_API_KEY` |
| 协议 | OpenAI-compatible（function calling） |

---

## Open Questions 剩余

| ID | 状态 |
|----|------|
| Q1 订单 API | ✅ 已关闭 |
| Q2 候选 SQL | ✅ 已关闭 |
| Q3 customer_type | ✅ 已关闭（tenantId==1） |
| Q4 lat/lng | ✅ 已关闭（打卡表） |
| Q5 LLM | ✅ 已关闭（缺 API Key） |
| — | `LLM_API_KEY` | ✅ 已填 |
| — | `DD20260702000005` numeric `id` | 联调 smoke 后回填 |

---

## P1（Phase 2）

- 路线距离 API / presence API
