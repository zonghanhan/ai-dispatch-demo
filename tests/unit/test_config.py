from app.config import Settings


def test_settings_loads_hx_tenant_and_safety_flags(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("DISPATCH_PHASE", "1")
    monkeypatch.setenv("HX_TENANT_ID", "1")
    monkeypatch.setenv("MOCK_MODE", "true")
    s = Settings()
    assert s.dry_run is True
    assert s.dispatch_phase == 1
    assert s.hx_tenant_id == 1
    assert s.mock_mode is True
