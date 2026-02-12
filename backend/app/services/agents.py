from __future__ import annotations

from app.models.schemas import Citation, Evidence
from app.services.mcp_executor import MCPExecutor
from app.services.retrieval import RetrievalService
from app.services.writer import WriterService


class ResearchAgent:
    """Collect evidence from configured providers and optional MCP read tools."""

    def __init__(self, retrieval_service: RetrievalService, mcp_executor: MCPExecutor | None = None) -> None:
        self.retrieval_service = retrieval_service
        self.mcp_executor = mcp_executor

    async def collect_evidence(
        self,
        *,
        task_id: str,
        node_id: str,
        query: str,
        sources: list[str],
        mcp_read_tools: list[str] | None = None,
    ) -> list[Evidence]:
        evidences = await self.retrieval_service.retrieve(
            task_id=task_id,
            node_id=node_id,
            query=query,
            sources=sources,
        )
        if not self.mcp_executor or not mcp_read_tools:
            return evidences

        # Placeholder MCP hook for future expansion.
        for tool_name in mcp_read_tools:
            await self.mcp_executor.execute(
                tool_name=tool_name,
                method="tools/call",
                params={"query": query, "taskId": task_id, "nodeId": node_id},
                mode="read",
            )
        return evidences


class ReportAgent:
    """Generate report artifacts from structured sections and evidence."""

    def __init__(self, writer_service: WriterService) -> None:
        self.writer_service = writer_service

    def generate_report(
        self,
        *,
        task_id: str,
        task_title: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        locked_sections: set[str] | None = None,
    ) -> tuple[str, str, dict[str, Citation]]:
        return self.writer_service.write_report(
            task_id=task_id,
            task_title=task_title,
            sections=sections,
            evidences=evidences,
            locked_sections=locked_sections,
        )
