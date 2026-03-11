from datetime import UTC, datetime

from app.models.schemas import Evidence, EvidenceMetadata, ExtractedData, SourceType
from app.services.retrieval import RetrievalService


def test_query_expansion_shape() -> None:
    expanded = RetrievalService.expand_query("transformer architecture")
    year = datetime.now(tz=UTC).year
    assert "(transformer architecture OR transformer architecture review)" in expanded
    assert f"({year} OR {year - 1} OR {year - 2})" in expanded


def test_clean_text_decodes_unicode_and_html() -> None:
    cleaned = RetrievalService._clean_text("A&amp;B \\u4e2d\\u6587 <b>test</b>")  # noqa: SLF001
    assert cleaned == "A&B 中文 test"


def test_validate_evidences_filters_garbled_payload() -> None:
    good = Evidence(
        id="e1",
        taskId="t1",
        nodeId="n1",
        sourceType=SourceType.WEB,
        url="https://example.net/good",
        content="这是一段足够长的正常研究摘要，用于验证过滤器不会误删可信内容。",
        metadata=EvidenceMetadata(
            authors=[],
            publishDate="2024-01-01T00:00:00Z",
            title="正常标题",
            abstract="正常摘要",
            impactFactor=0,
            isPeerReviewed=False,
            relevanceScore=0.8,
            citationCount=0,
        ),
        score=0.8,
        extractedData=ExtractedData(),
    )
    bad = Evidence(
        id="e2",
        taskId="t1",
        nodeId="n1",
        sourceType=SourceType.WEB,
        url="https://example.net/bad",
        content='ǵ(002594) Ͷ_F10_ͬ˳ڷ d1\\u5e03\\u7684\\u6743\\u5a01\\u4fe1\\u606f {"type":1,"publishsource":"xx"}',
        metadata=EvidenceMetadata(
            authors=[],
            publishDate="2024-01-01T00:00:00Z",
            title="F10 异常标题",
            abstract="",
            impactFactor=0,
            isPeerReviewed=False,
            relevanceScore=0.2,
            citationCount=0,
        ),
        score=0.2,
        extractedData=ExtractedData(),
    )
    validated = RetrievalService._validate_evidences([good, bad], allow_mock=False)  # noqa: SLF001
    assert [ev.id for ev in validated] == ["e1"]
