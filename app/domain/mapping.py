BIZ_TYPE_SERVICE = {1: "LX001", 2: "LX002", 3: "LX003", 4: "LX003"}
BIZ_TYPE_NAME = {1: "测量", 2: "安装", 3: "单次维修", 4: "质保维修"}


def biz_type_to_service_code(biz_type: int) -> str:
    return BIZ_TYPE_SERVICE.get(biz_type, "LX003")


def resolve_customer_type(tenant_id: int, settings) -> str:
    return "汇信昌" if tenant_id == settings.hx_tenant_id else "非汇信昌"


def mask_address(province: str, area: str, address: str) -> str:
    region = f"{province or ''}{area or ''}".strip()
    return f"{region}***" if region else "***"


def _urgent_from_data(data: dict) -> bool:
    if data.get("emergencyFlag", 0) not in (0, None):
        return True
    if data.get("isNightEmergency") is True:
        return True
    for g in data.get("goodsSaveReqVOList") or []:
        if g.get("isNightEmergency") in (1, 2):
            return True
    return False


def map_api_order(data: dict, settings) -> "Order":
    from app.domain.models import Order

    tenant_id = int(data.get("tenantId") or 0)
    biz_type = int(data.get("bizType") or 0)
    erp_codes = [
        g.get("erpCode")
        for g in (data.get("goodsSaveReqVOList") or [])
        if g.get("erpCode")
    ]
    return Order(
        order_id=str(data["id"]),
        order_no=data.get("orderNo") or "",
        biz_type=biz_type,
        biz_type_name=data.get("spuTypeName") or BIZ_TYPE_NAME.get(biz_type, ""),
        customer_type=resolve_customer_type(tenant_id, settings),
        tenant_id=tenant_id,
        category=data.get("spuCategoryName") or (data.get("spuPath") or "").split(">")[-1],
        lat=data.get("lat"),
        lng=data.get("lon"),
        city=data.get("city") or "",
        address_masked=mask_address(
            data.get("province", ""), data.get("area", ""), data.get("address", "")
        ),
        urgent=_urgent_from_data(data),
        status=int(data.get("status") or 0),
        erp_codes=list(dict.fromkeys(erp_codes)),
        service_type_code=biz_type_to_service_code(biz_type),
    )
