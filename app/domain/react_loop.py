from __future__ import annotations

import time
import uuid

from app.config import Settings
from app.domain.presentation import enrich_top3
from app.tools.gateway import ToolGateway
from app.tools.registry import TOOL_SCHEMAS

_SYSTEM_PROMPT = (
    "你是智能派单助手。请按顺序调用工具：先查订单、再查候选师傅、再规则打分，"
    "最后输出 Top3 推荐。仅可使用提供的 4 个工具。"
)


def _summarize_observation(observation: dict) -> str:
    if observation.get("error"):
        codes = observation.get("codes") or []
        if codes:
            return f"error={observation['error']} codes={','.join(codes)}"
        return f"error={observation['error']}"
    if "order_id" in observation and "rankings" not in observation and "masters" not in observation:
        return f"order_id={observation['order_id']}"
    if "count" in observation:
        return f"candidates={observation['count']}"
    if "rankings" in observation:
        return f"rankings={len(observation['rankings'])}"
    if observation.get("logged"):
        return "logged"
    return "ok"


def _top3_from_state(session_state: dict, llm_top3: list | None = None) -> list:
    rankings = llm_top3 if llm_top3 else session_state.get("rankings") or []
    return enrich_top3(rankings[:3], session_state.get("candidates"))


def _loop_result(
    status: str,
    session_state: dict,
    steps: list[dict],
    session_id: str,
    llm_top3: list | None = None,
) -> dict:
    return {
        "status": status,
        "top3": _top3_from_state(session_state, llm_top3),
        "steps": steps,
        "session_id": session_id,
        "order": session_state.get("order"),
        "candidates": session_state.get("candidates"),
        "rankings": session_state.get("rankings"),
    }


def run_react_loop(
    order_key: str,
    llm,
    gateway: ToolGateway,
    settings: Settings,
    session_id: str | None = None,
) -> dict:
    session_id = session_id or str(uuid.uuid4())
    session_state: dict = {"order_id": order_key, "steps": []}
    steps: list[dict] = []
    start = time.monotonic()

    for step_num in range(1, settings.max_steps + 1):
        if time.monotonic() - start >= settings.t_session_sec:
            break

        llm_out = llm.next(session_state, TOOL_SCHEMAS, _SYSTEM_PROMPT)

        if llm_out.get("finish"):
            return _loop_result(
                "SUCCESS",
                session_state,
                steps,
                session_id,
                llm_out.get("top3"),
            )

        tool_name = llm_out.get("tool_name", "")
        tool_input = llm_out.get("tool_input") or {}

        t0 = time.monotonic()
        observation = gateway.execute(tool_name, tool_input, session_state)
        duration_ms = int((time.monotonic() - t0) * 1000)

        step_record = {
            "step": step_num,
            "tool": tool_name,
            "duration_ms": duration_ms,
            "observation": _summarize_observation(observation),
        }
        steps.append(step_record)
        session_state["steps"].append(step_record)

    return _loop_result("ESCALATED", session_state, steps, session_id)
