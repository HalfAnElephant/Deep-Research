from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import re

import httpx

from app.core.config import settings
from app.models.schemas import Citation, Evidence


@dataclass(frozen=True)
class ReportBlueprint:
    output_format: str
    objective: str
    tone: str
    section_titles: list[str]


class WriterService:
    """研究文章写作服务，支持分离导出文章和引用列表。"""

    URL_PATTERN = re.compile(r"https?://\S+")
    PLACEHOLDER_TITLE_PATTERN = re.compile(
        r"(?i)(^\[mock\]|result\s+for|synthetic evidence|semantic scholar result|arxiv result|web result)"
    )
    # 需要过滤的内部标记模式
    INTERNAL_MARKERS_PATTERN = re.compile(
        r"(_taskId:\s*\S+_)"
        r"|(\#\#\s*AI\s*综合解读)"
        r"|(\#\#\s*输出格式)"
        r"|(\#\#\s*Trace\s*Section)"
        r"|(\[locked\])"
    )

    def __init__(self, output_dir: str = "backend/.data/reports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_report(
        self,
        *,
        task_id: str,
        task_title: str,
        task_description: str = "",
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        locked_sections: set[str] | None = None,
        blueprint: ReportBlueprint | None = None,
        report_body: str | None = None,
    ) -> tuple[str, str, dict[str, Citation]]:
        """生成研究文章和引用列表两个独立的文件。

        Returns:
            tuple[str, str, dict]: (文章路径, 引用列表路径, 引用映射)
        """
        _ = locked_sections
        blueprint = blueprint or self._default_blueprint()
        citation_map = self._build_citations(evidences)

        if report_body is None:
            generated_body = self.generate_body(
                task_title=task_title,
                task_description=task_description,
                sections=sections,
                evidences=evidences,
                blueprint=blueprint,
            )
        else:
            generated_body = report_body

        # 过滤内部标记，确保输出干净
        clean_body = self._strip_internal_markers(generated_body)

        # 生成文章文件（纯内容，引用在文末）
        article_lines = [f"# {task_title}", ""]
        article_lines.extend(clean_body.splitlines())
        article_lines.append("")
        article_lines.append("## 参考文献")
        for i, cid in enumerate(citation_map, start=1):
            c = citation_map[cid]
            article_lines.append(f"[{i}] {', '.join(c.authors)} ({c.year}). {c.title}. {c.url}")

        article_path = self.output_dir / f"{task_id}_article.md"
        article_path.write_text("\n".join(article_lines), encoding="utf-8")

        # 生成引用列表文件（包含评分和说明）
        references_content = self._build_references_list(evidences, citation_map)
        references_path = self.output_dir / f"{task_id}_references.md"
        references_path.write_text(references_content, encoding="utf-8")

        # 保留旧的 .md 和 .bib 文件以保持兼容
        legacy_md_path = self.output_dir / f"{task_id}.md"
        legacy_md_path.write_text("\n".join(article_lines), encoding="utf-8")

        bib_lines: list[str] = []
        for c in citation_map.values():
            key = c.id.replace("-", "")[:8]
            bib_lines.extend(
                [
                    f"@article{{{key},",
                    f"  title = {{{c.title}}},",
                    f"  author = {{{' and '.join(c.authors) or 'Unknown'}}},",
                    f"  year = {{{c.year}}},",
                    f"  url = {{{c.url}}}",
                    "}",
                    "",
                ]
            )
        bib_path = self.output_dir / f"{task_id}.bib"
        bib_path.write_text("\n".join(bib_lines), encoding="utf-8")

        return str(article_path), str(references_path), citation_map

    def generate_body(
        self,
        *,
        task_title: str,
        task_description: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint | None = None,
    ) -> str:
        selected_blueprint = blueprint or self._default_blueprint()
        return self._generate_body(
            task_title=task_title,
            task_description=task_description,
            sections=sections,
            evidences=evidences,
            blueprint=selected_blueprint,
        )

    def generate_template_body(
        self,
        *,
        task_title: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint | None = None,
    ) -> str:
        selected_blueprint = blueprint or self._default_blueprint()
        return self._generate_template(
            task_title=task_title,
            sections=sections,
            evidences=evidences,
            blueprint=selected_blueprint,
        )

    def _generate_body(
        self,
        *,
        task_title: str,
        task_description: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint,
    ) -> str:
        """生成文章正文内容，不含内部标记。"""
        evidence_rich_template = self._generate_template(
            task_title=task_title,
            sections=sections,
            evidences=evidences,
            blueprint=blueprint,
        )
        if settings.use_mock_sources:
            return evidence_rich_template

        llm_text = self._generate_with_llm(
            task_title=task_title,
            task_description=task_description,
            sections=sections,
            evidences=evidences,
            blueprint=blueprint,
        )
        if not llm_text:
            return evidence_rich_template
        sanitized = self._strip_inline_urls(llm_text.strip())
        # 不再添加 "## AI 综合解读" 标记，直接返回 LLM 生成的内容
        # 如果 LLM 内容较短，补充模板内容
        if len(sanitized) < 500:
            return evidence_rich_template
        return sanitized

    def _generate_with_llm(
        self,
        *,
        task_title: str,
        task_description: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint,
    ) -> str:
        base_url, api_key, model = self._resolve_provider()
        if not base_url or not api_key:
            return ""

        evidence_snippets = "\n".join(
            (
                f"- [{ev.id}] {self._display_title(ev)} | 类型：{ev.sourceType.value} | "
                f"时间：{ev.metadata.publishDate or '未知'}\n"
                f"  摘要：{self._compact_text(ev.content, 320)}"
            )
            for ev in evidences[:18]
        )
        section_snippets = "\n".join(
            f"- {self._compact_text(content, 260)}" for _, content in sections[:12]
        )
        blueprint_snippets = "\n".join(f"- {title}" for title in blueprint.section_titles)
        prompt = (
            f"研究题目：{task_title}\n"
            f"任务背景与用户要求：{task_description[:1200]}\n"
            f"输出体裁：{blueprint.output_format}\n"
            f"写作目标：{blueprint.objective}\n"
            f"风格要求：{blueprint.tone}\n"
            "请按如下章节生成正文：\n"
            f"{blueprint_snippets}\n"
            "保持结构化、客观、可读性强。禁止编造不存在的数据、论文、链接。\n"
            "深度与广度要求：\n"
            "1) 正文总字数不少于 2200 字。\n"
            "2) 除摘要/结论章节外，每个章节至少 2 段，每段不少于 120 字。\n"
            "3) 每个章节至少覆盖 3 个维度：现状、驱动机制、影响评估、风险边界、落地策略。\n"
            "4) 每个章节至少引用 2 个不同证据 ID；证据不足时须明确写出缺口与补充方向。\n"
            "5) 结论必须给出可执行动作、优先级与前置条件。\n"
            "每个关键结论必须引用至少一个证据ID（例如 [evidence:xxxx]）。\n"
            "正文中不要放证据网址，不要输出参考文献与证据附录，网址统一在文末追加。\n\n"
            f"任务分段信息：\n{section_snippets}\n\n"
            f"证据片段：\n{evidence_snippets}\n"
        )
        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "temperature": 0.2,
                        "messages": [
                            {"role": "system", "content": "你是严谨的研究写作助手。"},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                response.raise_for_status()
                payload = response.json()
            return (
                payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
        except Exception:
            return ""

    def _resolve_provider(self) -> tuple[str, str, str]:
        provider = settings.default_llm_provider.lower().strip()
        if provider == "openrouter":
            return settings.openrouter_base_url, settings.openrouter_api_key, settings.openrouter_model
        if provider == "deepseek":
            return settings.deepseek_base_url, settings.deepseek_api_key, settings.deepseek_model
        if provider == "openai":
            return settings.openai_base_url, settings.openai_api_key, settings.openai_model
        return "", "", ""

    def _generate_template(
        self,
        *,
        task_title: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint,
    ) -> str:
        ranked = sorted(evidences, key=lambda item: item.score, reverse=True)
        top = ranked[:8]
        source_types = sorted({ev.sourceType.value for ev in ranked})
        lines = [
            "## 输出格式",
            f"体裁：{blueprint.output_format}",
            f"目标：{blueprint.objective}",
            f"风格：{blueprint.tone}",
            "",
        ]
        section_to_evidence: dict[str, list[Evidence]] = defaultdict(list)
        for ev in ranked:
            section_to_evidence[ev.nodeId].append(ev)

        used_ids: set[str] = set()
        for idx, heading in enumerate(blueprint.section_titles):
            lines.append(f"## {heading}")
            if idx == 0:
                ref_summary = "、".join(f"[evidence:{ev.id}]" for ev in top[:4]) if top else "无"
                lines.append(
                    f"围绕“{task_title}”共纳入 {len(ranked)} 条证据，来源类型："
                    f"{', '.join(source_types) or '无'}。"
                )
                lines.append(
                    "本报告从问题背景、机制解释、影响评估、风险边界与行动路径五个层面展开，"
                    "优先基于可追溯证据构建结论链条，避免仅停留在概念罗列。"
                )
                if top:
                    lines.append(f"高优先证据线索：{ref_summary}")
                else:
                    lines.append("当前没有检索到可用证据，请检查数据源配置与网络连通性后重试。")
                lines.append("")
                continue

            if not sections:
                lines.append(
                    "暂无可用任务分段，当前仅能给出高层研判。建议先补充分解：问题定义、"
                    "关键变量、评估指标、对照样本，再回填到本章节。"
                )
                lines.append(
                    "在缺少结构化分段时，本节仍应覆盖成因解释、影响范围和可执行动作，"
                    "并明确当前结论的可信度边界。"
                )
                lines.append("")
                continue

            section_idx = min(idx - 1, len(sections) - 1)
            section_id, section_content = sections[section_idx]
            section_lines = [line.strip() for line in section_content.splitlines() if line.strip()]
            section_title = section_lines[0] if section_lines else section_id
            section_desc = section_lines[1] if len(section_lines) > 1 else section_content.strip()
            matched = section_to_evidence.get(section_id, [])[:3]
            if not matched:
                matched = [ev for ev in ranked if ev.id not in used_ids][:3]
            if matched:
                evidence_details: list[str] = []
                for ev in matched:
                    used_ids.add(ev.id)
                    evidence_details.append(
                        f"{self._display_title(ev)} 指出“{self._compact_text(ev.content, 95)}”"
                        f" [evidence:{ev.id}]"
                    )
                lines.append(
                    f"研究问题：{section_title}。本节围绕“{self._compact_text(section_desc, 260)}”展开，"
                    "重点刻画问题定义、驱动因素、关键影响与可行约束。"
                )
                lines.append(
                    f"证据解读：{'；'.join(evidence_details)}。以上证据共同支持本节判断，"
                    "同时提示结论需结合场景差异进行校准。"
                )
            else:
                lines.append(
                    f"研究问题：{section_title}。当前尚未命中该分段的直接证据，"
                    "建议扩展检索词并增加跨来源验证，以避免单一视角偏差。"
                )
            lines.append(self._section_focus_hint(heading))
            lines.append("")

        leftovers = [ev for ev in ranked if ev.id not in used_ids][:4]
        if leftovers:
            lines.append("## 补充线索")
            for ev in leftovers:
                lines.append(
                    f"- {self._display_title(ev)}：{self._compact_text(ev.content, 120)} "
                    f"[evidence:{ev.id}]"
                )
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _section_focus_hint(heading: str) -> str:
        if "方法" in heading or "范围" in heading:
            return (
                "方法与范围：明确样本覆盖、数据时效与对照口径，补充可复现实验步骤，"
                "避免仅用定性描述替代可验证过程。"
            )
        if "背景" in heading:
            return (
                "背景延展：说明该问题在产业、技术与政策层面的演化脉络，"
                "并区分长期趋势与短期波动，减少时点偏差。"
            )
        if "发现" in heading:
            return (
                "关键发现：将共识点与争议点并列呈现，分别标注证据强度，"
                "并解释不同来源出现结论分歧的潜在原因。"
            )
        if "风险" in heading or "局限" in heading:
            return (
                "风险与局限：识别证据覆盖盲区、外部变量干扰与实施前提缺失，"
                "同时给出最可能导致结论失效的边界条件。"
            )
        if "结论" in heading or "建议" in heading:
            return (
                "行动建议：按短期（1-3个月）、中期（3-12个月）拆分任务优先级，"
                "给出落地前置条件、负责人角色与效果评估指标。"
            )
        return (
            "综合分析：从机制解释、影响传播与实施可行性三个层面推进论证，"
            "并对关键假设进行显式标注，便于后续复核。"
        )

    @staticmethod
    def _compact_text(text: str, limit: int) -> str:
        compacted = " ".join(text.split()).strip()
        if not compacted:
            return "暂无内容。"
        return compacted[:limit]

    def _build_evidence_appendix(self, evidences: list[Evidence]) -> str:
        ranked = sorted(evidences, key=lambda item: item.score, reverse=True)
        lines = ["## 证据说明与来源链接"]
        if not ranked:
            lines.append("暂无可用证据。")
            return "\n".join(lines)

        for idx, ev in enumerate(ranked, start=1):
            snippet = " ".join(ev.content.split())
            lines.append(f"{idx}. [{ev.id}] {self._display_title(ev)}")
            lines.append(f"说明：{snippet[:220] or '该来源未返回可展示摘要。'}")
            lines.append(
                f"来源：{ev.sourceType.value} | 发表时间：{ev.metadata.publishDate or '未知'} | 评分：{ev.score:.2f}"
            )
            lines.append(f"网址：{ev.url}")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def _strip_inline_urls(cls, text: str) -> str:
        return cls.URL_PATTERN.sub("[链接见文末证据附录]", text)

    @staticmethod
    def _default_blueprint() -> ReportBlueprint:
        return ReportBlueprint(
            output_format="研究报告",
            objective="给出跨维度、可复核且可执行的研究结论",
            tone="客观中立、论证充分、信息密集",
            section_titles=["摘要", "研究范围与方法", "背景", "关键发现", "分析", "结论与建议"],
        )

    def _build_citations(self, evidences: list[Evidence]) -> dict[str, Citation]:
        citations: dict[str, Citation] = {}
        for ev in evidences:
            year = 2026
            if ev.metadata.publishDate[:4].isdigit():
                year = int(ev.metadata.publishDate[:4])
            citations[ev.id] = Citation(
                id=ev.id,
                authors=ev.metadata.authors or ["Unknown"],
                title=self._display_title(ev),
                year=year,
                source=ev.sourceType.value,
                url=ev.url,
            )
        return citations

    @classmethod
    def _display_title(cls, evidence: Evidence) -> str:
        raw_title = " ".join(evidence.metadata.title.split()).strip()
        if raw_title and not cls._looks_placeholder_title(raw_title):
            return raw_title
        fallback = " ".join(evidence.content.split()).strip()
        if fallback:
            return fallback[:120]
        return "未命名证据"

    @classmethod
    def _looks_placeholder_title(cls, title: str) -> bool:
        return bool(cls.PLACEHOLDER_TITLE_PATTERN.search(title.strip()))

    @classmethod
    def _strip_internal_markers(cls, text: str) -> str:
        """移除内部标记，确保输出干净。

        过滤的内容包括：
        - _taskId: xxx_ 内部任务标记
        - ## AI 综合解读 AI 提示词泄露
        - ## 输出格式 输出格式信息泄露
        - ## Trace Section 调试信息
        - [locked] 锁定标记
        """
        # 移除匹配的行
        lines = text.splitlines()
        filtered_lines = []
        skip_next_empty = False

        for line in lines:
            # 检查是否是需要移除的行
            if cls.INTERNAL_MARKERS_PATTERN.search(line):
                skip_next_empty = True
                continue
            # 跳过标记后的空行
            if skip_next_empty and line.strip() == "":
                skip_next_empty = False
                continue
            filtered_lines.append(line)

        return "\n".join(filtered_lines)

    def _build_references_list(
        self,
        evidences: list[Evidence],
        citation_map: dict[str, Citation]
    ) -> str:
        """生成引用列表文件，包含评分和说明。

        Args:
            evidences: 证据列表
            citation_map: 引用映射

        Returns:
            格式化的引用列表内容
        """
        ranked = sorted(evidences, key=lambda item: item.score, reverse=True)

        lines = ["# 引用列表", ""]
        lines.append("本文档包含研究中引用的所有文献，包括评分、来源和相关说明。")
        lines.append("")

        if not ranked:
            lines.append("暂无引用文献。")
            return "\n".join(lines)

        lines.append(f"共 {len(ranked)} 条引用文献，按相关性评分排序。")
        lines.append("")

        for idx, ev in enumerate(ranked, start=1):
            citation = citation_map.get(ev.id)
            lines.append(f"## 文献 {idx}")
            lines.append(f"- **ID**: `{ev.id}`")
            lines.append(f"- **标题**: {self._display_title(ev)}")

            if citation:
                authors_str = "、".join(citation.authors) if citation.authors else "未知"
                lines.append(f"- **作者**: {authors_str}")
                lines.append(f"- **年份**: {citation.year}")

            lines.append(f"- **来源类型**: {ev.sourceType.value}")
            lines.append(f"- **发表时间**: {ev.metadata.publishDate or '未知'}")
            lines.append(f"- **相关性评分**: {ev.score:.2f}")
            lines.append(f"- **是否同行评审**: {'是' if ev.metadata.isPeerReviewed else '否'}")

            if ev.metadata.citationCount > 0:
                lines.append(f"- **引用次数**: {ev.metadata.citationCount}")

            lines.append(f"- **链接**: [{ev.url}]({ev.url})")
            lines.append("")

            # 添加摘要/说明
            snippet = " ".join(ev.content.split()).strip()
            if snippet:
                lines.append("**摘要/说明**:")
                lines.append(f"> {snippet[:500]}{'...' if len(snippet) > 500 else ''}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)
