from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.routes.dispatch import get_settings, router as dispatch_router

_STATIC_DIR = Path(__file__).resolve().parents[1] / "web" / "static"

app = FastAPI(title="AI Dispatch Demo")

app.include_router(dispatch_router)


@app.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"ok": True}


if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
