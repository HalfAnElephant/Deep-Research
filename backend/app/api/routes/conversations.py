from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse

from app.deps import conversation_agent, conversation_repository, evidence_repository, task_repository
from app.models.schemas import (
    ConversationBulkDeleteResponse,
    ConversationDeleteResponse,
    ConversationDetail,
    ConversationSummary,
    CreateConversationRequest,
    PlanRevision,
    RevisePlanRequest,
    RevisePlanResponse,
    RunConversationRequest,
    RunConversationResponse,
    UpdateConversationRequest,
    UpdatePlanRequest,
)
from app.services.export_service import export_service

router = APIRouter(prefix="/api/v1")


@router.post("/conversations", response_model=ConversationDetail, status_code=201)
async def create_conversation(payload: CreateConversationRequest) -> ConversationDetail:
    return await conversation_agent.create_conversation(topic=payload.topic, config=payload.config)


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations() -> list[ConversationSummary]:
    return conversation_repository.list_summaries()


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str) -> ConversationDetail:
    try:
        return conversation_repository.get_detail(conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}") from exc


@router.delete("/conversations/{conversation_id}", response_model=ConversationDeleteResponse)
def delete_conversation(conversation_id: str) -> ConversationDeleteResponse:
    try:
        conversation_agent.delete_conversation(conversation_id=conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}") from exc
    return ConversationDeleteResponse(conversationId=conversation_id, deleted=True)


@router.delete("/conversations", response_model=ConversationBulkDeleteResponse)
def delete_all_conversations() -> ConversationBulkDeleteResponse:
    deleted_count = conversation_agent.delete_all_conversations()
    return ConversationBulkDeleteResponse(deleted=True, deletedCount=deleted_count)


