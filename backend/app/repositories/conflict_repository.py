from __future__ import annotations

import json

from app.core.database import get_connection
from app.core.utils import now_iso
from app.models.schemas import ConflictRecord, ResolutionStatus


class ConflictRepository:
    def save_many(self, conflicts: list[ConflictRecord]) -> None:
        with get_connection() as conn:
            for item in conflicts:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO conflicts(
                      conflict_id, task_id, parameter, disputed_values_json, variance, context,
                      resolution_status, resolution_json, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.conflictId,
                        item.taskId,
                        item.parameter,
                        json.dumps([v.model_dump() for v in item.disputedValues]),
                        item.variance,
                        item.context,
                        item.resolutionStatus.value,
                        item.resolution.model_dump_json() if item.resolution else None,
                        now_iso(),
                        now_iso(),
                    ),
                )
            conn.commit()

    def get(self, conflict_id: str) -> ConflictRecord:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM conflicts WHERE conflict_id = ?", (conflict_id,)).fetchone()
        if row is None:
            raise KeyError(conflict_id)
        return ConflictRecord.model_validate(
            {
                "conflictId": row["conflict_id"],
                "taskId": row["task_id"],
                "parameter": row["parameter"],
                "disputedValues": json.loads(row["disputed_values_json"]),
                "variance": row["variance"],
                "context": row["context"],
                "resolutionStatus": row["resolution_status"],
                "resolution": json.loads(row["resolution_json"]) if row["resolution_json"] else None,
            }
        )

    def list_by_task(self, task_id: str) -> list[ConflictRecord]:
        with get_connection() as conn:
            rows = conn.execute("SELECT conflict_id FROM conflicts WHERE task_id = ?", (task_id,)).fetchall()
        return [self.get(r["conflict_id"]) for r in rows]

    def resolve(self, conflict_id: str, selected_evidence_id: str, reason: str) -> ConflictRecord:
        self.get(conflict_id)
        resolution = {
            "selectedEvidenceId": selected_evidence_id,
            "reason": reason,
            "resolvedAt": now_iso(),
        }
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE conflicts
                SET resolution_status = ?, resolution_json = ?, updated_at = ?
                WHERE conflict_id = ?
                """,
                (ResolutionStatus.RESOLVED.value, json.dumps(resolution), now_iso(), conflict_id),
            )
            conn.commit()
        return self.get(conflict_id)
