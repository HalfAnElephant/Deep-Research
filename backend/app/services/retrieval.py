from __future__ import annotations

import asyncio
import logging
import re
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from hashlib import sha1
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx

from app.core.config import settings
from app.core.utils import now_iso
from app.core.utils import new_id
from app.models.schemas import Evidence, EvidenceMetadata, ExtractedData, SourceType
from app.services.retry import retry_async

logger = logging.getLogger(__name__)


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
    _PLACEHOLDER_HOSTS = {"example.org", "example.com", "localhost", "127.0.0.1", "httpbin.org"}

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
        year = datetime.now(tz=UTC).year
        year_part = f"({year} OR {year - 1} OR {year - 2})"
        if any(ord(ch) > 127 for ch in term):
            focus_part = f"({term})"
        else:
            focus_part = f"({term} OR {term} review)"
        return f"{focus_part} AND {year_part}"

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
                url=f"mock://paper/{node_id}",
                content=f"[MOCK] Synthetic evidence for query: {query}",
                metadata=EvidenceMetadata(
                    authors=["Mock Author"],
                    publishDate="2025-01-01T00:00:00Z",
                    title=f"[MOCK] {source} result for {query[:40]}",
                    abstract="[MOCK] This abstract is synthetic and for test mode only.",
                    impactFactor=5.2,
                    isPeerReviewed=True,
                    relevanceScore=synthetic_metric,
                    citationCount=42,
                ),
                score=synthetic_metric,
                extractedData=ExtractedData(
                    tables=[{"caption": "Sample table", "data": {"rows": 3}}],
                    images=[{"caption": "Sample figure", "url": "mock://img/1.png"}],
                    numericalValues=[{"value": synthetic_metric, "unit": "score", "context": "relevance"}],
                ),
            )
        ]

    async def _real_retrieve(self, *, task_id: str, node_id: str, query: str, sources: list[str]) -> list[Evidence]:
        normalized_sources = [self._normalize_source_name(s) for s in sources] if sources else []
        if not normalized_sources:
            normalized_sources = ["tavily", "arxiv", "semanticscholar"]

        provider_calls: list[tuple[str, asyncio.Future]] = []
        for source in normalized_sources:
            if source == "tavily":
                if settings.tavily_api_key:
                    provider_calls.append(
                        (
                            source,
                            asyncio.create_task(
                                self._safe_provider_call(
                                    source,
                                    self._retrieve_from_tavily,
                                    task_id=task_id,
                                    node_id=node_id,
                                    query=query,
                                )
                            ),
                        )
                    )
                continue
            if source == "arxiv":
                provider_calls.append(
                    (
                        source,
                        asyncio.create_task(
                            self._safe_provider_call(
                                source,
                                self._retrieve_from_arxiv,
                                task_id=task_id,
                                node_id=node_id,
                                query=query,
                            )
                        ),
                    )
                )
                continue
            if source == "semanticscholar":
                provider_calls.append(
                    (
                        source,
                        asyncio.create_task(
                            self._safe_provider_call(
                                source,
                                self._retrieve_from_semantic_scholar,
                                task_id=task_id,
                                node_id=node_id,
                                query=query,
                            )
                        ),
                    )
                )

        if not provider_calls and settings.tavily_api_key:
            provider_calls.append(
                (
                    "tavily",
                    asyncio.create_task(
                        self._safe_provider_call(
                            "tavily",
                            self._retrieve_from_tavily,
                            task_id=task_id,
                            node_id=node_id,
                            query=query,
                        )
                    ),
                )
            )

        gathered: list[Evidence] = []
        for _, provider_task in provider_calls:
            gathered.extend(await provider_task)

        valid = self._validate_evidences(gathered, allow_mock=False)
        return self._dedupe_by_url(valid)

    async def _safe_provider_call(
        self,
        provider_name: str,
        provider_func,
        *,
        task_id: str,
        node_id: str,
        query: str,
    ) -> list[Evidence]:
        try:
            return await provider_func(task_id=task_id, node_id=node_id, query=query)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Provider '%s' failed: %s", provider_name, exc)
            return []

    async def _retrieve_from_tavily(self, *, task_id: str, node_id: str, query: str) -> list[Evidence]:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await retry_async(
                lambda: client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": settings.tavily_api_key,
                        "query": query,
                        "search_depth": "advanced",
                        "max_results": 5,
                        "include_answer": False,
                        "include_raw_content": True,
                    },
                ),
                max_attempts=3,
                base_delay_seconds=0.8,
            )
            assert isinstance(resp, httpx.Response)
            resp.raise_for_status()
            payload = resp.json()

        results = payload.get("results", [])
        evidences: list[Evidence] = []
        for item in results:
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            score = float(item.get("score", 0.6))
            url = str(item.get("url", ""))
            title = str(item.get("title", "Untitled Web Result"))
            evidences.append(
                Evidence(
                    id=new_id(),
                    taskId=task_id,
                    nodeId=node_id,
                    sourceType=SourceType.WEB,
                    url=url,
                    content=content,
                    metadata=EvidenceMetadata(
                        authors=[],
                        publishDate=str(item.get("published_date") or now_iso()),
                        title=title,
                        abstract=content[:500],
                        impactFactor=0,
                        isPeerReviewed=False,
                        relevanceScore=max(0.0, min(score, 1.0)),
                        citationCount=0,
                    ),
                    score=max(0.0, min(score, 1.0)),
                    extractedData=ExtractedData(
                        numericalValues=[
                            {
                                "value": round(max(0.0, min(score, 1.0)), 4),
                                "unit": "score",
                                "context": "relevance",
                            }
                        ]
                    ),
                )
            )
        return evidences

    async def _retrieve_from_arxiv(self, *, task_id: str, node_id: str, query: str) -> list[Evidence]:
        search_query = f"all:{self._keyword_query_for_paper_apis(query)}"
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": 5,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await retry_async(
                lambda: client.get("https://export.arxiv.org/api/query", params=params),
                max_attempts=3,
                base_delay_seconds=0.7,
            )
            assert isinstance(resp, httpx.Response)
            resp.raise_for_status()
            payload = resp.text

        root = ElementTree.fromstring(payload)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        evidences: list[Evidence] = []
        for idx, entry in enumerate(entries):
            title = self._read_xml_text(entry, "atom:title", ns)
            summary = self._read_xml_text(entry, "atom:summary", ns)
            if not title and not summary:
                continue
            url = self._read_xml_text(entry, "atom:id", ns)
            if url.startswith("http://"):
                url = "https://" + url[len("http://") :]
            published = self._read_xml_text(entry, "atom:published", ns) or now_iso()
            authors = [
                name.text.strip()
                for name in entry.findall("atom:author/atom:name", ns)
                if name.text and name.text.strip()
            ]
            rank_score = max(0.45, round(0.9 - idx * 0.08, 3))
            evidences.append(
                Evidence(
                    id=new_id(),
                    taskId=task_id,
                    nodeId=node_id,
                    sourceType=SourceType.PAPER,
                    url=url,
                    content=summary or title,
                    metadata=EvidenceMetadata(
                        authors=authors,
                        publishDate=published,
                        title=title or "arXiv paper",
                        abstract=summary[:500] if summary else "",
                        impactFactor=0,
                        isPeerReviewed=False,
                        relevanceScore=rank_score,
                        citationCount=0,
                    ),
                    score=rank_score,
                    extractedData=ExtractedData(),
                )
            )
        return evidences

    async def _retrieve_from_semantic_scholar(self, *, task_id: str, node_id: str, query: str) -> list[Evidence]:
        paper_query = self._keyword_query_for_paper_apis(query)
        params = {
            "query": paper_query,
            "limit": 5,
            "fields": "title,abstract,authors,year,url,publicationDate,citationCount,paperId,openAccessPdf",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await retry_async(
                lambda: client.get("https://api.semanticscholar.org/graph/v1/paper/search", params=params),
                max_attempts=3,
                base_delay_seconds=0.8,
            )
            assert isinstance(resp, httpx.Response)
            resp.raise_for_status()
            payload = resp.json()

        results = payload.get("data", [])
        evidences: list[Evidence] = []
        for idx, item in enumerate(results):
            abstract = str(item.get("abstract") or "").strip()
            title = str(item.get("title") or "Semantic Scholar paper").strip()
            if not abstract and not title:
                continue
            authors = [str(author.get("name", "")).strip() for author in item.get("authors", []) if author.get("name")]
            year = item.get("year")
            publication_date = str(item.get("publicationDate") or "").strip()
            if not publication_date and isinstance(year, int):
                publication_date = f"{year}-01-01T00:00:00Z"
            if not publication_date:
                publication_date = now_iso()
            url = str(item.get("url") or "").strip()
            if not url:
                open_pdf = item.get("openAccessPdf") or {}
                url = str(open_pdf.get("url") or "").strip()
            if not url:
                paper_id = str(item.get("paperId") or "").strip()
                if paper_id:
                    url = f"https://www.semanticscholar.org/paper/{paper_id}"

            citation_count = int(item.get("citationCount") or 0)
            rank_bonus = max(0.0, 0.15 - idx * 0.03)
            score = max(0.45, min(0.95, round(0.52 + min(citation_count, 400) / 1200 + rank_bonus, 3)))

            evidences.append(
                Evidence(
                    id=new_id(),
                    taskId=task_id,
                    nodeId=node_id,
                    sourceType=SourceType.PAPER,
                    url=url,
                    content=abstract or title,
                    metadata=EvidenceMetadata(
                        authors=authors,
                        publishDate=publication_date,
                        title=title,
                        abstract=(abstract or title)[:500],
                        impactFactor=0,
                        isPeerReviewed=False,
                        relevanceScore=score,
                        citationCount=citation_count,
                    ),
                    score=score,
                    extractedData=ExtractedData(
                        numericalValues=[
                            {
                                "value": float(citation_count),
                                "unit": "citations",
                                "context": "semantic_scholar_citation_count",
                            }
                        ]
                    ),
                )
            )
        return evidences

    @classmethod
    def _normalize_source_name(cls, source: str) -> str:
        lowered = source.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
        if lowered in {"arxiv", "arxivorg"}:
            return "arxiv"
        if lowered in {"semanticscholar", "s2"}:
            return "semanticscholar"
        if lowered == "tavily":
            return "tavily"
        return lowered

    @classmethod
    def _is_placeholder_url(cls, url: str) -> bool:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        return hostname in cls._PLACEHOLDER_HOSTS

    @staticmethod
    def _clean_text(content: str) -> str:
        return " ".join(content.split())

    @staticmethod
    def _read_xml_text(entry, path: str, ns: dict[str, str]) -> str:
        item = entry.find(path, ns)
        return item.text.strip() if item is not None and item.text else ""

    @staticmethod
    def _keyword_query_for_paper_apis(query: str) -> str:
        cleaned_query = re.sub(r"[\(\)]", " ", query)
        ascii_tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-_]{1,}", cleaned_query)
        stop_tokens = {"and", "or", "review", "analyze", "improve", "evaluate"}
        picked = [token for token in ascii_tokens if token.lower() not in stop_tokens]
        if picked:
            base = " ".join(picked[:8])
            if any(word in query for word in ["软件", "工程", "开发", "代码"]):
                base += " software engineering"
            if "测试" in query:
                base += " testing"
            if "挑战" in query:
                base += " challenges"
            return base.strip()
        return "artificial intelligence agent software engineering"

    @classmethod
    def _validate_evidences(cls, evidences: list[Evidence], *, allow_mock: bool) -> list[Evidence]:
        valid: list[Evidence] = []
        for ev in evidences:
            parsed = urlparse(ev.url)
            if not ev.url:
                continue
            if allow_mock and parsed.scheme == "mock":
                valid.append(ev)
                continue
            if parsed.scheme not in {"http", "https"}:
                continue
            if cls._is_placeholder_url(ev.url):
                continue
            cleaned = cls._clean_text(ev.content)
            if len(cleaned) < 30:
                continue
            ev.content = cleaned
            if not ev.metadata.title:
                ev.metadata.title = ev.url
            valid.append(ev)
        return valid

    @staticmethod
    def _dedupe_by_url(evidences: list[Evidence]) -> list[Evidence]:
        deduped: list[Evidence] = []
        seen: set[str] = set()
        for ev in evidences:
            key = ev.url.rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            deduped.append(ev)
        return deduped
