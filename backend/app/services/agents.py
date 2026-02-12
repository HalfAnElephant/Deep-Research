from __future__ import annotations

import re

from app.models.schemas import Citation, Evidence
from app.services.mcp_executor import MCPExecutor
from app.services.retrieval import RetrievalService
from app.services.writer import ReportBlueprint, WriterService


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

    def __init__(
        self,
        writer_service: WriterService,
        format_agent: "ReportFormatAgent | None" = None,
    ) -> None:
        self.writer_service = writer_service
        self.format_agent = format_agent or ReportFormatAgent()

    def generate_report(
        self,
        *,
        task_id: str,
        task_title: str,
        task_description: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        locked_sections: set[str] | None = None,
    ) -> tuple[str, str, dict[str, Citation]]:
        blueprint = self.format_agent.design_blueprint(
            task_title=task_title,
            task_description=task_description,
        )
        return self.writer_service.write_report(
            task_id=task_id,
            task_title=task_title,
            task_description=task_description,
            sections=sections,
            evidences=evidences,
            locked_sections=locked_sections,
            blueprint=blueprint,
        )


class ReportFormatAgent:
    """Infer requested output format and section blueprint from task text."""

    FORMAT_PATTERN = re.compile(r"(?:格式|体裁|输出形式)\s*[:：]\s*([^\n，。;；]+)")

    def design_blueprint(self, *, task_title: str, task_description: str) -> ReportBlueprint:
        source_text = f"{task_title}\n{task_description}"
        lowered = source_text.lower()
        custom_format = self._extract_custom_format(source_text)

        if self._contains_any(lowered, ["演讲", "演讲稿", "speech", "keynote"]):
            return ReportBlueprint(
                output_format="演讲稿",
                objective="面向听众传达问题背景、关键观点与行动方案",
                tone="清晰有节奏、以结论驱动",
                section_titles=["开场", "背景", "核心观点", "证据支撑", "行动建议", "结语"],
            )
        if self._contains_any(lowered, ["论文", "paper", "academic", "journal", "学术"]):
            return ReportBlueprint(
                output_format="论文",
                objective="形成可复核的研究论证与结构化结论",
                tone="严谨客观、术语准确",
                section_titles=["摘要", "引言", "相关工作", "方法", "结果与讨论", "结论"],
            )
        if self._contains_any(lowered, ["报告", "report", "调研"]):
            return ReportBlueprint(
                output_format="研究报告",
                objective="给出可执行的分析结论与决策建议",
                tone="客观中立、结论先行",
                section_titles=["摘要", "背景", "关键发现", "分析", "风险与局限", "结论与建议"],
            )
        if custom_format:
            return ReportBlueprint(
                output_format=custom_format,
                objective=f"按“{custom_format}”体裁交付内容，并保持结构化表达",
                tone="清晰、克制、信息密集",
                section_titles=["开篇", "主体", "结论"],
            )
        return ReportBlueprint(
            output_format="通用文章",
            objective="在保持可读性的前提下，完整回答用户研究需求",
            tone="客观清晰",
            section_titles=["摘要", "主体分析", "结论"],
        )

    @classmethod
    def _extract_custom_format(cls, source_text: str) -> str:
        match = cls.FORMAT_PATTERN.search(source_text)
        if not match:
            return ""
        return match.group(1).strip()

    @staticmethod
    def _contains_any(text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)
