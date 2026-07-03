WHITELIST = frozenset({
    "query_order_detail",
    "query_candidate_masters",
    "score_master_by_rule",
    "log_decision",
})


def reject_assign_in_phase1(tool_name: str, phase: int):
    if phase == 1 and tool_name in {"assign_order", "reassign_order"}:
        return False, ["R-PHASE-01"]
    return True, []


def assert_tool_allowed(tool_name: str, phase: int):
    if tool_name not in WHITELIST:
        return False, ["INVALID_TOOL"]
    return reject_assign_in_phase1(tool_name, phase)
