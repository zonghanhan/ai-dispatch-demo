from app.domain.presentation import (
    build_order_summary,
    enrich_top3,
    format_duration_ms,
    humanize_steps,
)


def test_enrich_top3_merges_candidate_fields():
    rankings = [
        {
            "master_id": "aeb790a58e46432e8f8497cd0e7d9246",
            "score": 5.8,
            "reason": "距订单约 3.2 公里，当前空闲度 100%",
            "breakdown": {"distance_km": 3.2},
        }
    ]
    candidates = [
        {
            "master_id": "aeb790a58e46432e8f8497cd0e7d9246",
            "master_name": "宗含含",
            "nbs_id": "A0454",
            "profession_type": "安装",
            "service_city": "深圳市",
            "company": 1,
        }
    ]

    result = enrich_top3(rankings, candidates)

    assert len(result) == 1
    assert result[0]["rank"] == 1
    assert result[0]["master_name"] == "宗含含"
    assert result[0]["nbs_id"] == "A0454"
    assert result[0]["profession_type"] == "安装"
    assert result[0]["service_city"] == "深圳市"
    assert result[0]["company_label"] == "汇信昌"
    assert result[0]["score"] == 5.8
    assert "3.2 公里" in result[0]["reason"]


def test_enrich_top3_unknown_master_fallback():
    result = enrich_top3([{"master_id": "unknown", "score": 1.0, "reason": "test"}], [])
    assert result[0]["master_name"] == "未知师傅"
    assert result[0]["nbs_id"] == ""


def test_humanize_steps_maps_tools_to_chinese():
    steps = [
        {
            "step": 1,
            "tool": "query_order_detail",
            "duration_ms": 120,
            "observation": "order_id=243",
        },
        {
            "step": 2,
            "tool": "query_candidate_masters",
            "duration_ms": 850,
            "observation": "candidates=3",
        },
        {
            "step": 3,
            "tool": "score_master_by_rule",
            "duration_ms": 45,
            "observation": "rankings=3",
        },
    ]

    result = humanize_steps(steps)

    assert result[0]["title"] == "查看订单信息"
    assert "243" in result[0]["detail"]
    assert result[0]["duration_label"] == "用时 120 毫秒"
    assert result[1]["title"] == "筛选候选师傅"
    assert "3 位" in result[1]["detail"]
    assert result[2]["title"] == "综合评分排序"
    assert "3 条" in result[2]["detail"]


def test_format_duration_ms_seconds():
    assert format_duration_ms(1500) == "用时 1.5 秒"
    assert format_duration_ms(12000) == "用时 12 秒"


def test_build_order_summary():
    summary = build_order_summary(
        {
            "order_no": "DD20250102000023",
            "biz_type_name": "安装",
            "category": "窗帘",
            "city": "深圳市",
            "customer_type": "汇信昌",
            "urgent": True,
            "address_masked": "广东省***",
        }
    )

    assert summary["order_no"] == "DD20250102000023"
    assert summary["biz_type_name"] == "安装"
    assert summary["urgent"] is True
