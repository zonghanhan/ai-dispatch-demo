from app.domain.distance import haversine_km
from app.domain.models import MasterCandidate, Order, RankingItem


def distance_score(km: float, customer_type: str) -> float:
    if km <= 0.5:
        return 5.0
    if customer_type == "汇信昌":
        if km > 100.5:
            return 0.0
        return max(0.0, 5.0 - (km - 0.5) * 0.05)
    if km > 10.0:
        return 0.0
    return max(0.0, 5.0 - (km - 0.5) * 0.5)


def rank_masters(order: Order, masters: list[MasterCandidate]) -> list[RankingItem]:
    items: list[RankingItem] = []
    for m in masters:
        if not m.skill_match:
            continue
        if m.free_ratio < 0.5:
            continue
        if order.lat is None or order.lng is None or m.lat is None or m.lng is None:
            km = 999.0
        else:
            km = haversine_km(order.lat, order.lng, m.lat, m.lng)
        d_score = distance_score(km, order.customer_type)
        if order.customer_type == "非汇信昌" and km > 10:
            d_score = 0.0
        total = d_score + m.free_ratio
        if km >= 900:
            distance_text = "距离信息暂不可用"
        else:
            distance_text = f"距订单约 {km:.1f} 公里"
        reason = (
            f"{distance_text}，当前空闲度 {m.free_ratio:.0%}，"
            f"擅长{m.profession_type or '相关工种'}，"
            f"服务区域：{m.service_city or '未知'}"
        )
        items.append(RankingItem(
            master_id=m.master_id,
            score=round(total, 2),
            breakdown={"distance_km": round(km, 2), "distance_score": d_score, "free_ratio": m.free_ratio},
            reason=reason,
        ))
    items.sort(key=lambda x: x.score, reverse=True)
    return items
