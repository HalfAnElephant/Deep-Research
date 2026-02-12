from app.models.schemas import Evidence, EvidenceMetadata, ExtractedData, SourceType
from app.services.analyst import AnalystService


def _evidence(eid: str, value: float) -> Evidence:
    return Evidence(
        id=eid,
        taskId="t1",
        nodeId="n1",
        sourceType=SourceType.PAPER,
        url=f"https://example.org/{eid}",
        content="x",
        metadata=EvidenceMetadata(
            authors=["A"],
            publishDate="2025-01-01T00:00:00Z",
            title=f"Title {eid}",
            abstract="",
            impactFactor=5.0,
            isPeerReviewed=True,
            relevanceScore=0.8,
            citationCount=1,
        ),
        score=0.8,
        extractedData=ExtractedData(numericalValues=[{"value": value, "unit": "score", "context": "metric"}]),
    )


def test_detect_conflicts_with_variance() -> None:
    analyst = AnalystService()
    evidences = [_evidence("e1", 0.9), _evidence("e2", 0.5)]
    conflicts = analyst.detect_conflicts("task1", evidences, threshold=0.15)
    assert len(conflicts) == 1
    assert conflicts[0].resolutionStatus.value == "OPEN"
