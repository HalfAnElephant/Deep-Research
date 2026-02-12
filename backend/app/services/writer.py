from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import httpx

from app.core.config import settings
from app.models.schemas import Citation, Evidence


class WriterService:
    def __init__(self, output_dir: str = "backend/.data/reports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_report(
        self,
        *,
        task_id: str,
        task_title: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        locked_sections: set[str] | None = None,
    ) -> tuple[str, str, dict[str, Citation]]:
        locked_sections = locked_sections or set()
        citation_map = self._build_citations(evidences)

        generated_body = self._generate_body(task_title=task_title, sections=sections, evidences=evidences)
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

    def _generate_body(self, *, task_title: str, sections: list[tuple[str, str]], evidences: list[Evidence]) -> str:
        evidence_rich_template = self._generate_template(task_title=task_title, sections=sections, evidences=evidences)
        if settings.use_mock_sources:
            return evidence_rich_template

        llm_text = self._generate_with_llm(task_title=task_title, sections=sections, evidences=evidences)
        if not llm_text:
            return evidence_rich_template
        return "\n".join(
            [
                "## AI 综合解读",
                llm_text.strip(),
                "",
                evidence_rich_template,
            ]
        )

    def _generate_with_llm(self, *, task_title: str, sections: list[tuple[str, str]], evidences: list[Evidence]) -> str:
        base_url, api_key, model = self._resolve_provider()
        if not base_url or not api_key:
            return ""

        evidence_snippets = "\n".join(
            f"- [{ev.id}] {ev.metadata.title}: {ev.content[:300]} (url={ev.url})" for ev in evidences[:12]
        )
        section_snippets = "\n".join(f"- {content[:180]}" for _, content in sections[:8])
        prompt = (
            f"研究题目：{task_title}\n"
            "请生成中文研究报告，包含：摘要、背景、关键发现、方法与证据、局限性、结论与后续建议。\n"
            "保持结构化、客观、可读性强。禁止编造不存在的数据、论文、链接。\n"
            "每个关键结论必须引用至少一个证据ID（例如 [evidence:xxxx]）。\n\n"
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
    def _generate_template(*, task_title: str, sections: list[tuple[str, str]], evidences: list[Evidence]) -> str:
        ranked = sorted(evidences, key=lambda item: item.score, reverse=True)
        top = ranked[:8]
        source_types = sorted({ev.sourceType.value for ev in ranked})
        lines = [
            "## 摘要",
            f"本文围绕“{task_title}”进行研究，共纳入 {len(ranked)} 条证据，来源类型：{', '.join(source_types) or '无'}。",
            "",
            "## 关键发现",
        ]
        if not top:
            lines.append("当前没有检索到可用证据，请检查数据源配置与网络连通性后重试。")
        for idx, ev in enumerate(top, start=1):
            lines.append(f"{idx}. {ev.metadata.title}（score={ev.score:.2f}, evidenceId={ev.id}）")

        lines.extend(["", "## 证据化分析"])
        section_to_evidence: dict[str, list[Evidence]] = defaultdict(list)
        for ev in ranked:
            section_to_evidence[ev.nodeId].append(ev)

        used_ids: set[str] = set()
        for section_id, section_content in sections[:8]:
            section_lines = [line.strip() for line in section_content.splitlines() if line.strip()]
            section_title = section_lines[0] if section_lines else section_id
            section_desc = section_lines[1] if len(section_lines) > 1 else section_content.strip()
            lines.append(f"### {section_title}")
            lines.append(f"分析范围：{section_desc[:220]}")
            matched = section_to_evidence.get(section_id, [])[:3]
            for ev in matched:
                used_ids.add(ev.id)
                lines.append(f"- 证据：{ev.metadata.title}")
                lines.append(
                    f"  来源：{ev.sourceType.value} | 时间：{ev.metadata.publishDate or '未知'} | 相关性：{ev.score:.2f}"
                )
                lines.append(f"  摘要：{ev.content[:260]}")
                lines.append(f"  链接：{ev.url} | evidenceId={ev.id}")
            if not matched:
                lines.append("- 该主题暂未命中专属证据，建议扩展关键词后补检索。")
            lines.append("")

        leftovers = [ev for ev in ranked if ev.id not in used_ids][:5]
        if leftovers:
            lines.append("## 补充证据")
            for ev in leftovers:
                lines.append(f"- {ev.metadata.title} | {ev.url} | evidenceId={ev.id}")
            lines.append("")

        lines.extend(
            [
                "## 局限性",
                "当前结果依赖公开可访问来源，未覆盖付费数据库与私有实验记录；部分来源可能缺少标准化元数据。",
                "",
                "## 结论与建议",
                "建议优先围绕高相关性证据开展二次核验，并为关键结论补充可复现实验或行业数据。",
            ]
        )
        return "\n".join(lines)

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
