from __future__ import annotations

import json

import httpx

from app.config import Settings


class LlmError(Exception):
    def __init__(self, msg: str) -> None:
        self.msg = msg
        super().__init__(msg)


class LlmClient:
    def __init__(self, settings: Settings, http_client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._http = http_client or httpx.Client()

    def next(self, state: dict, tool_schemas: list[dict], system_prompt: str) -> dict:
        url = f"{self._settings.llm_base_url.rstrip('/')}/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self._settings.llm_api_key}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(state, ensure_ascii=False)},
        ]
        payload = {
            "model": self._settings.llm_model,
            "messages": messages,
            "tools": tool_schemas,
        }

        response = self._http.post(
            url,
            json=payload,
            headers=headers,
            timeout=self._settings.llm_timeout_sec,
        )
        if response.is_error:
            raise LlmError(self._format_error(response))
        return self._parse_response(response.json())

    def _format_error(self, response: httpx.Response) -> str:
        try:
            body = response.json()
            err = body.get("error") or {}
            message = err.get("message") or body.get("msg") or response.text
            code = err.get("code") or err.get("type") or response.status_code
            return f"LLM HTTP {response.status_code} ({code}): {message}"
        except Exception:
            return f"LLM HTTP {response.status_code}: {response.text[:200]}"

    def _parse_response(self, data: dict) -> dict:
        choices = data.get("choices") or []
        if not choices:
            return {"finish": True, "top3": []}

        message = choices[0].get("message") or {}
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            fn = tool_calls[0].get("function") or {}
            name = fn.get("name", "")
            args_raw = fn.get("arguments") or "{}"
            if isinstance(args_raw, str):
                tool_input = json.loads(args_raw)
            else:
                tool_input = args_raw
            return {"tool_name": name, "tool_input": tool_input}

        content = (message.get("content") or "").strip()
        if content:
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and parsed.get("finish"):
                    return {"finish": True, "top3": parsed.get("top3", [])}
            except json.JSONDecodeError:
                pass

        return {"finish": True, "top3": []}
