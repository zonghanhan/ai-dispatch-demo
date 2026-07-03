import os

import pytest

from app.config import Settings
from app.services.dispatch_service import DispatchService


@pytest.mark.integration
def test_live_dispatch():
    if os.getenv("INTEGRATION") != "1":
        pytest.skip("Set INTEGRATION=1 to run live API/DB/LLM tests")

    settings = Settings()
    if settings.mock_mode:
        pytest.skip("Integration tests require MOCK_MODE=false in .env")

    order_key = settings.test_order_no or settings.test_order_id
    assert order_key, "Set TEST_ORDER_NO or TEST_ORDER_ID in .env"

    service = DispatchService(settings)
    result = service.run(order_key)

    assert result["status"] in ("SUCCESS", "ESCALATED")
    assert any(step["tool"] == "query_order_detail" for step in result["steps"])
