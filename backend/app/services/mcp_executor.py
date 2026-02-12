from __future__ import annotations

import asyncio
from typing import Any


class MCPExecutor:
    async def execute(self, *, tool_name: str, method: str, params: dict[str, Any], mode: str) -> dict[str, Any]:
        if mode in {"write", "execute"}:
            return {
                "status": "USER_CONFIRMATION_REQUIRED",
                "toolName": tool_name,
                "method": method,
                "params": params,
            }

        # Minimal JSON-RPC compatible read-only execution simulation.
        await asyncio.sleep(0.05)
        return {
            "status": "SUCCESS",
            "result": {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "tool": tool_name,
            },
        }
