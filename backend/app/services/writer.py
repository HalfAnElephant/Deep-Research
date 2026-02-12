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
    URL_PATTERN = re.compile(r"https?://\S+")

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
    ) -> tuple[str, str, dict[str, Citation]]:
        locked_sections = locked_sections or set()
        blueprint = blueprint or self._default_blueprint()
        citation_map = self._build_citations(evidences)

        generated_body = self._generate_body(
            task_title=task_title,
            task_description=task_description,
            sections=sections,
            evidences=evidences,
            blueprint=blueprint,
        )
        lines = [f"# {task_title}", "", f"_taskId: {task_id}_", ""]
        lines.extend(generated_body.splitlines())
        lines.append("")

        # Keep section-to-task traceability even when LLM text is used.
        for idx, (section_id, content) in enumerate(sections, start=1):
            lines.append(f"## Trace Section {idx}")
            if section_id in locked_sections:
                lines.append(f"[LOCKED] {content}")
            else:
                lines.append(content)
            lines.append("")

        lines.extend(self._build_evidence_appendix(evidences).splitlines())
        lines.append("")
        lines.append("## References")
        for i, cid in enumerate(citation_map, start=1):
            c = citation_map[cid]
            lines.append(f"[{i}] {', '.join(c.authors)} ({c.year}). {c.title}. {c.url}")

        md_path = self.output_dir / f"{task_id}.md"
        md_path.write_text("\n".join(lines), encoding="utf-8")

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
        return str(md_path), str(bib_path), citation_map

    def _generate_body(
        self,
        *,
        task_title: str,
        task_description: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint,
    ) -> str:
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
        return "\n".join(
            [
                "## AI 综合解读",
                sanitized,
                "",
                evidence_rich_template,
            ]
        )

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
            f"- [{ev.id}] {ev.metadata.title}: {ev.content[:220]}" for ev in evidences[:12]
        )
        section_snippets = "\n".join(f"- {content[:180]}" for _, content in sections[:8])
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

    @staticmethod
    def _generate_template(
        *,
        task_title: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint,
    ) -> str:
        ranked = sorted(evidences, key=lambda item: item.score, reverse=True)
        top = ranked[:6]
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
                lines.append(
                    f"围绕“{task_title}”共纳入 {len(ranked)} 条证据，来源类型：{', '.join(source_types) or '无'}。"
                )
                if top:
                    refs = "、".join(f"[evidence:{ev.id}]" for ev in top[:3])
                    lines.append(f"高优先证据线索：{refs}")
                else:
                    lines.append("当前没有检索到可用证据，请检查数据源配置与网络连通性后重试。")
                lines.append("")
                continue

            if not sections:
                lines.append("暂无可用任务分段，建议补充分解后重试。")
                lines.append("")
                continue

            section_idx = min(idx - 1, len(sections) - 1)
            section_id, section_content = sections[section_idx]
            section_lines = [line.strip() for line in section_content.splitlines() if line.strip()]
            section_title = section_lines[0] if section_lines else section_id
            section_desc = section_lines[1] if len(section_lines) > 1 else section_content.strip()
            lines.append(f"关注问题：{section_title}")
            lines.append(f"分析范围：{section_desc[:220]}")

            matched = section_to_evidence.get(section_id, [])[:2]
            if matched:
                for ev in matched:
                    used_ids.add(ev.id)
                    lines.append(f"- 论据线索：{ev.metadata.title} [evidence:{ev.id}]")
            else:
                lines.append("- 当前未命中该分段的直接证据，建议扩展检索词。")
            lines.append("")

        leftovers = [ev for ev in ranked if ev.id not in used_ids][:4]
        if leftovers:
            lines.append("## 补充线索")
            for ev in leftovers:
                lines.append(f"- {ev.metadata.title} [evidence:{ev.id}]")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _build_evidence_appendix(evidences: list[Evidence]) -> str:
        ranked = sorted(evidences, key=lambda item: item.score, reverse=True)
        lines = ["## 证据说明与来源链接"]
        if not ranked:
            lines.append("暂无可用证据。")
            return "\n".join(lines)

        for idx, ev in enumerate(ranked, start=1):
            snippet = " ".join(ev.content.split())
            lines.append(f"{idx}. [{ev.id}] {ev.metadata.title}")
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
            objective="给出结构化分析结论，并覆盖可执行建议",
            tone="客观中立、简洁清晰",
            section_titles=["摘要", "背景", "关键发现", "分析", "结论与建议"],
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
                title=ev.metadata.title,
                year=year,
                source=ev.sourceType.value,
                url=ev.url,
            )
        return citations
