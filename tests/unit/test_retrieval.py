from datetime import UTC, datetime

from app.services.retrieval import RetrievalService


def test_query_expansion_shape() -> None:
    expanded = RetrievalService.expand_query("transformer architecture")
    year = datetime.now(tz=UTC).year
    assert "(transformer architecture OR transformer architecture review)" in expanded
    assert f"({year} OR {year - 1} OR {year - 2})" in expanded
