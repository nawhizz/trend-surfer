from fastapi import APIRouter
from app.api.v1.endpoints import collector

api_router = APIRouter()
api_router.include_router(collector.router, prefix="/collect", tags=["collector"])
