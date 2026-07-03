import json

import httpx

from app.adapters.llm_client import LlmClient
from app.config import Settings
from app.tools.registry import TOOL_SCHEMAS


def test_next_parses_tool_calls_from_chat_completion():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "query_order_detail",
                                        "arguments": json.dumps({"order_id": "11409"}),
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    settings = Settings(
        llm_base_url="http://llm.test/v1",
        llm_api_key="sk-test",
        llm_model="qwen-plus",
    )
    transport = httpx.MockTransport(handler)
    client = LlmClient(settings, httpx.Client(transport=transport))

    state = {"order_id": "11409", "steps": []}
    result = client.next(state, TOOL_SCHEMAS, "system prompt")

    assert result == {
        "tool_name": "query_order_detail",
        "tool_input": {"order_id": "11409"},
    }
    assert captured["url"] == "http://llm.test/v1/chat/completions"
    assert captured["body"]["model"] == "qwen-plus"
    assert captured["body"]["tools"] == TOOL_SCHEMAS
    assert captured["body"]["messages"][0] == {"role": "system", "content": "system prompt"}
    assert json.loads(captured["body"]["messages"][1]["content"]) == state
    assert captured["headers"].get("authorization") == "Bearer sk-test"


def test_next_parses_finish_json_from_content():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "finish": True,
                                    "top3": [{"master_id": "M001", "score": 90.0}],
                                }
                            ),
                        }
                    }
                ]
            },
        )

    settings = Settings(llm_base_url="http://llm.test/v1", llm_model="qwen-plus")
    transport = httpx.MockTransport(handler)
    client = LlmClient(settings, httpx.Client(transport=transport))

    result = client.next({"order_id": "11409", "steps": []}, TOOL_SCHEMAS, "system")

    assert result == {
        "finish": True,
        "top3": [{"master_id": "M001", "score": 90.0}],
    }


def test_next_returns_finish_when_no_tool_calls():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "done",
                        }
                    }
                ]
            },
        )

    settings = Settings(llm_base_url="http://llm.test/v1")
    transport = httpx.MockTransport(handler)
    client = LlmClient(settings, httpx.Client(transport=transport))

    result = client.next({}, TOOL_SCHEMAS, "system")

    assert result == {"finish": True, "top3": []}