@router.patch("/conversations/{conversation_id}", response_model=ConversationDetail)
def rename_conversation(conversation_id: str, payload: UpdateConversationRequest) -> ConversationDetail:
    try:
        return conversation_agent.rename_conversation(
            conversation_id=conversation_id,
            topic=payload.topic,
            sync_current_plan=payload.syncCurrentPlan,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/conversations/{conversation_id}/plan/revise", response_model=RevisePlanResponse)
async def revise_plan(conversation_id: str, payload: RevisePlanRequest) -> RevisePlanResponse:
    try:
        plan, message = await conversation_agent.revise_plan(
            conversation_id=conversation_id,
            instruction=payload.instruction,
        )
        return RevisePlanResponse(plan=plan, message=message)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/conversations/{conversation_id}/plan", response_model=PlanRevision)
def update_plan(conversation_id: str, payload: UpdatePlanRequest) -> PlanRevision:
    try:
        return conversation_agent.update_plan(conversation_id=conversation_id, markdown=payload.markdown)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/conversations/{conversation_id}/run", response_model=RunConversationResponse)
async def run_conversation(conversation_id: str, payload: RunConversationRequest) -> RunConversationResponse:
    _ = payload
    try:
        return await conversation_agent.start_research(conversation_id=conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/conversations/{conversation_id}/report/download")
def download_conversation_report(conversation_id: str) -> FileResponse:
    try:
        summary = conversation_repository.get_summary(conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}") from exc
    if not summary.taskId:
        raise HTTPException(status_code=404, detail="Conversation has no task yet")
    try:
        task = task_repository.get_task(summary.taskId)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Task not found: {summary.taskId}") from exc
    if not task.reportPath:
        raise HTTPException(status_code=404, detail="Report not generated yet")
    path = Path(task.reportPath)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report file does not exist")
    return FileResponse(path, media_type="text/markdown", filename=f"{conversation_id}.md")


@router.get("/conversations/{conversation_id}/export/article")
def export_article(conversation_id: str) -> FileResponse:
    """导出文章文件（纯内容，引用在文末）。"""
    try:
        summary = conversation_repository.get_summary(conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}") from exc
    if not summary.taskId:
        raise HTTPException(status_code=404, detail="Conversation has no task yet")

    task_id = summary.taskId
    article_path = Path(f"backend/.data/reports/{task_id}_article.md")
    if not article_path.exists():
        # 回退到旧的报告文件
        legacy_path = Path(f"backend/.data/reports/{task_id}.md")
        if not legacy_path.exists():
            raise HTTPException(status_code=404, detail="Article file not generated yet")
        article_path = legacy_path

    return FileResponse(
        article_path,
        media_type="text/markdown",
        filename=f"{conversation_id}_article.md"
    )


@router.get("/conversations/{conversation_id}/export/references")
def export_references(conversation_id: str) -> FileResponse:
    """导出引用列表文件（包含评分和说明）。"""
    try:
        summary = conversation_repository.get_summary(conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}") from exc
    if not summary.taskId:
        raise HTTPException(status_code=404, detail="Conversation has no task yet")

    task_id = summary.taskId
    references_path = Path(f"backend/.data/reports/{task_id}_references.md")
    if not references_path.exists():
        raise HTTPException(status_code=404, detail="References file not generated yet")

    return FileResponse(
        references_path,
        media_type="text/markdown",
        filename=f"{conversation_id}_references.md"
    )


@router.get("/conversations/{conversation_id}/export/ris")
def export_ris(conversation_id: str) -> PlainTextResponse:
    """导出 RIS 格式的引用文件。"""
    try:
        summary = conversation_repository.get_summary(conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}") from exc
    if not summary.taskId:
        raise HTTPException(status_code=404, detail="Conversation has no task yet")

    # Get all evidence for this task
    evidences = evidence_repository.list(task_id=summary.taskId, limit=500).items

    if not evidences:
        raise HTTPException(status_code=404, detail="No evidence found for this conversation")

    # Generate RIS content
    ris_content = export_service.generate_ris(evidences)

    return PlainTextResponse(
        content=ris_content,
        media_type="application/x-research-info-systems",
        headers={"Content-Disposition": f'attachment; filename="{conversation_id}.ris"'}
    )


@router.get("/conversations/{conversation_id}/export/bibtex")
def export_bibtex(conversation_id: str) -> PlainTextResponse:
    """导出 BibTeX 格式的引用文件。"""
    try:
        summary = conversation_repository.get_summary(conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}") from exc
    if not summary.taskId:
        raise HTTPException(status_code=404, detail="Conversation has no task yet")

    # Get all evidence for this task
    evidences = evidence_repository.list(task_id=summary.taskId, limit=500).items

    if not evidences:
        raise HTTPException(status_code=404, detail="No evidence found for this conversation")

    # Generate BibTeX content
    bibtex_content = export_service.generate_bibtex(evidences)

    return PlainTextResponse(
        content=bibtex_content,
        media_type="application/x-bibtex",
        headers={"Content-Disposition": f'attachment; filename="{conversation_id}.bib"'}
    )


@router.get("/library/export/ris")
def export_library_ris(
    favorited_only: bool = Query(default=False, alias="favoritedOnly")
) -> PlainTextResponse:
    """导出文献库为 RIS 格式。

    Args:
        favorited_only: 仅导出收藏的文献
    """
    from app.services.library_service import library_service

    # Get library items
    result = library_service.get_library_items(
        page=1,
        page_size=500,
        favorited_only=favorited_only,
        sort_by="created_at",
        sort_order="desc"
    )

    if not result["items"]:
        raise HTTPException(status_code=404, detail="No evidence found in library")

    # Convert dict items back to Evidence-like objects for the export service
    from app.models.schemas import Evidence, EvidenceMetadata, ExtractedData, SourceType

    evidences = []
    for item in result["items"]:
        evidence = Evidence(
            id=item["id"],
            taskId=item["taskId"],
            nodeId=item["nodeId"],
            sourceType=SourceType(item["sourceType"]),
            url=item["url"],
            content=item["content"],
            metadata=EvidenceMetadata(**item["metadata"]),
            score=item["score"],
            extractedData=ExtractedData(**item["extractedData"]),
            favorited=item["favorited"]
        )
        evidences.append(evidence)

    # Generate RIS content
    ris_content = export_service.generate_ris(evidences)

    filename = "library_favorited.ris" if favorited_only else "library.ris"

    return PlainTextResponse(
        content=ris_content,
        media_type="application/x-research-info-systems",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
