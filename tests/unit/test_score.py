from app.domain.models import MasterCandidate, Order
from app.domain.score import distance_score, rank_masters


def _order(customer_type: str, lat=31.23, lng=121.47):
    return Order(
        order_id="1", biz_type=2, customer_type=customer_type,
        tenant_id=1 if customer_type == "汇信昌" else 2,
        lat=lat, lng=lng, service_type_code="LX002",
    )


def test_non_hxc_8km_distance_score():
    assert distance_score(8.0, "非汇信昌") == 1.25


def test_non_hxc_12km_distance_score():
    assert distance_score(12.0, "非汇信昌") == 0.0


def test_rank_excludes_low_free_ratio():
    order = _order("非汇信昌")
    masters = [
        MasterCandidate(master_id="m1", free_ratio=0.3, lat=31.23, lng=121.47, skill_match=True),
        MasterCandidate(master_id="m2", free_ratio=0.8, lat=31.24, lng=121.48, skill_match=True),
    ]
    ranked = rank_masters(order, masters)
    assert len(ranked) == 1
    assert ranked[0].master_id == "m2"
