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
                      score, extracted_data_json, created_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    @staticmethod
    def _row_to_evidence(row) -> Evidence:
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
        )
