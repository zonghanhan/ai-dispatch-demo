TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "query_order_detail",
            "description": "查询订单详情（API），返回脱敏后的订单字段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "订单 numeric id 或 DD 开头 order_no",
                    }
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_candidate_masters",
            "description": "根据订单技能/区域从 DB 查询候选师傅池。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "订单 id，须先 query_order_detail",
                    }
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_master_by_rule",
            "description": "按派单规则对候选师傅打分排序。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "订单 id",
                    },
                    "master_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可选，限定评分的师傅 id 子集",
                    },
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_decision",
            "description": "记录 Agent 决策摘要（审计 ack）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "summary": {"type": "string"},
                    "top3": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                },
                "required": ["session_id", "summary"],
            },
        },
    },
]
