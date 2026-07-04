from __future__ import annotations

from app.domain.distance import haversine_km
from app.domain.models import MasterCandidate, Order
from app.domain.presentation import format_duration_ms

PHASE1_CALLOUT = "Phase 1 Demo 尚未接入该规则，本步骤为说明性回放；真实路径以步骤 4 评分结果为准。"


def _distance_km(order: Order, master: MasterCandidate) -> float:
    if order.lat is None or order.lng is None or master.lat is None or master.lng is None:
        return 999.0
    return haversine_km(order.lat, order.lng, master.lat, master.lng)


def _distance_label(km: float) -> str:
    if km >= 900:
        return "距离未知"
    return f"{km:.1f} 公里"


def _row(
    master: MasterCandidate,
    km: float,
    *,
    status: str,
    status_label: str,
    reason_code: str,
    reason_text: str,
) -> dict:
    return {
        "master_id": str(master.master_id),
        "master_name": master.master_name or "未知师傅",
        "nbs_id": master.nbs_id or "",
        "distance_km": round(km, 2) if km < 900 else None,
        "distance_label": _distance_label(km),
        "status": status,
        "status_label": status_label,
        "reason_code": reason_code,
        "reason_text": reason_text,
    }


def classify_candidate(
    order: Order,
    master: MasterCandidate,
    top3_ids: list[str],
) -> dict:
    km = _distance_km(order, master)
    master_id = str(master.master_id)
    top_set = {str(mid) for mid in top3_ids}

    if not master.skill_match:
        return _row(
            master,
            km,
            status="exclude",
            status_label="直接排除",
            reason_code="SKILL_MISMATCH",
            reason_text="技能与订单商品不匹配",
        )

    if master.free_ratio < 0.5:
        return _row(
            master,
            km,
            status="exclude",
            status_label="直接排除",
            reason_code="LOW_FREE_RATIO",
            reason_text=f"空闲度 {master.free_ratio:.0%}，低于 50% 门槛",
        )

    if order.customer_type == "非汇信昌":
        if km > 10:
            return _row(
                master,
                km,
                status="exclude",
                status_label="直接排除",
                reason_code="DIST_OVER_10KM",
                reason_text="超过 10 公里硬上限",
            )
        if km > 5:
            return _row(
                master,
                km,
                status="skip",
                status_label="不参与",
                reason_code="DIST_5_10KM",
                reason_text="在 5～10 公里区间，不参与评分",
            )
    elif km > 100.5:
        return _row(
            master,
            km,
            status="exclude",
            status_label="直接排除",
            reason_code="DIST_OVER_100KM",
            reason_text="超过汇信昌距离上限",
        )

    if top3_ids and master_id == top3_ids[0]:
        return _row(
            master,
            km,
            status="selected",
            status_label="选中",
            reason_code="TOP1",
            reason_text="综合分最高，首选推荐",
        )

    if master_id in top_set:
        return _row(
            master,
            km,
            status="ranked",
            status_label="备选推荐",
            reason_code="TOP3",
            reason_text="进入 Top3 备选名单",
        )

    return _row(
        master,
        km,
        status="ranked",
        status_label="未入选",
        reason_code="LOW_SCORE",
        reason_text="符合硬性条件，综合分未进 Top3",
    )


def build_candidate_matrix(
    order: Order,
    candidates: list[MasterCandidate],
    top3_ids: list[str],
) -> list[dict]:
    rows = [classify_candidate(order, master, top3_ids) for master in candidates]
    rows.sort(key=lambda row: (row["distance_km"] is None, row["distance_km"] or 9999))
    return rows


def infer_scenario(matrix: list[dict], order: Order) -> dict:
    if not matrix:
        return {
            "code": "no_candidate",
            "label": "情形 · 无可用师傅",
            "badge": "fail",
        }

    if any(row.get("reason_code") == "DIST_OVER_10KM" for row in matrix):
        return {
            "code": "distance_exclude",
            "label": "情形 · 距离排除",
            "badge": "warn",
        }

    if any(row.get("reason_code") == "DIST_5_10KM" for row in matrix):
        return {
            "code": "distance_skip",
            "label": "情形 · 距离不参与",
            "badge": "warn",
        }

    if all(row["status"] in {"exclude", "skip"} for row in matrix):
        return {
            "code": "no_candidate",
            "label": "情形 · 无可用师傅",
            "badge": "fail",
        }

    if order.urgent:
        return {
            "code": "urgent_recommend",
            "label": "情形 · 紧急单推荐",
            "badge": "ok",
        }

    return {
        "code": "normal_recommend",
        "label": "情形 · 规则评分推荐",
        "badge": "ok",
    }


