from __future__ import annotations

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
        if not settings.use_mock_sources:
            llm_text = self._generate_with_llm(task_title=task_title, sections=sections, evidences=evidences)
            if llm_text:
                return llm_text
        return self._generate_template(task_title=task_title, sections=sections, evidences=evidences)

    def _generate_with_llm(self, *, task_title: str, sections: list[tuple[str, str]], evidences: list[Evidence]) -> str:
        base_url, api_key, model = self._resolve_provider()
        if not base_url or not api_key:
            return ""

        evidence_snippets = "\n".join(
            f"- {ev.metadata.title}: {ev.content[:300]} (url={ev.url})" for ev in evidences[:12]
        )
        section_snippets = "\n".join(f"- {content[:180]}" for _, content in sections[:8])
        prompt = (
            f"研究题目：{task_title}\n"
            "请生成中文研究报告，包含：摘要、背景、关键发现、方法与证据、局限性、结论与后续建议。\n"
            "保持结构化、客观、可读性强。不要编造不存在的数据。\n\n"
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
        top = evidences[:5]
        lines = [
            "## 摘要",
            f"本文围绕“{task_title}”进行快速研究，总结了当前公开资料中的关键观点与证据。",
            "",
            "## 关键发现",
        ]
        for idx, ev in enumerate(top, start=1):
            lines.append(f"{idx}. {ev.metadata.title}（score={ev.score:.2f}）")
        lines.extend(["", "## 分析说明"])
        for _, section_content in sections[:4]:
            lines.append(f"- {section_content[:220]}")
        lines.extend(
            [
                "",
                "## 结论",
                "当前证据已覆盖主要趋势，但仍需针对高争议结论补充更高质量、可复现实验的数据。",
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
