import pytest

from app.domain.order_resolver import (
    is_order_no,
    parse_order_key,
    resolve_order_key,
    resolve_order_no,
)


def test_resolve_numeric_id_passthrough():
    assert resolve_order_key("11409") == (11409, None)


def test_parse_numeric_key():
    assert parse_order_key("11409") == ("numeric", 11409)


def test_resolve_order_no_prefix():
    assert is_order_no("DD20260702000005") is True


def test_parse_order_no_key():
    assert parse_order_key("DD20260702000005") == ("order_no", None)


def test_resolve_order_key_rejects_order_no_without_db():
    with pytest.raises(ValueError, match="database lookup"):
        resolve_order_key("DD20260702000005")


def test_resolve_order_no_from_db():
    class FakeDb:
        def lookup_order_by_no(self, order_no: str) -> tuple[int, int]:
            assert order_no == "DD20260702000005"
            return (11409, 1)

    assert resolve_order_no(FakeDb(), "DD20260702000005") == (11409, 1)
