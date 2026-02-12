from app.services.retrieval import RetrievalService


def test_query_expansion_shape() -> None:
    expanded = RetrievalService.expand_query("transformer architecture")
    assert "(transformer architecture OR transformer architecture review)" in expanded
    assert "(2026 OR 2025 OR 2024)" in expanded
    assert "(analyze OR improve OR evaluate)" in expanded