def build_conclusion(order: Order, matrix: list[dict], top3: list[dict]) -> dict:
    selected = next((row for row in matrix if row["status"] == "selected"), None)
    if selected is None and top3:
        selected = {
            "master_name": top3[0].get("master_name") or "未知师傅",
            "distance_label": _extract_distance(top3[0].get("reason") or ""),
        }

    excluded = next(
        (
            row
            for row in matrix
            if row["status"] == "exclude" and row.get("reason_code") == "DIST_OVER_10KM"
        ),
        None,
    )
    if excluded is None:
        excluded = next((row for row in matrix if row["status"] == "exclude"), None)

    if selected and excluded:
        headline = (
            f"结论：{excluded['master_name']} {excluded['distance_label']}被排除，"
            f"推荐{selected['master_name']}"
        )
        detail = (
            f"{excluded['master_name']}因{excluded['reason_text']}被排除；"
            f"{selected['master_name']}距订单{selected['distance_label']}，"
            f"综合评分最高，作为首选推荐。"
        )
        tone = "warn"
    elif selected:
        headline = f"结论：推荐 {selected['master_name']} 作为首选师傅"
        detail = (
            f"{selected['master_name']}距订单{selected['distance_label']}，"
            f"通过距离与空闲度综合评分，排名第一。"
        )
        tone = "ok"
    elif top3:
        name = top3[0].get("master_name") or "未知师傅"
        headline = f"结论：推荐 {name} 作为首选师傅"
        detail = top3[0].get("reason") or "已完成规则评分。"
        tone = "ok"
    else:
        headline = "结论：未能找到符合条件的推荐师傅"
        detail = "所有候选人均未通过硬性筛选或评分，建议转人工处理。"
        tone = "fail"

    return {"headline": headline, "detail": detail, "tone": tone}


def _extract_distance(reason: str) -> str:
    if "公里" in reason:
        start = reason.find("约")
        if start >= 0:
            end = reason.find("公里", start)
            if end >= 0:
                return reason[start + 1 : end + 2]
    return "距离未知"


def build_replay_steps(
    order: Order,
    matrix: list[dict],
    top3: list[dict],
    total_ms: int,
    *,
    dry_run: bool,
) -> list[dict]:
    urgent_hint = "紧急单" if order.urgent else "普通单"
    biz_label = order.biz_type_name or "托管维修"

    compare_table = [
        {
            "master_name": row["master_name"],
            "distance_label": row["distance_label"],
            "reason_text": row["reason_text"],
            "status_label": row["status_label"],
            "status": row["status"],
        }
        for row in matrix
    ]

    selected_name = top3[0]["master_name"] if top3 else "暂无"
    dispatch_mode = "推荐模式（未真实派单）" if dry_run else "联调模式"

    return [
        {
            "step": 1,
            "title": "检查是否命中商圈值守范围",
            "body": (
                f"系统查询商圈值守范围：订单所在{'城市 ' + order.city if order.city else '区域'}"
                f"在 Phase 1 Demo 中未接入值守规则数据，本步标记为<strong>未命中</strong>，跳过值守路径。"
            ),
            "callout": {"type": "info", "text": PHASE1_CALLOUT},
            "compare_table": None,
        },
        {
            "step": 2,
            "title": "检查酒店专属师傅",
            "body": (
                "Phase 1 Demo 尚未接入专属师傅与请假状态。"
                "若生产环境专属无法正常派单，系统将自动进入附近维修匹配路径。"
            ),
            "callout": {
                "type": "warn",
                "text": "说明：专属正常派单走不通时，自动进入「按距离与空闲度规则评分」路径。",
            },
            "compare_table": None,
        },
        {
            "step": 3,
            "title": "进入规则评分匹配",
            "body": (
                f"订单类型为 {biz_label} · {urgent_hint}。"
                "Phase 1 使用候选师傅池 + 距离/空闲度规则进行综合评分。"
            ),
            "callout": None,
            "compare_table": None,
        },
        {
            "step": 4,
            "title": "按距离规则筛选候选人",
            "body": (
                "· <strong>5 公里以内</strong>：可参与评分<br>"
                "· <strong>5～10 公里</strong>：不参与评分（非汇信昌）<br>"
                "· <strong>超过 10 公里</strong>：直接从名单剔除（非汇信昌）"
            ),
            "callout": None,
            "compare_table": compare_table,
        },
        {
            "step": 5,
            "title": "输出推荐结果",
            "body": (
                f"系统完成评分，首选推荐 <strong>{selected_name}</strong>。"
                f"本次为{dispatch_mode}，总耗时 {format_duration_ms(total_ms)}。"
            ),
            "callout": None,
            "compare_table": None,
        },
    ]


def build_replay_payload(
    order: Order | dict | None,
    candidates: list[dict] | None,
    top3: list[dict],
    total_ms: int,
    *,
    dry_run: bool,
) -> dict:
    if order is None:
        return {
            "conclusion": {
                "headline": "结论：订单信息不可用",
                "detail": "未能读取订单，无法生成回放。",
                "tone": "fail",
            },
            "scenario": {"code": "unknown", "label": "情形 · 未知", "badge": "fail"},
            "replay_steps": [],
            "candidate_matrix": [],
            "total_duration_ms": total_ms,
            "total_duration_label": format_duration_ms(total_ms),
        }

    order_model = order if isinstance(order, Order) else Order.model_validate(order)
    master_models = [MasterCandidate.model_validate(c) for c in (candidates or [])]
    top3_ids = [str(item.get("master_id", "")) for item in top3 if item.get("master_id")]

    matrix = build_candidate_matrix(order_model, master_models, top3_ids)
    conclusion = build_conclusion(order_model, matrix, top3)
    scenario = infer_scenario(matrix, order_model)
    replay_steps = build_replay_steps(
        order_model,
        matrix,
        top3,
        total_ms,
        dry_run=dry_run,
    )

    return {
        "conclusion": conclusion,
        "scenario": scenario,
        "replay_steps": replay_steps,
        "candidate_matrix": matrix,
        "total_duration_ms": total_ms,
        "total_duration_label": format_duration_ms(total_ms),
    }
