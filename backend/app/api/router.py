from fastapi import APIRouter

from app.api.routes.evidence import router as evidence_router
from app.api.routes.mcp import router as mcp_router
from app.api.routes.tasks import router as tasks_router

api_router = APIRouter()
api_router.include_router(tasks_router)
api_router.include_router(evidence_router)
api_router.include_router(mcp_router)
