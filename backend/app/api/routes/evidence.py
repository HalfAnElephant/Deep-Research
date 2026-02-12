from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.deps import evidence_repository
from app.models.schemas import Evidence, EvidenceListResponse

router = APIRouter(prefix="/api/v1")


@router.get("/evidence", response_model=EvidenceListResponse)
def list_evidence(
    task_id: str | None = Query(default=None, alias="taskId"),
    node_id: str | None = Query(default=None, alias="nodeId"),
    limit: int = Query(default=100, ge=1, le=500),
) -> EvidenceListResponse:
    return evidence_repository.list(task_id=task_id, node_id=node_id, limit=limit)


@router.get("/evidence/{evidence_id}", response_model=Evidence)
def get_evidence(evidence_id: str) -> Evidence:
    try:
        return evidence_repository.get(evidence_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Evidence not found: {evidence_id}") from exc
