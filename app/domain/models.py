from pydantic import BaseModel, Field


class Order(BaseModel):
    order_id: str
    order_no: str = ""
    biz_type: int
    biz_type_name: str = ""
    customer_type: str
    tenant_id: int
    category: str = ""
    lat: float | None = None
    lng: float | None = None
    city: str = ""
    address_masked: str = ""
    urgent: bool = False
    status: int = 0
    erp_codes: list[str] = Field(default_factory=list)
    service_type_code: str = ""


class MasterCandidate(BaseModel):
    master_id: str
    master_name: str = ""
    nbs_id: str = ""
    profession_type: str = ""
    skill_match: bool = True
    skill_codes: str = ""
    free_ratio: float = 1.0
    lat: float | None = None
    lng: float | None = None
    company: int | None = None
    service_city: str = ""
    active_orders: int = 0


class RankingItem(BaseModel):
    master_id: str
    score: float
    breakdown: dict
    reason: str = ""
