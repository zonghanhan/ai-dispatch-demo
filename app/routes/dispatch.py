from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import Settings
from app.services.dispatch_service import DispatchService

router = APIRouter(prefix="/demo", tags=["demo"])


class DispatchRequest(BaseModel):
    order_id: str


def get_settings() -> Settings:
    return Settings()


def get_dispatch_service(
    settings: Settings = Depends(get_settings),
) -> DispatchService:
    return DispatchService(settings)


@router.post("/dispatch")
def dispatch_order(
    body: DispatchRequest,
    service: DispatchService = Depends(get_dispatch_service),
) -> dict:
    return service.run(body.order_id)


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    service: DispatchService = Depends(get_dispatch_service),
) -> dict:
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
