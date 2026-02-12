from __future__ import annotations

from fastapi import APIRouter

from app.deps import mcp_executor
from app.models.schemas import MCPExecutionRequest, MCPExecutionResult

router = APIRouter(prefix="/api/v1")


@router.post("/mcp/execute", response_model=MCPExecutionResult)
async def execute_mcp(payload: MCPExecutionRequest) -> MCPExecutionResult:
    result = await mcp_executor.execute(
        tool_name=payload.toolName,
        method=payload.method,
        params=payload.params,
        mode=payload.mode,
    )
    return MCPExecutionResult(**result)
