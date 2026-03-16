from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.deps import conflict_repository, evidence_repository
from app.models.schemas import Evidence, EvidenceListResponse, VoteRequest, VoteResponse
from app.services.library_service import LibraryService

router = APIRouter(prefix="/api/v1")
library_service = LibraryService()


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


# Library endpoints
@router.get("/library")
def get_library_items(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    source_type: str | None = Query(default=None, alias="sourceType"),
    search: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="dateFrom"),
    date_to: str | None = Query(default=None, alias="dateTo"),
    min_score: float | None = Query(default=None, ge=0, le=1, alias="minScore"),
    favorited_only: bool = Query(default=False, alias="favoritedOnly"),
    sort_by: str = Query(default="created_at", alias="sortBy"),
    sort_order: str = Query(default="desc", alias="sortOrder"),
) -> dict:
    """Get paginated library items with filtering and sorting."""
    return library_service.get_library_items(
        page=page,
        page_size=page_size,
        source_type=source_type,
        search_query=search,
        date_from=date_from,
        date_to=date_to,
        min_score=min_score,
        favorited_only=favorited_only,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("/library/{evidence_id}/favorite")
def toggle_favorite(evidence_id: str) -> dict:
    """Toggle favorite status for an evidence item."""
    try:
        return library_service.toggle_favorite(evidence_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Evidence not found: {evidence_id}") from exc


@router.get("/library/trends")
def get_library_trends(
    days: int = Query(default=90, ge=7, le=365),
) -> dict:
    """Get trend analysis for library items."""
    return library_service.get_trend_analysis(days=days)


@router.get("/library/keywords")
def get_library_keywords(
    top_n: int = Query(default=50, ge=10, le=100),
) -> dict:
    """Get keyword analysis from library content."""
    return library_service.get_keyword_analysis(top_n=top_n)


@router.get("/library/summary")
def get_library_summary() -> dict:
    """Get a summary overview of the library."""
    return library_service.get_library_summary()
