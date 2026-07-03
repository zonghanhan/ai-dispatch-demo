from app.domain.guard import assert_tool_allowed, reject_assign_in_phase1


def test_reject_assign_in_phase1():
    ok, codes = reject_assign_in_phase1("assign_order", phase=1)
    assert ok is False
    assert "R-PHASE-01" in codes


def test_whitelist_tool_ok():
    ok, codes = assert_tool_allowed("query_order_detail", phase=1)
    assert ok is True
    assert codes == []


def test_unknown_tool_rejected():
    ok, codes = assert_tool_allowed("relax_rule", phase=1)
    assert ok is False
    assert "INVALID_TOOL" in codes
