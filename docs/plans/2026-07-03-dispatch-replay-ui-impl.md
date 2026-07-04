# 派单回放 UI 实现计划

> 设计文档：[`2026-07-03-dispatch-replay-ui-design.md`](./2026-07-03-dispatch-replay-ui-design.md)

## Task 1 — test_replay_classify

- 新建 `tests/unit/test_replay.py`（分类用例）
- 新建 `app/domain/replay.py` → `classify_candidate`
- 运行：`pytest tests/unit/test_replay.py -k classify`

## Task 2 — test_replay_matrix / conclusion / steps

- 实现 `build_candidate_matrix`、`build_conclusion`、`infer_scenario`、`build_replay_steps`、`build_replay_payload`
- 运行：`pytest tests/unit/test_replay.py`

## Task 3 — score_align_exclude

- 修改 `app/domain/score.py`：非汇信昌 >10km / 5–10km 不进 rankings
- 新增 `test_rank_excludes_over_10km` in `test_score.py`

## Task 4 — dispatch_api_replay

- `react_loop._loop_result` 增加 `candidates`、`rankings`
- `dispatch_service.run` 调用 `build_replay_payload`，扩展 session payload
- `get_session` 返回完整回放字段
- 更新 `test_dispatch_route.py`

## Task 5 — ui_replay

- 改造 `web/static/index.html` + `app.js`
- 验收：mock 订单 `11409` 页面含结论横幅 + 5 步 + 对比表

## Task 6 — git push

- `pytest tests/unit` 全绿后 commit
- `git push -u origin master:main`
