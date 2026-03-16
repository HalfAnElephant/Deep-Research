from __future__ import annotations

import asyncio
import html
import logging
import re
import unicodedata
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
from app.services.retry import retry_async, RetryableError

logger = logging.getLogger(__name__)


class L1EvidenceCache:
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600) -> None:
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        self._store: OrderedDict[str, tuple[datetime,
                                            list[Evidence]]] = OrderedDict()

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
    _PLACEHOLDER_HOSTS = {"example.org", "example.com",
                          "localhost", "127.0.0.1", "httpbin.org"}
    _UNICODE_ESCAPE_PATTERN = re.compile(r"\\u([0-9a-fA-F]{4})")
    _MOJIBAKE_PATTERNS = (
        re.compile(r"\\u[0-9a-fA-F]{4}"),
        re.compile(r"publishsource|srsltid|download\?etag=", re.IGNORECASE),
        re.compile(r"(?:_F10_|ͬ˳|ǵ\(|51sjsj)", re.IGNORECASE),
    )

    def __init__(self) -> None:
        self.cache = L1EvidenceCache()

    async def retrieve(self, *, task_id: str, node_id: str, query: str, sources: list[str]) -> list[Evidence]:
        expanded = self.expand_query(query)
        cache_key = sha1(
            f"{task_id}:{node_id}:{expanded}".encode()).hexdigest()
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
    def _should_apply_year_filter(query: str) -> bool:
        """Determine if year filter should be applied based on query content.

        Returns False for historical research queries that need older documents.
        Returns True for technical/recent research queries.
        """
        # Keywords indicating historical research - should NOT apply year filter
        historical_keywords = [
            "历史", "校史", "发展史", "沿革", "起源", "演变", "发展历程",
            "history", "historical", "origin", "evolution", "development",
            "古代", "近代", "现代史", "年代", "时期",
            "传记", "生平", "往事", "回忆", "传统", "文化"
        ]

        query_lower = query.lower()
        for keyword in historical_keywords:
            if keyword in query_lower:
                return False

        return True

    @staticmethod
    def expand_query(query: str, *, enable_year_filter: bool | None = None) -> str:
        """Expand query with optional year filtering.

        Args:
            query: The search query
            enable_year_filter: If None, auto-detect based on query content.
                               If True/False, force enable/disable.
        """
        term = query.strip()

        # Auto-detect if year filter should be applied
        if enable_year_filter is None:
            enable_year_filter = RetrievalService._should_apply_year_filter(
                term)

        if any(ord(ch) > 127 for ch in term):
            focus_part = f"({term})"
        else:
            focus_part = f"({term} OR {term} review)"

        if enable_year_filter:
            year = datetime.now(tz=UTC).year
            year_part = f"({year} OR {year - 1} OR {year - 2})"
            return f"{focus_part} AND {year_part}"

        return focus_part

    async def _mock_retrieve(self, *, task_id: str, node_id: str, query: str, sources: list[str]) -> list[Evidence]:
        await asyncio.sleep(0.05)
        source = sources[0] if sources else "MockSource"
        synthetic_metric = round(
            ((sum(ord(c) for c in node_id) % 60) / 100) + 0.2, 2)
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
                    images=[{"caption": "Sample figure",
                             "url": "mock://img/1.png"}],
                    numericalValues=[{"value": synthetic_metric,
                                      "unit": "score", "context": "relevance"}],
                ),
            )
        ]

    async def _real_retrieve(self, *, task_id: str, node_id: str, query: str, sources: list[str]) -> list[Evidence]:
        normalized_sources = [self._normalize_source_name(
            s) for s in sources] if sources else []
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
                continue
            if source == "googlescholar":
                provider_calls.append(
                    (
                        source,
                        asyncio.create_task(
                            self._safe_provider_call(
                                source,
                                self._retrieve_from_google_scholar,
                                task_id=task_id,
                                node_id=node_id,
                                query=query,
                            )
                        ),
                    )
                )
                continue
            if source == "pubmed":
                provider_calls.append(
                    (
                        source,
                        asyncio.create_task(
                            self._safe_provider_call(
                                source,
                                self._retrieve_from_pubmed,
                                task_id=task_id,
                                node_id=node_id,
                                query=query,
                            )
                        ),
                    )
                )
                continue
            if source == "openalex":
                provider_calls.append(
                    (
                        source,
                        asyncio.create_task(
                            self._safe_provider_call(
                                source,
                                self._retrieve_from_openalex,
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
            content = self._normalize_text(str(item.get("content", "")))
            if not content:
                continue
            score = float(item.get("score", 0.6))
            url = str(item.get("url", ""))
            title = self._normalize_text(
                str(item.get("title", "Untitled Web Result")))
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
                        publishDate=str(
                            item.get("published_date") or now_iso()),
                        title=title,
                        abstract=self._normalize_text(content[:500]),
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
        # arXiv has strict rate limiting: 1 request per 3 seconds recommended
        # Using longer delays and fewer attempts
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await retry_async(
                    lambda: client.get(
                        "https://export.arxiv.org/api/query", params=params),
                    max_attempts=2,
                    base_delay_seconds=3.0,  # arXiv recommends 3 seconds between requests
                )
            except RetryableError as exc:
                logger.warning("arXiv API failed after retries: %s", exc)
                return []
            assert isinstance(resp, httpx.Response)
            if resp.status_code == 429:
                logger.warning("arXiv rate limit hit (429), returning empty results")
                return []
            resp.raise_for_status()
            payload = resp.text

        root = ElementTree.fromstring(payload)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        evidences: list[Evidence] = []
        for idx, entry in enumerate(entries):
            title = self._normalize_text(
                self._read_xml_text(entry, "atom:title", ns))
            summary = self._normalize_text(
                self._read_xml_text(entry, "atom:summary", ns))
            if not title and not summary:
                continue
            url = self._read_xml_text(entry, "atom:id", ns)
            if url.startswith("http://"):
                url = "https://" + url[len("http://"):]
            published = self._read_xml_text(
                entry, "atom:published", ns) or now_iso()
            authors = [
                self._normalize_text(name.text)
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
                lambda: client.get(
                    "https://api.semanticscholar.org/graph/v1/paper/search", params=params),
                max_attempts=3,
                base_delay_seconds=0.8,
            )
            assert isinstance(resp, httpx.Response)
            resp.raise_for_status()
            payload = resp.json()

        results = payload.get("data", [])
        evidences: list[Evidence] = []
        for idx, item in enumerate(results):
            abstract = self._normalize_text(str(item.get("abstract") or ""))
            title = self._normalize_text(
                str(item.get("title") or "Semantic Scholar paper"))
            if not abstract and not title:
                continue
            authors = [
                self._normalize_text(str(author.get("name", "")))
                for author in item.get("authors", [])
                if author.get("name")
            ]
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
            score = max(0.45, min(0.95, round(
                0.52 + min(citation_count, 400) / 1200 + rank_bonus, 3)))

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

    async def _retrieve_from_pubmed(self, *, task_id: str, node_id: str, query: str) -> list[Evidence]:
        """Search PubMed using NCBI E-utilities API (free, no API key required)."""
        # Step 1: Search for PMIDs
        search_query = self._keyword_query_for_paper_apis(query)
        search_params = {
            "db": "pubmed",
            "term": search_query,
            "retmode": "json",
            "retmax": 5,
            "sort": "relevance",
        }

        async with httpx.AsyncClient(timeout=20) as client:
            search_resp = await retry_async(
                lambda: client.get(
                    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                    params=search_params,
                ),
                max_attempts=3,
                base_delay_seconds=0.5,
            )
            assert isinstance(search_resp, httpx.Response)
            search_resp.raise_for_status()
            search_data = search_resp.json()

        pmids = search_data.get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return []

        # Step 2: Fetch article details using ESummary
        summary_params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json",
        }

        async with httpx.AsyncClient(timeout=20) as client:
            summary_resp = await retry_async(
                lambda: client.get(
                    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                    params=summary_params,
                ),
                max_attempts=3,
                base_delay_seconds=0.5,
            )
            assert isinstance(summary_resp, httpx.Response)
            summary_resp.raise_for_status()
            summary_data = summary_resp.json()

        result = summary_data.get("result", {})
        evidences: list[Evidence] = []

        for idx, pmid in enumerate(pmids):
            article = result.get(pmid, {})
            if not article:
                continue

            title = self._normalize_text(str(article.get("title", "")))
            # PubMed ESummary doesn't return abstract directly, use title as fallback
            abstract = title  # We'll try to fetch abstracts in a follow-up if needed

            # Extract authors
            author_list = article.get("authors", [])
            authors = [str(a.get("name", "")) for a in author_list if a.get("name")]

            # Extract publication date
            pub_date_parts = []
            if article.get("pubdate"):
                pub_date_parts.append(str(article["pubdate"]))
            publication_date = "-".join(pub_date_parts) if pub_date_parts else now_iso()

            # Build URL
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            # Calculate relevance score
            rank_score = max(0.45, round(0.9 - idx * 0.08, 3))

            evidences.append(
                Evidence(
                    id=new_id(),
                    taskId=task_id,
                    nodeId=node_id,
                    sourceType=SourceType.PAPER,
                    url=url,
                    content=title,
                    metadata=EvidenceMetadata(
                        authors=authors,
                        publishDate=publication_date,
                        title=title or "PubMed Article",
                        abstract=title[:500] if title else "",
                        impactFactor=0,
                        isPeerReviewed=True,
                        relevanceScore=rank_score,
                        citationCount=0,
                    ),
                    score=rank_score,
                    extractedData=ExtractedData(),
                )
            )

        return evidences

    async def _retrieve_from_openalex(self, *, task_id: str, node_id: str, query: str) -> list[Evidence]:
        """Search OpenAlex API for scholarly works (free, no API key required).

        OpenAlex API docs: https://docs.openalex.org/
        """
        search_query = self._keyword_query_for_paper_apis(query)

        # Build OpenAlex search URL
        # Use search filter for relevance scoring
        encoded_query = search_query.replace(" ", "%20")
        url = f"https://api.openalex.org/works?search={encoded_query}&per-page=5&sort=relevance_score:desc"

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await retry_async(
                lambda: client.get(url),
                max_attempts=3,
                base_delay_seconds=0.5,
            )
            assert isinstance(resp, httpx.Response)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        evidences: list[Evidence] = []

        for idx, item in enumerate(results[:5]):
            # Extract title
            title = self._normalize_text(str(item.get("display_name") or ""))
            if not title:
                continue

            # Extract abstract (OpenAlex stores abstract as inverted index, use title as fallback)
            abstract = title
            abstract_inverted = item.get("abstract_inverted_index")
            if abstract_inverted and isinstance(abstract_inverted, dict):
                # Reconstruct abstract from inverted index
                word_positions = []
                for word, positions in abstract_inverted.items():
                    for pos in positions:
                        word_positions.append((pos, word))
                if word_positions:
                    word_positions.sort(key=lambda x: x[0])
                    abstract = self._normalize_text(" ".join(word for _, word in word_positions))

            # Extract authors
            authors = []
            authorships = item.get("authorships", [])
            for auth in authorships:
                author_info = auth.get("author", {})
                name = author_info.get("display_name", "")
                if name:
                    authors.append(self._normalize_text(name))

            # Extract publication date
            pub_date = item.get("publication_date", "")
            if pub_date:
                # Ensure ISO format
                if "T" not in pub_date:
                    pub_date = f"{pub_date}T00:00:00Z"
            else:
                pub_date = now_iso()

            # Extract OpenAlex ID as URL
            openalex_id = item.get("id", "")
            if openalex_id:
                url = openalex_id
            else:
                # Fallback to search URL
                url = f"https://openalex.org/works/{item.get('ids', {}).get('doi', '')}"

            # Get DOI if available for better linking
            doi = item.get("doi", "")
            if doi:
                url = doi

            # Extract citation count
            cited_by_count = int(item.get("cited_by_count") or 0)

            # Calculate relevance score with citation bonus
            rank_score = max(0.45, round(0.9 - idx * 0.08, 3))
            if cited_by_count:
                citation_bonus = min(cited_by_count, 500) / 1500
                rank_score = min(0.95, rank_score + citation_bonus)

            # Extract concepts/topics for relevance
            concepts = item.get("concepts", [])
            concept_names = [c.get("display_name", "") for c in concepts[:3]]

            # Determine if peer-reviewed
            is_peer_reviewed = item.get("is_retracted") is False and item.get("type") in ["article", "review", "preprint"]

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
                        publishDate=pub_date,
                        title=title,
                        abstract=(abstract or title)[:500],
                        impactFactor=0,
                        isPeerReviewed=is_peer_reviewed,
                        relevanceScore=rank_score,
                        citationCount=cited_by_count,
                    ),
                    score=rank_score,
                    extractedData=ExtractedData(
                        numericalValues=[
                            {
                                "value": float(cited_by_count),
                                "unit": "citations",
                                "context": "openalex_cited_by_count",
                            }
                        ] if cited_by_count else [],
                    ),
                )
            )

        return evidences

    async def _retrieve_from_google_scholar(self, *, task_id: str, node_id: str, query: str) -> list[Evidence]:
        """Search Google Scholar using SerpAPI or Serper if configured, otherwise return empty."""
        # Prefer SerpAPI if available, then Serper
        if settings.serpapi_api_key:
            return await self._retrieve_from_serpapi(task_id, node_id, query)
        if settings.serper_api_key:
            return await self._retrieve_from_serper(task_id, node_id, query)

        # No Google Scholar API configured
        logger.warning("Google Scholar search requested but no API key configured (SerpAPI or Serper)")
        return []

    async def _retrieve_from_serpapi(self, task_id: str, node_id: str, query: str) -> list[Evidence]:
        """Search using SerpAPI Google Scholar endpoint."""
        params = {
            "api_key": settings.serpapi_api_key,
            "engine": "google_scholar",
            "q": query,
            "num": 5,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await retry_async(
                lambda: client.get(
                    "https://serpapi.com/search",
                    params=params,
                ),
                max_attempts=2,
                base_delay_seconds=1.0,
            )
            assert isinstance(resp, httpx.Response)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("organic_results", [])
        evidences: list[Evidence] = []

        for idx, item in enumerate(results[:5]):
            title = self._normalize_text(str(item.get("title", "")))
            snippet = self._normalize_text(str(item.get("snippet", "")))
            if not title and not snippet:
                continue

            # Extract publication info
            publication_info = item.get("publication_info", {})
            authors = []
            if publication_info.get("authors"):
                for author in publication_info["authors"]:
                    name = author.get("name", "")
                    if name:
                        authors.append(name)

            # Extract year
            summary = publication_info.get("summary", "")
            year_match = re.search(r"\b(19\d{2}|20\d{2})\b", summary)
            year = int(year_match.group(1)) if year_match else None
            publication_date = f"{year}-01-01T00:00:00Z" if year else now_iso()

            # Get URL - prefer PDF link, then result link
            url = ""
            if item.get("resources"):
                for resource in item["resources"]:
                    if resource.get("file_format") == "PDF":
                        url = resource.get("link", "")
                        break
            if not url:
                url = item.get("link", "")
            if not url and item.get("displayed_link"):
                # Extract URL from displayed_link if it's a proper URL
                displayed = item["displayed_link"]
                if displayed.startswith("http"):
                    url = displayed

            if not url:
                url = f"https://scholar.google.com/scholar?q={query.replace(' ', '+')}"

            # Calculate score
            rank_score = max(0.45, round(0.88 - idx * 0.08, 3))
            cited_by = item.get("inline_links", {}).get("cited_by", {}).get("total", 0)
            if cited_by:
                citation_bonus = min(int(cited_by), 500) / 1500
                rank_score = min(0.95, rank_score + citation_bonus)

            evidences.append(
                Evidence(
                    id=new_id(),
                    taskId=task_id,
                    nodeId=node_id,
                    sourceType=SourceType.PAPER,
                    url=url,
                    content=snippet or title,
                    metadata=EvidenceMetadata(
                        authors=authors,
                        publishDate=publication_date,
                        title=title or "Google Scholar Result",
                        abstract=(snippet or title)[:500],
                        impactFactor=0,
                        isPeerReviewed=False,
                        relevanceScore=rank_score,
                        citationCount=int(cited_by) if cited_by else 0,
                    ),
                    score=rank_score,
                    extractedData=ExtractedData(
                        numericalValues=[
                            {
                                "value": int(cited_by) if cited_by else 0,
                                "unit": "citations",
                                "context": "google_scholar_cited_by",
                            }
                        ]
                    ) if cited_by else ExtractedData(),
                )
            )

        return evidences

    async def _retrieve_from_serper(self, task_id: str, node_id: str, query: str) -> list[Evidence]:
        """Search using Serper Google Scholar endpoint."""
        headers = {
            "X-API-KEY": settings.serper_api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "q": query,
            "num": 5,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await retry_async(
                lambda: client.post(
                    "https://google.serper.dev/scholar",
                    headers=headers,
                    json=payload,
                ),
                max_attempts=2,
                base_delay_seconds=1.0,
            )
            assert isinstance(resp, httpx.Response)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("organic", [])
        evidences: list[Evidence] = []

        for idx, item in enumerate(results[:5]):
            title = self._normalize_text(str(item.get("title", "")))
            snippet = self._normalize_text(str(item.get("snippet", "")))
            if not title and not snippet:
                continue

            # Extract authors and year from citation info
            authors = []
            year = None
            publication_info = item.get("publicationInfo", "")
            if publication_info:
                # Parse "Author1, Author2 - Year - Journal" format
                parts = publication_info.split(" - ")
                if len(parts) >= 2:
                    author_part = parts[0]
                    authors = [a.strip() for a in author_part.split(",") if a.strip()]
                    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", parts[1])
                    if year_match:
                        year = int(year_match.group(1))

            publication_date = f"{year}-01-01T00:00:00Z" if year else now_iso()

            # Get URL
            url = item.get("link", "")
            if not url:
                url = f"https://scholar.google.com/scholar?q={query.replace(' ', '+')}"

            # Calculate score
            rank_score = max(0.45, round(0.88 - idx * 0.08, 3))
            cited_by = item.get("citedBy", 0)
            if cited_by:
                citation_bonus = min(int(cited_by), 500) / 1500
                rank_score = min(0.95, rank_score + citation_bonus)

            evidences.append(
                Evidence(
                    id=new_id(),
                    taskId=task_id,
                    nodeId=node_id,
                    sourceType=SourceType.PAPER,
                    url=url,
                    content=snippet or title,
                    metadata=EvidenceMetadata(
                        authors=authors,
                        publishDate=publication_date,
                        title=title or "Google Scholar Result",
                        abstract=(snippet or title)[:500],
                        impactFactor=0,
                        isPeerReviewed=False,
                        relevanceScore=rank_score,
                        citationCount=int(cited_by) if cited_by else 0,
                    ),
                    score=rank_score,
                    extractedData=ExtractedData(
                        numericalValues=[
                            {
                                "value": int(cited_by) if cited_by else 0,
                                "unit": "citations",
                                "context": "google_scholar_cited_by",
                            }
                        ]
                    ) if cited_by else ExtractedData(),
                )
            )

        return evidences

    @classmethod
    def _normalize_source_name(cls, source: str) -> str:
        lowered = source.strip().lower().replace(
            "-", "").replace("_", "").replace(" ", "")
        if lowered in {"arxiv", "arxivorg"}:
            return "arxiv"
        if lowered in {"semanticscholar", "s2"}:
            return "semanticscholar"
        if lowered in {"tavily", "websearch", "web", "tavilysearch"}:
            return "tavily"
        if lowered in {"googlescholar", "scholar", "google"}:
            return "googlescholar"
        if lowered in {"pubmed", "ncbi", "pubmedncbi"}:
            return "pubmed"
        if lowered in {"openalex"}:
            return "openalex"
        return lowered

    @classmethod
    def _is_placeholder_url(cls, url: str) -> bool:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        return hostname in cls._PLACEHOLDER_HOSTS

    @staticmethod
    def _clean_text(content: str) -> str:
        return RetrievalService._normalize_text(content)

    @classmethod
    def _normalize_text(cls, content: str) -> str:
        if not content:
            return ""
        text = html.unescape(content)
        text = cls._UNICODE_ESCAPE_PATTERN.sub(
            lambda match: chr(int(match.group(1), 16)), text)
        text = unicodedata.normalize("NFKC", text)
        text = text.replace("\ufeff", " ").replace("\u200b", " ")
        text = "".join(
            " " if unicodedata.category(ch).startswith(
                "C") and ch not in "\n\t" else ch
            for ch in text
        )
        text = cls._try_fix_mojibake(text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _try_fix_mojibake(text: str) -> str:
        if not text or not any(token in text for token in ("Ã", "â", "å", "æ", "ç", "ä")):
            return text
        try:
            repaired = text.encode("latin1").decode("utf-8")
        except Exception:
            return text
        return repaired if sum(1 for ch in repaired if '\u4e00' <= ch <= '\u9fff') >= sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff') else text

    @staticmethod
    def _read_xml_text(entry, path: str, ns: dict[str, str]) -> str:
        item = entry.find(path, ns)
        return item.text.strip() if item is not None and item.text else ""

    @staticmethod
    def _keyword_query_for_paper_apis(query: str) -> str:
        """Build keyword query for academic paper APIs (arXiv, Semantic Scholar).

        Strategy:
        1. Extract English tokens if present
        2. Extract Chinese characters (Unicode CJK range)
        3. Combine both for mixed queries
        4. Fall back to original query (NEVER return hardcoded irrelevant terms)
        """
        cleaned_query = re.sub(r"[\(\)]", " ", query)

        # Extract ASCII tokens
        ascii_tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-_]{1,}", cleaned_query)
        stop_tokens = {"and", "or", "review", "analyze", "improve", "evaluate"}
        picked_ascii = [
            token for token in ascii_tokens if token.lower() not in stop_tokens]

        # Extract Chinese characters (Unicode CJK range)
        chinese_tokens = re.findall(r"[\u4e00-\u9fff]+", cleaned_query)

        # Combine results
        result_parts = []
        if picked_ascii:
            result_parts.append(" ".join(picked_ascii[:8]))
        if chinese_tokens:
            result_parts.append(" ".join(chinese_tokens[:5]))

        if result_parts:
            return " ".join(result_parts)

        # Last resort: return original query stripped of special chars
        # NEVER return hardcoded irrelevant fallback like "software engineering"
        fallback = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", cleaned_query).strip()
        return fallback if fallback else "research"

    @classmethod
    def _is_garbage_content(cls, content: str, url: str) -> bool:
        """检测垃圾内容。

        检测以下类型的垃圾内容：
        1. 代码仓库文件（diff, patch 等）
        2. 分词器词汇表（+ll +lo +lp...）
        3. 页面导航元素（下载、页数、引文网络等）
        4. 二进制/乱码内容
        5. Excel 等非文本文件
        """
        # 1. 检测特殊文件扩展名
        garbage_extensions = [
            r'\.diff$', r'\.patch$', r'\.xls$', r'\.xlsx$', r'\.csv$',
            r'\.pdf$', r'\.zip$', r'\.tar$', r'\.gz$', r'\.rar$',
            r'\.exe$', r'\.dll$', r'\.so$', r'\.bin$', r'\.dat$',
            r'\.json$', r'\.xml$', r'\.yaml$', r'\.yml$',
        ]
        for pattern in garbage_extensions:
            if re.search(pattern, url, re.IGNORECASE):
                return True

        # 2. 检测分词器 token 格式 (+ll +lo +lp... 或 +不减 +不凡...)
        if re.match(r'^(\+\w+\s*){5,}', content.strip()):
            return True

        # 3. 检测代码仓库 diff 内容
        code_patterns = [
            r'^diff --git',
            r'^@@\s+-\d+,\d+\s+\+\d+,\d+\s+@@',
            r'^index\s+[a-f0-9]{7,}',
            r'^---\s+a/',
            r'^\+\+\+\s+b/',
            r'\+\[unused\d+\]',  # 匹配 +[unused12] 这样的标记
        ]
        for pattern in code_patterns:
            if re.search(pattern, content, re.MULTILINE):
                return True

        # 4. 检测页面导航元素（CNKI 等）
        navigation_keywords = [
            '下载：', '页数：', '大小：', '引文网络', '参考文献',
            '共引文献', '同被引文献', '相关文献推荐', 'CNKI AI阅读',
            '原版阅读', 'HTML阅读', 'CAJ下载', '在线阅读',
            '##### 引文网络', '##### 相关文献',
        ]
        # 如果内容主要由导航元素组成，判定为垃圾
        nav_count = sum(1 for kw in navigation_keywords if kw in content)
        if nav_count >= 3:
            return True

        if any(pattern.search(content) for pattern in cls._MOJIBAKE_PATTERNS):
            return True

        if content.count("{") + content.count("}") >= 4 and content.count('"') >= 6:
            return True

        # 5. 检测二进制/乱码内容（大量非可打印字符）
        if len(content) > 50:
            non_printable = sum(1 for c in content if ord(
                c) > 127 and not ('\u4e00' <= c <= '\u9fff'))
            if non_printable / len(content) > 0.2:
                return True

        # 6. 检测 URL 中包含 commit/diff/blob 等路径
        garbage_url_patterns = [
            r'/commit/[a-f0-9]+\.diff$',
            r'/commit/[a-f0-9]+\.patch$',
            r'/blob/',
            r'/tree/',
            r'/raw/',
            r'download\?etag=',
        ]
        for pattern in garbage_url_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True

        return False

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

            # 检测垃圾内容
            if cls._is_garbage_content(cleaned, ev.url):
                logger.warning(f"过滤垃圾内容: {ev.url[:80]}")
                continue

            ev.content = cleaned
            ev.metadata.title = cls._normalize_text(
                ev.metadata.title) or ev.url
            ev.metadata.abstract = cls._normalize_text(ev.metadata.abstract)
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
