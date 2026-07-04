# AI 智能体派单 Demo

Guarded Agent（ReAct + 规则护栏）本地演示项目。

- **设计文档：** [docs/plans/2026-07-03-ai-dispatch-demo-design.md](docs/plans/2026-07-03-ai-dispatch-demo-design.md)
- **产品 Spec：** 见知识库 `AI智能体派单需求文档.md`

## 数据策略

- **订单：** 测试环境 HTTP API
- **候选师傅池：** 只读 MySQL SQL
- **安全：** `DRY_RUN=true`，`DISPATCH_PHASE=1`

## 快速开始

```bash
cd D:\ai-dispatch-demo
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
# 编辑 .env 与 CONTEXT.md
pytest tests/unit tests/contract -v
uvicorn app.main:app --reload
# 浏览器 http://127.0.0.1:8000
```

## 测试

**默认（单元 + 契约，不含联调）：**

```bash
pytest tests/unit tests/contract -v
```

**联调（真实 API / DB / LLM，需 `.env` 中 `MOCK_MODE=false`）：**

```bash
set INTEGRATION=1
pytest tests/integration -m integration -v
```

## 环境清单

见 [CONTEXT.md](CONTEXT.md).
