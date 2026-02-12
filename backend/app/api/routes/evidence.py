from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.deps import conflict_repository, evidence_repository
from app.models.schemas import Evidence, EvidenceListResponse, VoteRequest, VoteResponse

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


@router.post("/evidence/{evidence_id}/vote", response_model=VoteResponse)
def vote_conflict(evidence_id: str, payload: VoteRequest) -> VoteResponse:
    try:
        evidence_repository.get(evidence_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Evidence not found: {evidence_id}") from exc
    try:
        resolved = conflict_repository.resolve(payload.conflictId, payload.selectedEvidenceId, payload.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Conflict not found: {payload.conflictId}") from exc
    return VoteResponse(
        conflictId=resolved.conflictId,
        resolutionStatus=resolved.resolutionStatus,
        selectedEvidenceId=payload.selectedEvidenceId,
    )
