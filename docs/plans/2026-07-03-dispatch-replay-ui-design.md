# 派单回放 UI 设计 — P010 对齐

> 参考原型：`管理后台-P010-回放-情形08-师傅太远排除.html`  
> 策略：**混合** — UI 对齐 P010；步骤 1–3 为 Phase 1 说明性文案；步骤 4 为真实候选人对比表。

## API 扩展字段

`POST /demo/dispatch` 与 `GET /demo/sessions/{id}` 增加：

| 字段 | 说明 |
|------|------|
| `conclusion` | `{ headline, detail, tone }` |
| `scenario` | `{ code, label, badge }` |
| `replay_steps` | 5 步业务回放，含 `callout`、`compare_table` |
| `candidate_matrix` | 候选人分类行（selected/skip/exclude/ranked） |
| `total_duration_ms` / `total_duration_label` | 总耗时 |

## 候选人分类规则

- 技能不匹配 → exclude (`SKILL_MISMATCH`)
- 空闲度 < 50% → exclude (`LOW_FREE_RATIO`)
- 非汇信昌：>10km exclude；5–10km skip；≤5km 可评分
- 汇信昌：>100.5km exclude；其余可评分

## Phase 1 步骤 1–3

不接入真实商圈值守/专属规则，以 callout 标注「Phase 1 Demo 尚未接入」，引导用户关注步骤 4 对比表。
