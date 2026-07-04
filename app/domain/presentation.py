from __future__ import annotations

import re

TOOL_LABELS: dict[str, tuple[str, str]] = {
    "query_order_detail": ("查看订单信息", "已读取订单类型、地址等基本信息"),
    "query_candidate_masters": ("筛选候选师傅", "正在匹配技能与服务区域"),
    "score_master_by_rule": ("综合评分排序", "已按距离与空闲度排出推荐名单"),
    "log_decision": ("记录推荐结果", "推荐结果已保存"),
}

STATUS_LABELS = {
    "SUCCESS": "推荐完成",
    "ESCALATED": "未能完成推荐",
    "RUNNING": "处理中",
}

COMPANY_LABELS = {1: "汇信昌", 2: "其他公司"}


def format_duration_ms(duration_ms: int | None) -> str:
    ms = duration_ms or 0
    if ms < 1000:
        return f"用时 {ms} 毫秒"
    seconds = ms / 1000
    if seconds < 10:
        return f"用时 {seconds:.1f} 秒"
    return f"用时 {round(seconds)} 秒"


def _observation_detail(tool: str, observation: str) -> str:
    if not observation:
        return TOOL_LABELS.get(tool, (tool, ""))[1]

    if observation.startswith("error="):
        return f"步骤未完成：{observation.replace('error=', '')}"

    match = re.match(r"order_id=(\S+)", observation)
    if match:
        return f"已获取订单信息（编号 {match.group(1)}）"

    match = re.match(r"candidates=(\d+)", observation)
    if match:
        count = int(match.group(1))
        return f"找到 {count} 位符合条件的师傅"

    match = re.match(r"rankings=(\d+)", observation)
    if match:
        count = int(match.group(1))
        return f"已完成评分，产出 {count} 条推荐结果"

    if observation == "logged":
        return "推荐结果已记录"

    return observation


def humanize_steps(steps: list[dict]) -> list[dict]:
    humanized: list[dict] = []
    for step in steps:
        tool = step.get("tool") or ""
        title, default_detail = TOOL_LABELS.get(tool, (tool, "已完成"))
        observation = step.get("observation") or ""
        detail = _observation_detail(tool, observation) or default_detail
        humanized.append(
            {
                **step,
                "title": title,
                "detail": detail,
                "duration_label": format_duration_ms(step.get("duration_ms")),
            }
        )
    return humanized


def build_order_summary(
    order: dict | None,
    *,
    conclusion: dict | None = None,
    total_duration_label: str | None = None,
) -> dict | None:
    if not order:
        return None
    summary = {
        "order_no": order.get("order_no") or order.get("order_id") or "",
        "biz_type_name": order.get("biz_type_name") or "",
        "category": order.get("category") or "",
        "city": order.get("city") or "",
        "customer_type": order.get("customer_type") or "",
        "urgent": bool(order.get("urgent")),
        "address_masked": order.get("address_masked") or "",
    }
    if conclusion:
        summary["dispatch_result_label"] = conclusion.get("headline", "").replace("结论：", "")
    if total_duration_label:
        summary["total_duration_label"] = total_duration_label
    return summary


def enrich_top3(
    rankings: list[dict] | None,
    candidates: list[dict] | None,
) -> list[dict]:
    if not rankings:
        return []

    candidate_map = {str(c.get("master_id")): c for c in (candidates or [])}
    enriched: list[dict] = []

    for rank, item in enumerate(rankings[:3], start=1):
        master_id = str(item.get("master_id", ""))
        candidate = candidate_map.get(master_id, {})
        company = candidate.get("company")
        enriched.append(
            {
                "rank": rank,
                "master_id": master_id,
                "master_name": candidate.get("master_name") or "未知师傅",
                "nbs_id": candidate.get("nbs_id") or "",
                "profession_type": candidate.get("profession_type") or "",
                "service_city": candidate.get("service_city") or "",
                "company_label": COMPANY_LABELS.get(company, ""),
                "score": item.get("score"),
                "reason": item.get("reason") or "",
                "breakdown": item.get("breakdown") or {},
            }
        )
    return enriched
