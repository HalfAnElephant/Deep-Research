from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.deps import conversation_agent, conversation_repository, task_repository
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
