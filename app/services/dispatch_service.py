from __future__ import annotations

import httpx

from app.adapters.api_client import ApiClient
from app.adapters.db_client import DbClient
from app.adapters.llm_client import LlmClient
from app.config import Settings
from app.domain.presentation import build_order_summary, humanize_steps
from app.domain.react_loop import run_react_loop
from app.domain.replay import build_replay_payload
from app.persistence.sqlite import SessionStore
from app.tools.gateway import ToolGateway


class _FakeLlm:
    def __init__(self, order_key: str) -> None:
        self._steps = iter(
            [
                {"tool_name": "query_order_detail", "tool_input": {"order_id": order_key}},
                {"tool_name": "query_candidate_masters", "tool_input": {"order_id": order_key}},
                {"tool_name": "score_master_by_rule", "tool_input": {"order_id": order_key}},
                {"finish": True, "top3": [{"master_id": "M001", "score": 90.0}]},
            ]
        )

    def next(self, state: dict, tool_schemas: list[dict], system_prompt: str) -> dict:
        step = next(self._steps)
        if step.get("finish"):
            rankings = state.get("rankings") or []
            if rankings:
                return {"finish": True, "top3": rankings[:3]}
        return step


class _LlmWithFallback:
    def __init__(self, settings: Settings, order_key: str) -> None:
        self._llm = LlmClient(settings)
        self._fallback = _FakeLlm(order_key)
        self._using_fallback = False

    def next(self, state: dict, tool_schemas: list[dict], system_prompt: str) -> dict:
        if self._using_fallback:
            return self._fallback.next(state, tool_schemas, system_prompt)
        try:
            return self._llm.next(state, tool_schemas, system_prompt)
        except Exception:
            self._using_fallback = True
            return self._fallback.next(state, tool_schemas, system_prompt)


class DispatchService:
    def __init__(self, settings: Settings, llm=None) -> None:
        self._settings = settings
        self._llm_override = llm
        self._store = SessionStore(settings)
        self._store.init_db()
        http = httpx.Client()
        self._api = ApiClient(settings, http)
        self._db = DbClient(settings)
        self._gateway = ToolGateway(settings, self._api, self._db)

    def _build_llm(self, order_key: str):
        if self._llm_override is not None:
            return self._llm_override
        if self._settings.mock_mode:
            return _FakeLlm(order_key)
        if self._settings.llm_fallback:
            return _LlmWithFallback(self._settings, order_key)
        return LlmClient(self._settings)

    def run(self, order_id: str) -> dict:
        order_key = order_id.strip()
        session_id = self._store.create_session(order_id, "RUNNING")
        llm = self._build_llm(order_key)

        result = run_react_loop(
            order_key=order_key,
            llm=llm,
            gateway=self._gateway,
            settings=self._settings,
            session_id=session_id,
        )

        for step in result["steps"]:
            self._store.append_tool_call(
                session_id,
                step["step"],
                step["tool"],
                step["duration_ms"],
                {"summary": step["observation"]},
            )

        total_ms = sum(step.get("duration_ms", 0) for step in result["steps"])
        replay = build_replay_payload(
            result.get("order"),
            result.get("candidates"),
            result.get("top3", []),
            total_ms,
            dry_run=self._settings.dry_run,
        )
        order_summary = build_order_summary(
            result.get("order"),
            conclusion=replay["conclusion"],
            total_duration_label=replay["total_duration_label"],
        )

        payload = {
            "top3": result.get("top3", []),
            "order_summary": order_summary,
            **replay,
        }
        self._store.update_session_status(session_id, result["status"], payload)

        return {
            "session_id": session_id,
            "status": result["status"],
            "status_label": "推荐完成" if result["status"] == "SUCCESS" else "未能完成推荐",
            "top3": result.get("top3", []),
            "order_summary": order_summary,
            "steps": humanize_steps(result["steps"]),
            "guard_logs": [],
            "dry_run": self._settings.dry_run,
            "phase": self._settings.dispatch_phase,
            **replay,
        }

    def get_session(self, session_id: str) -> dict | None:
        session = self._store.get_session(session_id)
        if session is None:
            return None

        payload = session.get("payload") or {}
        steps_raw = session.get("steps") or []
        human_steps = []
        for step in steps_raw:
            obs = step.get("observation")
            if isinstance(obs, dict):
                observation = obs.get("summary") or ""
            else:
                observation = obs or ""
            human_steps.append(
                {
                    "step": step["step"],
                    "tool": step["tool"],
                    "duration_ms": step["duration_ms"],
                    "observation": observation,
                }
            )

        return {
            "session_id": session["session_id"],
            "order_id": session["order_id"],
            "status": session["status"],
            "status_label": "推荐完成" if session["status"] == "SUCCESS" else "未能完成推荐",
            "created_at": session.get("created_at"),
            "top3": payload.get("top3", []),
            "order_summary": payload.get("order_summary"),
            "steps": humanize_steps(human_steps),
            "dry_run": self._settings.dry_run,
            "phase": self._settings.dispatch_phase,
            "conclusion": payload.get("conclusion"),
            "scenario": payload.get("scenario"),
            "replay_steps": payload.get("replay_steps", []),
            "candidate_matrix": payload.get("candidate_matrix", []),
            "total_duration_ms": payload.get("total_duration_ms"),
            "total_duration_label": payload.get("total_duration_label"),
        }
