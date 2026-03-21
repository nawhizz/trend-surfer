from fastapi import APIRouter
from app.api.v1.endpoints import collector, signals

api_router = APIRouter()
api_router.include_router(collector.router, prefix="/collect", tags=["collector"])
api_router.include_router(signals.router, prefix="/signals", tags=["signals"])
