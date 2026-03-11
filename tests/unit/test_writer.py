from app.models.schemas import Evidence, EvidenceMetadata, ExtractedData, SourceType
from app.core.config import settings
from app.services.writer import WriterService


def test_writer_generates_md_and_bib(tmp_path) -> None:
    writer = WriterService(output_dir=str(tmp_path))
    evidence = Evidence(
        id="e1",
        taskId="t1",
        nodeId="n1",
        sourceType=SourceType.PAPER,
        url="https://example.org/e1",
        content="content",
        metadata=EvidenceMetadata(
            authors=["Alice"],
            publishDate="2024-01-01T00:00:00Z",
            title="Paper A",
            abstract="",
            impactFactor=2.0,
            isPeerReviewed=True,
            relevanceScore=0.8,
            citationCount=1,
        ),
        score=0.8,
        extractedData=ExtractedData(),
    )
    article_path, references_path, citations = writer.write_report(
        task_id="t1",
        task_title="Demo",
        article_title="面向可靠性验证的 Demo 研究",
        task_description="请输出研究报告",
        sections=[("n1", "section content")],
        evidences=[evidence],
        report_body="## 引言\n\n这是一段带有 [evidence:e1] 的正文，用于验证引用替换和导出行为。\n\n## 结论\n\n结论同样引用 [evidence:e1]。",
    )
    report = (tmp_path / "t1_article.md").read_text(encoding="utf-8")
    assert (tmp_path / "t1.md").exists()
    assert (tmp_path / "t1_article.md").exists()
    assert (tmp_path / "t1_references.md").exists()
    assert (tmp_path / "t1.bib").exists()
    assert article_path.endswith("_article.md")
    assert references_path.endswith("_references.md")
    assert "e1" in citations
    body, _, appendix = report.partition("## 参考文献")
    assert "https://example.org/e1" not in body
    assert "https://example.org/e1" in appendix
    assert "[1]" in report
    assert "[evidence:e1]" not in report
    assert "## Trace Section" not in report
    assert report.startswith("# 面向可靠性验证的 Demo 研究")


def test_writer_sanitizes_placeholder_titles(tmp_path) -> None:
    writer = WriterService(output_dir=str(tmp_path))
    evidence = Evidence(
        id="e1",
        taskId="t1",
        nodeId="n1",
        sourceType=SourceType.PAPER,
        url="https://example.org/e1",
        content="A practical benchmark study on multi-agent reliability in software engineering.",
        metadata=EvidenceMetadata(
            authors=["Alice"],
            publishDate="2024-01-01T00:00:00Z",
            title="[MOCK] arXiv result for multi-agent reliability",
            abstract="",
            impactFactor=2.0,
            isPeerReviewed=True,
            relevanceScore=0.8,
            citationCount=1,
        ),
        score=0.8,
        extractedData=ExtractedData(),
    )
    writer.write_report(
        task_id="t1",
        task_title="Demo",
        task_description="请输出研究报告",
        sections=[("n1", "section content")],
        evidences=[evidence],
        report_body="## 引言\n\nA practical benchmark study on multi-agent reliability in software engineering. [evidence:e1]",
    )
    report = (tmp_path / "t1.md").read_text(encoding="utf-8")
    assert "arXiv result for" not in report
    assert "A practical benchmark study on multi-agent reliability" in report


def test_generate_title_sanitizes_plan_like_output(tmp_path) -> None:
    writer = WriterService(output_dir=str(tmp_path))
    title = writer._sanitize_article_title(  # noqa: SLF001
        "多智能体协作 深度研究方案",
        fallback="多智能体协作中的可靠性分析",
    )
    assert title == "多智能体协作中的可靠性分析"


def test_normalize_markdown_text_preserves_headings(tmp_path) -> None:
    writer = WriterService(output_dir=str(tmp_path))
    normalized = writer._normalize_markdown_text(  # noqa: SLF001
        "## 引言\r\n\r\n第一段包含 \\u4e2d\\u6587 内容。\r\n\r\n## 结论\r\n\r\n第二段继续展开。"
    )
    assert normalized.startswith("## 引言")
    assert "\n\n## 结论\n\n" in normalized
    assert "中文" in normalized


