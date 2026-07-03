from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    dry_run: bool = True
    dispatch_phase: int = 1
    mock_mode: bool = True

    api_base_url: str = "http://127.0.0.1:8000"
    api_token: str = ""
    api_order_path: str = "/app-api/order/publish-order/get"
    api_tenant_header: str = "tenant-id"
    api_timeout_sec: int = 10
    hx_tenant_id: int = 1

    db_host: str = ""
    db_port: int = 3306
    db_name: str = "hxc_cloud"
    db_user: str = ""
    db_password: str = ""

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    llm_timeout_sec: int = 30
    llm_fallback: bool = True

    test_order_no: str = "DD20260702000005"
    test_order_id: str = ""
    max_steps: int = 8
    t_session_sec: int = 30
    sqlite_path: str = "./data/demo.db"
