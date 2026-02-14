from __future__ import annotations

from dataclasses import dataclass
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
        review_agent: "ReportReviewAgent | None" = None,
        revision_agent: "ReportRevisionAgent | None" = None,
        max_review_rounds: int = 3,
    ) -> None:
        self.writer_service = writer_service
        self.format_agent = format_agent or ReportFormatAgent()
        self.review_agent = review_agent or ReportReviewAgent()
        self.revision_agent = revision_agent or ReportRevisionAgent(writer_service=writer_service)
        self.max_review_rounds = max(1, max_review_rounds)

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
        draft_body = self.writer_service.generate_body(
            task_title=task_title,
            task_description=task_description,
            sections=sections,
            evidences=evidences,
            blueprint=blueprint,
        )
        review_result = self.review_agent.review(body=draft_body, blueprint=blueprint, evidences=evidences)
        for _ in range(self.max_review_rounds):
            if review_result.approved:
                break
            draft_body = self.revision_agent.revise(
                draft_body=draft_body,
                feedback=review_result,
                task_title=task_title,
                task_description=task_description,
                sections=sections,
                evidences=evidences,
                blueprint=blueprint,
            )
            review_result = self.review_agent.review(body=draft_body, blueprint=blueprint, evidences=evidences)
        if not review_result.approved:
            draft_body = self.revision_agent.rewrite_with_template(
                task_title=task_title,
                task_description=task_description,
                sections=sections,
                evidences=evidences,
                blueprint=blueprint,
            )
        return self.writer_service.write_report(
            task_id=task_id,
            task_title=task_title,
            task_description=task_description,
            sections=sections,
            evidences=evidences,
            locked_sections=locked_sections,
            blueprint=blueprint,
            report_body=draft_body,
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
                objective="给出跨维度、可追溯且可执行的分析结论与决策建议",
                tone="客观中立、论证充分、结论先行",
                section_titles=["摘要", "研究范围与方法", "背景", "关键发现", "分析", "风险与局限", "结论与建议"],
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
            objective="在保持可读性的前提下，深度回答用户研究需求",
            tone="客观清晰、信息密集",
            section_titles=["摘要", "研究背景", "主体分析", "结论与下一步"],
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


@dataclass(frozen=True)
class ReportReviewResult:
    approved: bool
    issues: list[str]


class ReportReviewAgent:
    """Review report quality and block intermediate traces from leaking to users."""

    TRACE_PATTERNS = (
        re.compile(r"(?im)^\s*##\s*trace section\b"),
        re.compile(r"(?im)^\s*\[locked\]"),
        re.compile(r"(?im)^\s*挑战识别\s*:"),
    )
    PLACEHOLDER_PATTERNS = (
        re.compile(r"(?i)\[mock\]"),
        re.compile(r"(?i)\b(?:arxiv|semantic scholar|semanticscholar|tavily|web)\s+result\s+for\b"),
        re.compile(r"(?i)synthetic evidence"),
    )
    EVIDENCE_REF_PATTERN = re.compile(r"\[evidence:([^\]]+)\]")
    MIN_BODY_BASE_CHARS = 780
    MIN_BODY_PER_SECTION_CHARS = 170
    MIN_SECTION_CHARS = 180
    MIN_SUMMARY_SECTION_CHARS = 110
    MIN_PARAGRAPHS_PER_SECTION = 2
    MIN_PARAGRAPHS_FOR_SHORT_SECTION = 1
    SHORT_SECTION_KEYWORDS = ("摘要", "结论", "结语", "开场")

    def review(self, *, body: str, blueprint: ReportBlueprint, evidences: list[Evidence]) -> ReportReviewResult:
        issues: list[str] = []
        stripped = body.strip()
        if not stripped:
            return ReportReviewResult(approved=False, issues=["正文为空。"])

        if any(pattern.search(body) for pattern in self.TRACE_PATTERNS):
            issues.append("包含中间过程痕迹（如 Trace Section 或过程标签）。")
        if any(pattern.search(body) for pattern in self.PLACEHOLDER_PATTERNS):
            issues.append("包含占位检索文本，降低内容可信度。")

        missing_sections = [title for title in blueprint.section_titles if f"## {title}" not in body]
        if missing_sections:
            issues.append(f"章节不完整，缺少：{', '.join(missing_sections[:4])}。")
        section_contents = self._section_contents(body)
        shallow_sections: list[str] = []
        sparse_sections: list[str] = []
        for title in blueprint.section_titles:
            content = section_contents.get(title, "").strip()
            if not content:
                continue
            min_chars = self._section_min_chars(title)
            if len(content) < min_chars:
                shallow_sections.append(title)
            min_paragraphs = self._section_min_paragraphs(title)
            if self._paragraph_count(content) < min_paragraphs:
                sparse_sections.append(title)
        if shallow_sections:
            issues.append(f"章节深度不足，内容偏短：{', '.join(shallow_sections[:4])}。")
        if sparse_sections:
            issues.append(f"章节展开不足，段落层次不够：{', '.join(sparse_sections[:4])}。")

        evidence_ids = {ev.id for ev in evidences}
        cited_ids = set(self.EVIDENCE_REF_PATTERN.findall(body))
        cited_known = cited_ids.intersection(evidence_ids)
        if evidence_ids and not cited_known:
            issues.append("关键结论缺少有效证据ID引用。")
        if evidence_ids and len(cited_known) < min(2, len(evidence_ids)):
            issues.append("证据覆盖不足，至少应引用两个不同证据。")

        required_chars = self._minimum_body_chars(blueprint)
        if len(stripped) < required_chars:
            issues.append(f"正文过短，信息密度不足（当前 {len(stripped)}，要求至少 {required_chars}）。")
        return ReportReviewResult(approved=not issues, issues=issues)

    @classmethod
    def _section_contents(cls, body: str) -> dict[str, str]:
        section_map: dict[str, list[str]] = {}
        current_heading = ""
        for line in body.splitlines():
            heading_match = re.match(r"^\s*##\s+(.+?)\s*$", line)
            if heading_match:
                current_heading = heading_match.group(1).strip()
                section_map.setdefault(current_heading, [])
                continue
            if not current_heading:
                continue
            section_map[current_heading].append(line)
        return {heading: "\n".join(lines).strip() for heading, lines in section_map.items()}

    @classmethod
    def _minimum_body_chars(cls, blueprint: ReportBlueprint) -> int:
        return cls.MIN_BODY_BASE_CHARS + len(blueprint.section_titles) * cls.MIN_BODY_PER_SECTION_CHARS

    @classmethod
    def _section_min_chars(cls, title: str) -> int:
        return cls.MIN_SUMMARY_SECTION_CHARS if cls._is_short_section(title) else cls.MIN_SECTION_CHARS

    @classmethod
    def _section_min_paragraphs(cls, title: str) -> int:
        if cls._is_short_section(title):
            return cls.MIN_PARAGRAPHS_FOR_SHORT_SECTION
        return cls.MIN_PARAGRAPHS_PER_SECTION

    @classmethod
    def _is_short_section(cls, title: str) -> bool:
        return any(keyword in title for keyword in cls.SHORT_SECTION_KEYWORDS)

    @staticmethod
    def _paragraph_count(text: str) -> int:
        text = text.strip()
        if not text:
            return 0
        by_blank = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        if len(by_blank) > 1:
            return len(by_blank)
        by_lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(by_lines) > 1:
            return len(by_lines)
        return 1


class ReportRevisionAgent:
    """Revise report body according to reviewer feedback."""

    TRACE_LINE_PATTERNS = (
        re.compile(r"(?i)^\s*##\s*trace section\b"),
        re.compile(r"(?i)^\s*\[locked\]"),
        re.compile(r"^\s*挑战识别\s*:"),
    )
    PLACEHOLDER_LINE_PATTERNS = (
        re.compile(r"(?i)\[mock\]"),
        re.compile(r"(?i)\b(?:arxiv|semantic scholar|semanticscholar|tavily|web)\s+result\s+for\b"),
        re.compile(r"(?i)synthetic evidence"),
    )

    def __init__(self, writer_service: WriterService) -> None:
        self.writer_service = writer_service

    def revise(
        self,
        *,
        draft_body: str,
        feedback: ReportReviewResult,
        task_title: str,
        task_description: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint,
    ) -> str:
        cleaned = self._strip_noisy_lines(draft_body)
        if self._requires_template_rewrite(cleaned, feedback):
            return self.rewrite_with_template(
                task_title=task_title,
                task_description=task_description,
                sections=sections,
                evidences=evidences,
                blueprint=blueprint,
            )
        return cleaned

    def rewrite_with_template(
        self,
        *,
        task_title: str,
        task_description: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint,
    ) -> str:
        _ = task_description
        return self.writer_service.generate_template_body(
            task_title=task_title,
            sections=sections,
            evidences=evidences,
            blueprint=blueprint,
        )

    def _strip_noisy_lines(self, text: str) -> str:
        kept: list[str] = []
        for line in text.splitlines():
            if any(pattern.search(line) for pattern in self.TRACE_LINE_PATTERNS):
                continue
            if any(pattern.search(line) for pattern in self.PLACEHOLDER_LINE_PATTERNS):
                continue
            kept.append(line.rstrip())

        compacted: list[str] = []
        blank_run = 0
        for line in kept:
            if line.strip():
                blank_run = 0
                compacted.append(line)
                continue
            blank_run += 1
            if blank_run <= 1:
                compacted.append("")
        return "\n".join(compacted).strip()

    @staticmethod
    def _requires_template_rewrite(cleaned_body: str, feedback: ReportReviewResult) -> bool:
        minimum_chars = ReportReviewAgent.MIN_BODY_BASE_CHARS + ReportReviewAgent.MIN_BODY_PER_SECTION_CHARS
        if len(cleaned_body.strip()) < minimum_chars:
            return True
        blocking_keywords = (
            "章节不完整",
            "章节深度不足",
            "章节展开不足",
            "证据覆盖不足",
            "缺少有效证据ID引用",
            "正文过短",
        )
        return any(any(keyword in issue for keyword in blocking_keywords) for issue in feedback.issues)
