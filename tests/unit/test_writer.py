from app.models.schemas import Evidence, EvidenceMetadata, ExtractedData, SourceType
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
    md_path, bib_path, citations = writer.write_report(
        task_id="t1",
        task_title="Demo",
        sections=[("n1", "section content")],
        evidences=[evidence],
    )
    report = (tmp_path / "t1.md").read_text(encoding="utf-8")
    assert (tmp_path / "t1.md").exists()
    assert (tmp_path / "t1.bib").exists()
    assert md_path.endswith(".md")
    assert bib_path.endswith(".bib")
    assert "e1" in citations
    assert "证据：Paper A" in report
    assert "https://example.org/e1" in report
