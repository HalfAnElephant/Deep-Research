from __future__ import annotations

from pathlib import Path

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

        lines = [f"# {task_title}", "", f"_taskId: {task_id}_", ""]
        for idx, (section_id, content) in enumerate(sections, start=1):
            lines.append(f"## Section {idx}")
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
