from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from app.repositories.evidence_repository import EvidenceRepository


class LibraryService:
    def __init__(self, repository: EvidenceRepository | None = None) -> None:
        self.repository = repository or EvidenceRepository()

    def get_library_items(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        source_type: str | None = None,
        search_query: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        min_score: float | None = None,
        favorited_only: bool = False,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        """Get paginated library items with filtering."""
        result = self.repository.list_paginated(
            page=page,
            page_size=page_size,
            source_type=source_type,
            search_query=search_query,
            date_from=date_from,
            date_to=date_to,
            min_score=min_score,
            favorited_only=favorited_only,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        return {
            "items": [item.model_dump() for item in result.items],
            "total": result.total,
            "page": page,
            "page_size": page_size,
            "total_pages": (result.total + page_size - 1) // page_size,
        }

    def toggle_favorite(self, evidence_id: str) -> dict[str, Any]:
        """Toggle favorite status for an evidence item."""
        evidence = self.repository.toggle_favorite(evidence_id)
        return evidence.model_dump()

    def get_trend_analysis(self, days: int = 90) -> dict[str, Any]:
        """Get trend analysis for library items."""
        stats = self.repository.get_library_stats()

        # Calculate date range
        end_date = datetime.now(tz=UTC)
        start_date = end_date - timedelta(days=days)

        # Filter date distribution to the range
        date_dist = stats.get("dateDistribution", {})
        filtered_dates = {
            k: v for k, v in date_dist.items()
            if start_date.strftime("%Y-%m") <= k <= end_date.strftime("%Y-%m")
        }

        # Generate time series data
        time_series = []
        current = start_date
        while current <= end_date:
            month_key = current.strftime("%Y-%m")
            time_series.append({
                "date": month_key,
                "count": filtered_dates.get(month_key, 0),
            })
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        return {
            "timeRange": {"from": start_date.isoformat(), "to": end_date.isoformat()},
            "timeSeries": time_series,
            "sourceDistribution": stats.get("sourceDistribution", {}),
            "scoreDistribution": stats.get("scoreDistribution", {}),
            "totalItems": stats.get("total", 0),
            "favoritedItems": stats.get("favorited", 0),
        }

    def get_keyword_analysis(self, top_n: int = 50) -> dict[str, Any]:
        """Extract and analyze keywords from library content."""
        # Get all evidences (limit to recent 500 for performance)
        result = self.repository.list_paginated(page=1, page_size=500)

        # Extract keywords from titles and abstracts
        all_text = []
        for evidence in result.items:
            title = evidence.metadata.title or ""
            abstract = evidence.metadata.abstract or ""
            all_text.append(f"{title} {abstract}")

        full_text = " ".join(all_text).lower()

        # Common academic/stop words to exclude
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
            "been", "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "this", "that",
            "these", "those", "we", "you", "they", "it", "he", "she", "i", "me",
            "my", "our", "your", "their", "its", "his", "her", "study", "paper",
            "research", "analysis", "data", "method", "results", "conclusion",
            "using", "used", "based", "shown", "show", "found", "proposed",
            "approach", "system", "model", "algorithm", "technique", "et", "al",
        }

        # Extract words (2+ characters, alphanumeric)
        words = re.findall(r'\b[a-z][a-z0-9]+\b', full_text)
        word_counts = Counter(w for w in words if w not in stop_words and len(w) > 2)

        # Get top keywords
        top_keywords = [
            {"word": word, "count": count}
            for word, count in word_counts.most_common(top_n)
        ]

        # Extract bigrams (two-word phrases)
        bigrams = []
        for text in all_text:
            tokens = re.findall(r'\b[a-z][a-z0-9]+\b', text.lower())
            tokens = [t for t in tokens if t not in stop_words and len(t) > 2]
            for i in range(len(tokens) - 1):
                bigrams.append(f"{tokens[i]} {tokens[i+1]}")

        bigram_counts = Counter(bigrams)
        top_bigrams = [
            {"phrase": phrase, "count": count}
            for phrase, count in bigram_counts.most_common(top_n // 2)
        ]

        return {
            "totalDocuments": result.total,
            "analyzedDocuments": len(result.items),
            "topKeywords": top_keywords,
            "topPhrases": top_bigrams,
            "vocabularySize": len(word_counts),
        }

    def get_library_summary(self) -> dict[str, Any]:
        """Get a summary overview of the library."""
        stats = self.repository.get_library_stats()

        return {
            "totalEvidences": stats.get("total", 0),
            "favoritedEvidences": stats.get("favorited", 0),
            "sourceDistribution": stats.get("sourceDistribution", {}),
            "scoreDistribution": stats.get("scoreDistribution", {}),
            "lastUpdated": datetime.now(tz=UTC).isoformat(),
        }
