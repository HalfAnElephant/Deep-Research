from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from hashlib import sha1

import httpx

from app.core.config import settings
from app.core.utils import new_id
from app.models.schemas import Evidence, EvidenceMetadata, ExtractedData, SourceType
from app.services.retry import retry_async


class L1EvidenceCache:
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600) -> None:
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        self._store: OrderedDict[str, tuple[datetime, list[Evidence]]] = OrderedDict()

    def get(self, key: str) -> list[Evidence] | None:
        item = self._store.get(key)
        if not item:
            return None
        ts, value = item
        if datetime.now(tz=UTC) - ts > self.ttl:
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: list[Evidence]) -> None:
        self._store[key] = (datetime.now(tz=UTC), value)
        self._store.move_to_end(key)
        while len(self._store) > self.max_size:
            self._store.popitem(last=False)


class RetrievalService:
    def __init__(self) -> None:
        self.cache = L1EvidenceCache()

    async def retrieve(self, *, task_id: str, node_id: str, query: str, sources: list[str]) -> list[Evidence]:
        expanded = self.expand_query(query)
        cache_key = sha1(f"{task_id}:{node_id}:{expanded}".encode()).hexdigest()
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        if settings.use_mock_sources:
            evidences = await self._mock_retrieve(task_id=task_id, node_id=node_id, query=expanded, sources=sources)
        else:
            evidences = await self._real_retrieve(task_id=task_id, node_id=node_id, query=expanded, sources=sources)
        self.cache.set(cache_key, evidences)
        return evidences

    @staticmethod
    def expand_query(query: str) -> str:
        term = query.strip()
        year_part = "(2026 OR 2025 OR 2024)"
        verb_part = "(analyze OR improve OR evaluate)"
        return f"({term} OR {term} review) AND {year_part} AND {verb_part}"

    async def _mock_retrieve(self, *, task_id: str, node_id: str, query: str, sources: list[str]) -> list[Evidence]:
        await asyncio.sleep(0.05)
        source = sources[0] if sources else "MockSource"
        synthetic_metric = round(((sum(ord(c) for c in node_id) % 60) / 100) + 0.2, 2)
        return [
            Evidence(
                id=new_id(),
                taskId=task_id,
                nodeId=node_id,
                sourceType=SourceType.PAPER,
                url=f"https://example.org/paper/{node_id}",
                content=f"Mock evidence generated for query: {query}",
                metadata=EvidenceMetadata(
                    authors=["Mock Author"],
                    publishDate="2025-01-01T00:00:00Z",
                    title=f"{source} result for {query[:40]}",
                    abstract="This is a mock abstract.",
                    impactFactor=5.2,
                    isPeerReviewed=True,
                    relevanceScore=synthetic_metric,
                    citationCount=42,
                ),
                score=synthetic_metric,
                extractedData=ExtractedData(
                    tables=[{"caption": "Sample table", "data": {"rows": 3}}],
                    images=[{"caption": "Sample figure", "url": "https://example.org/img/1.png"}],
                    numericalValues=[{"value": synthetic_metric, "unit": "score", "context": "relevance"}],
                ),
            )
        ]

    async def _real_retrieve(self, *, task_id: str, node_id: str, query: str, sources: list[str]) -> list[Evidence]:
        # Minimal real-mode fallback. Full provider integration is intentionally kept lightweight for single-user use.
        if not sources:
            sources = ["web"]
        results: list[Evidence] = []
        async with httpx.AsyncClient(timeout=10) as client:
            for source in sources[:2]:
                url = f"https://httpbin.org/anything/{source}"
                resp = await retry_async(
                    lambda: client.get(url, params={"q": query}),
                    max_attempts=3,
                    base_delay_seconds=0.5,
                )
                assert isinstance(resp, httpx.Response)
                resp.raise_for_status()
                payload = resp.json()
                results.append(
                    Evidence(
                        id=new_id(),
                        taskId=task_id,
                        nodeId=node_id,
                        sourceType=SourceType.WEB,
                        url=url,
                        content=f"Fetched payload echo for source={source}.",
                        metadata=EvidenceMetadata(
                            authors=[],
                            publishDate="2026-01-01T00:00:00Z",
                            title=f"Web result ({source})",
                            abstract=str(payload)[:300],
                            impactFactor=0,
                            isPeerReviewed=False,
                            relevanceScore=0.65,
                            citationCount=0,
                        ),
                        score=0.65,
                        extractedData=ExtractedData(),
                    )
                )
        return results
