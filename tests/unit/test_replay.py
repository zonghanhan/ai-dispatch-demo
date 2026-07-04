from app.domain.models import MasterCandidate, Order
from app.domain.replay import (
    build_candidate_matrix,
    build_conclusion,
    build_replay_steps,
    classify_candidate,
    infer_scenario,
)


def _order(customer_type: str = "非汇信昌", urgent: bool = False):
    return Order(
        order_id="1",
        order_no="ORD-DEMO-S08",
        biz_type=3,
        biz_type_name="单次维修",
        customer_type=customer_type,
        tenant_id=1 if customer_type == "汇信昌" else 2,
        lat=31.23,
        lng=121.47,
        city="杭州",
        urgent=urgent,
    )


def _master(
    master_id: str,
    name: str,
    lat: float,
    lng: float,
    *,
    free_ratio: float = 1.0,
    skill_match: bool = True,
):
    return MasterCandidate(
        master_id=master_id,
        master_name=name,
        nbs_id=f"A{master_id[-3:]}",
        lat=lat,
        lng=lng,
        free_ratio=free_ratio,
        skill_match=skill_match,
    )


def test_classify_exclude_over_10km():
    order = _order("非汇信昌")
    master = _master("m1", "吴师傅", lat=31.33, lng=121.47)
    row = classify_candidate(order, master, top3_ids=[])
    assert row["status"] == "exclude"
    assert row["reason_code"] == "DIST_OVER_10KM"
    assert "10" in row["reason_text"]


def test_classify_skip_5_to_10km():
    order = _order("非汇信昌")
    master = _master("m2", "冯师傅", lat=31.28, lng=121.47)
    row = classify_candidate(order, master, top3_ids=[])
    assert row["status"] == "skip"
    assert row["reason_code"] == "DIST_5_10KM"


def test_classify_selected_top1():
    order = _order("非汇信昌")
    master = _master("m3", "郑师傅", lat=31.24, lng=121.47)
    row = classify_candidate(order, master, top3_ids=["m3", "m4"])
    assert row["status"] == "selected"
    assert row["status_label"] == "选中"


def test_classify_low_free_ratio():
    order = _order("非汇信昌")
    master = _master("m4", "忙师傅", lat=31.24, lng=121.47, free_ratio=0.3)
    row = classify_candidate(order, master, top3_ids=[])
    assert row["status"] == "exclude"
    assert row["reason_code"] == "LOW_FREE_RATIO"


def test_build_candidate_matrix_sorted_by_distance():
    order = _order("非汇信昌")
    masters = [
        _master("far", "吴师傅", lat=31.33, lng=121.47),
        _master("near", "郑师傅", lat=31.24, lng=121.47),
    ]
    matrix = build_candidate_matrix(order, masters, top3_ids=["near"])
    assert matrix[0]["master_id"] == "near"
    assert matrix[0]["status"] == "selected"
    assert matrix[1]["status"] == "exclude"


def test_build_conclusion_distance_exclude():
    order = _order("非汇信昌")
    matrix = [
        {
            "master_name": "吴师傅",
            "distance_label": "11.0 公里",
            "status": "exclude",
            "reason_code": "DIST_OVER_10KM",
            "reason_text": "超过 10 公里硬上限",
        },
        {
            "master_name": "郑师傅",
            "distance_label": "4.5 公里",
            "status": "selected",
        },
    ]
    top3 = [{"master_name": "郑师傅", "rank": 1}]
    conclusion = build_conclusion(order, matrix, top3)
    assert "吴师傅" in conclusion["headline"]
    assert "郑师傅" in conclusion["headline"]
    assert conclusion["tone"] == "warn"


def test_build_replay_steps_has_compare_table_on_step4():
    order = _order("非汇信昌", urgent=True)
    matrix = build_candidate_matrix(
        order,
        [_master("near", "郑师傅", lat=31.24, lng=121.47)],
        top3_ids=["near"],
    )
    steps = build_replay_steps(order, matrix, [{"master_name": "郑师傅"}], 170, dry_run=True)
    assert len(steps) == 5
    step4 = steps[3]
    assert step4["compare_table"]
    assert step4["compare_table"][0]["master_name"] == "郑师傅"


def test_replay_steps_1_to_3_mark_phase1():
    order = _order("非汇信昌")
    steps = build_replay_steps(order, [], [], 100, dry_run=True)
    assert "Phase 1" in (steps[0]["callout"] or {}).get("text", "")
    assert steps[1]["callout"]["type"] == "warn"


def test_infer_scenario_distance_exclude():
    matrix = [{"reason_code": "DIST_OVER_10KM", "status": "exclude"}]
    scenario = infer_scenario(matrix, _order())
    assert scenario["code"] == "distance_exclude"
    assert scenario["badge"] == "warn"