def test_writer_strips_meta_commentary_and_yaml_heading(tmp_path) -> None:
    writer = WriterService(output_dir=str(tmp_path))
    sanitized, suppressed = writer._sanitize_markdown_output(  # noqa: SLF001
        "## ```yaml\n\n"
        "当前提供的证据列表与研究主题高度不相关,无法为本章节的撰写提供有效支持。\n\n"
        "## 历史演变\n\n"
        "地府货币观念与民俗祭祀实践之间存在长期互动。"
    )

    assert "```yaml" not in sanitized
    assert "无法为本章节的撰写提供有效支持" not in sanitized
    assert "## 历史演变" in sanitized
    assert suppressed


def test_generate_draft_collects_suppressed_segments(tmp_path, monkeypatch) -> None:
    writer = WriterService(output_dir=str(tmp_path))
    monkeypatch.setattr(settings, "use_mock_sources", False)
    evidence = Evidence(
        id="e1",
        taskId="t1",
        nodeId="s1",
        sourceType=SourceType.PAPER,
        url="https://example.org/e1",
        content="关于冥币与祭祀经济的研究摘要。",
        metadata=EvidenceMetadata(
            authors=["Alice"],
            publishDate="2024-01-01T00:00:00Z",
            title="祭祀经济研究",
            abstract="",
            impactFactor=2.0,
            isPeerReviewed=True,
            relevanceScore=0.8,
            citationCount=1,
        ),
        score=0.8,
        extractedData=ExtractedData(),
    )

    def _fake_generate_section(**kwargs):  # noqa: ANN003
        outline = kwargs["outline"]
        if outline.heading == "历史演变与民俗本源":
            return (
                "当前提供的证据列表与研究主题高度不相关,无法为本章节的撰写提供有效支持。\n\n"
                "地府货币观念与丧葬祭祀实践相互塑造 [evidence:e1]。"
            )
        return f"围绕{outline.heading}展开分析，并引用 [evidence:e1]。\n\n第二段继续展开。"

    monkeypatch.setattr(
        writer, "_generate_single_section_with_llm", _fake_generate_section)
    monkeypatch.setattr(writer, "_resolve_provider", lambda: (
        "https://example.org", "key", "model"))

    draft = writer.generate_draft(
        task_title="地府货币体系",
        task_description="请输出研究报告。",
        sections=[
            ("s1", "历史演变与民俗本源\n\n说明来源"),
            ("s2", "仪式实践\n\n说明变化"),
            ("s3", "结论与建议\n\n总结判断"),
        ],
        evidences=[evidence],
    )

    assert draft.suppressedSegments
    assert "无法为本章节的撰写提供有效支持" not in draft.body


def test_generate_draft_keeps_other_sections_when_one_section_fails(tmp_path, monkeypatch) -> None:
    writer = WriterService(output_dir=str(tmp_path))
    monkeypatch.setattr(settings, "use_mock_sources", False)
    evidences = [
        Evidence(
            id="e1",
            taskId="t1",
            nodeId="n1",
            sourceType=SourceType.PAPER,
            url="https://example.org/e1",
            content="关于多智能体可靠性评估的基准测试总结。",
            metadata=EvidenceMetadata(
                authors=["Alice"],
                publishDate="2024-01-01T00:00:00Z",
                title="可靠性基准研究",
                abstract="",
                impactFactor=2.0,
                isPeerReviewed=True,
                relevanceScore=0.8,
                citationCount=1,
            ),
            score=0.8,
            extractedData=ExtractedData(),
        )
    ]

    def _fake_generate_section(**kwargs):  # noqa: ANN003
        outline = kwargs["outline"]
        if outline.heading == "证据与争议":
            return ""
        return (
            f"围绕{outline.heading}展开第一段分析，并引用 [evidence:e1] 说明证据基础。\n\n"
            f"第二段继续说明 {outline.brief}，确保章节结构完整。"
        )

    monkeypatch.setattr(
        writer, "_generate_single_section_with_llm", _fake_generate_section)
    monkeypatch.setattr(writer, "_resolve_provider", lambda: (
        "https://example.org", "key", "model"))

    draft = writer.generate_draft(
        task_title="多智能体工程可靠性评估",
        task_description="请输出研究报告。",
        sections=[
            ("s1", "引言与问题界定\n\n说明研究范围"),
            ("s2", "证据与争议\n\n比较主要分歧"),
            ("s3", "综合分析\n\n整合证据链"),
            ("s4", "结论与建议\n\n给出行动建议"),
        ],
        evidences=evidences,
    )

    assert draft.status in {"complete", "partial"}
    assert draft.body.count("## ") >= 3
    assert "证据与争议" in draft.body
    assert any(section.heading == "证据与争议" for section in draft.sections)
