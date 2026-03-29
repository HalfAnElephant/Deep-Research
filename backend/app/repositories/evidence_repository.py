from __future__ import annotations

import json

from app.core.database import get_connection
from app.core.utils import now_iso
from app.models.schemas import Evidence, EvidenceListResponse, EvidenceMetadata, ExtractedData, SourceType


class EvidenceRepository:
    def save_many(self, evidences: list[Evidence]) -> None:
        with get_connection() as conn:
            for item in evidences:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO evidences(
                      evidence_id, task_id, node_id, source_type, url, content, metadata_json,
                      score, extracted_data_json, favorited, created_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.id,
                        item.taskId,
                        item.nodeId,
                        item.sourceType.value,
                        item.url,
                        item.content,
                        item.metadata.model_dump_json(),
                        item.score,
                        item.extractedData.model_dump_json(),
                        1 if item.favorited else 0,
                        now_iso(),
                    ),
                )
            conn.commit()

    def get(self, evidence_id: str) -> Evidence:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM evidences WHERE evidence_id = ?", (evidence_id,)).fetchone()
        if row is None:
            raise KeyError(evidence_id)
        return self._row_to_evidence(row)

    def list(self, *, task_id: str | None = None, node_id: str | None = None, limit: int = 100) -> EvidenceListResponse:
        query = "SELECT * FROM evidences"
        clauses: list[str] = []
        params: list[str | int] = []
        if task_id:
            clauses.append("task_id = ?")
            params.append(task_id)
        if node_id:
            clauses.append("node_id = ?")
            params.append(node_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
        items = [self._row_to_evidence(row) for row in rows]
        return EvidenceListResponse(items=items, total=len(items))

    def list_paginated(
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
    ) -> EvidenceListResponse:
        """List evidences with pagination and filtering."""
        # Build count query
        count_query = "SELECT COUNT(*) FROM evidences"
        count_clauses: list[str] = []
        count_params: list = []

        if source_type:
            count_clauses.append("source_type = ?")
            count_params.append(source_type)
        if search_query:
            count_clauses.append("(content LIKE ? OR url LIKE ?)")
            search_pattern = f"%{search_query}%"
            count_params.extend([search_pattern, search_pattern])
        if date_from:
            count_clauses.append("created_at >= ?")
            count_params.append(date_from)
        if date_to:
            count_clauses.append("created_at <= ?")
            count_params.append(date_to)
        if min_score is not None:
            count_clauses.append("score >= ?")
            count_params.append(min_score)
        if favorited_only:
            count_clauses.append("favorited = 1")

        if count_clauses:
            count_query += " WHERE " + " AND ".join(count_clauses)

        with get_connection() as conn:
            total = conn.execute(count_query, count_params).fetchone()[0]

        # Build data query
        query = "SELECT * FROM evidences"
        params = count_params.copy()

        if count_clauses:
            query += " WHERE " + " AND ".join(count_clauses)

        # Sorting
        allowed_sort_columns = {"created_at", "score", "source_type"}
        if sort_by not in allowed_sort_columns:
            sort_by = "created_at"
        order = "DESC" if sort_order.lower() == "desc" else "ASC"
        query += f" ORDER BY {sort_by} {order}"

        # Pagination
        offset = (page - 1) * page_size
        query += " LIMIT ? OFFSET ?"
        params.extend([page_size, offset])

        with get_connection() as conn:
            rows = conn.execute(query, params).fetchall()

        items = [self._row_to_evidence(row) for row in rows]
        return EvidenceListResponse(items=items, total=total)

    def toggle_favorite(self, evidence_id: str) -> Evidence:
        """Toggle favorite status for an evidence."""
        with get_connection() as conn:
            # Get current status
            row = conn.execute(
                "SELECT favorited FROM evidences WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
            if row is None:
                raise KeyError(evidence_id)

            new_status = 0 if row[0] else 1
            conn.execute(
                "UPDATE evidences SET favorited = ? WHERE evidence_id = ?",
                (new_status, evidence_id)
            )
            conn.commit()

            # Return updated evidence
            row = conn.execute("SELECT * FROM evidences WHERE evidence_id = ?", (evidence_id,)).fetchone()
            return self._row_to_evidence(row)

    def get_library_stats(self) -> dict:
        """Get library statistics for analytics."""
        with get_connection() as conn:
            # Total count
            total = conn.execute("SELECT COUNT(*) FROM evidences").fetchone()[0]
            favorited = conn.execute("SELECT COUNT(*) FROM evidences WHERE favorited = 1").fetchone()[0]

            # Source distribution
            source_rows = conn.execute(
                "SELECT source_type, COUNT(*) FROM evidences GROUP BY source_type"
            ).fetchall()
            source_distribution = {row[0]: row[1] for row in source_rows}

            # Date distribution (by month)
            date_rows = conn.execute(
                "SELECT strftime('%Y-%m', created_at) as month, COUNT(*) FROM evidences GROUP BY month ORDER BY month"
            ).fetchall()
            date_distribution = {row[0]: row[1] for row in date_rows}

            # Score distribution
            score_rows = conn.execute(
                "SELECT CASE WHEN score >= 0.8 THEN 'high' WHEN score >= 0.5 THEN 'medium' ELSE 'low' END as tier, COUNT(*) FROM evidences GROUP BY tier"
            ).fetchall()
            score_distribution = {row[0]: row[1] for row in score_rows}

        return {
            "total": total,
            "favorited": favorited,
            "sourceDistribution": source_distribution,
            "dateDistribution": date_distribution,
            "scoreDistribution": score_distribution,
        }

    @staticmethod
    def _row_to_evidence(row) -> Evidence:
        # Handle favorited column - sqlite3.Row doesn't have .get() method
        favorited = False
        try:
            favorited = bool(row["favorited"])
        except (KeyError, IndexError):
            pass

        return Evidence(
            id=row["evidence_id"],
            taskId=row["task_id"],
            nodeId=row["node_id"],
            sourceType=SourceType(row["source_type"]),
            url=row["url"],
            content=row["content"],
            metadata=EvidenceMetadata.model_validate_json(row["metadata_json"]),
            score=float(row["score"]),
            extractedData=ExtractedData.model_validate(json.loads(row["extracted_data_json"])),
            favorited=favorited,
        )
