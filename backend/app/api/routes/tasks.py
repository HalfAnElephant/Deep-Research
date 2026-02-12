from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.core.utils import new_id
from app.deps import execution_engine, progress_hub, task_repository
from app.models.schemas import CreateTaskRequest, DeleteResponse, StateResponse, TaskResponse, TaskStatus, UpdateTaskRequest

router = APIRouter(prefix="/api/v1")


@router.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(payload: CreateTaskRequest) -> TaskResponse:
    task_id = new_id()
    return task_repository.create_task(task_id, payload.title, payload.description, payload.config)


@router.get("/tasks", response_model=list[TaskResponse])
def list_tasks() -> list[TaskResponse]:
    return task_repository.list_tasks()


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str) -> TaskResponse:
    try:
        return task_repository.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}") from exc


@router.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: str, payload: UpdateTaskRequest) -> TaskResponse:
    try:
        return task_repository.update_task(
            task_id,
            title=payload.title,
            description=payload.description,
            config=payload.config,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}") from exc


@router.delete("/tasks/{task_id}", response_model=DeleteResponse)
def delete_task(task_id: str) -> DeleteResponse:
    try:
        task_repository.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}") from exc
    task_repository.delete_task(task_id)
    return DeleteResponse(taskId=task_id, deleted=True)


@router.get("/tasks/{task_id}/dag")
def get_task_dag(task_id: str) -> dict:
    try:
        return task_repository.get_dag(task_id, allow_empty=True).model_dump(by_alias=True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}") from exc


@router.post("/tasks/{task_id}/start", response_model=StateResponse)
async def start_task(task_id: str) -> StateResponse:
    try:
        task = task_repository.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}") from exc
    if task.status in {TaskStatus.COMPLETED, TaskStatus.ABORTED}:
        raise HTTPException(status_code=400, detail=f"Task is in terminal state: {task.status.value}")
    await execution_engine.start(task_id)
    return StateResponse(taskId=task_id, status=TaskStatus.EXECUTING, message="Task execution started")


@router.post("/tasks/{task_id}/pause", response_model=StateResponse)
def pause_task(task_id: str) -> StateResponse:
    try:
        task_repository.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}") from exc
    execution_engine.pause(task_id)
    return StateResponse(taskId=task_id, status=TaskStatus.SUSPENDED, message="Task paused")


@router.post("/tasks/{task_id}/resume", response_model=StateResponse)
async def resume_task(task_id: str) -> StateResponse:
    try:
        task = task_repository.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}") from exc
    if task.status not in {TaskStatus.SUSPENDED, TaskStatus.REVIEWING, TaskStatus.READY}:
        raise HTTPException(status_code=400, detail=f"Task status does not support resume: {task.status.value}")
    await execution_engine.resume(task_id)
    return StateResponse(taskId=task_id, status=TaskStatus.EXECUTING, message="Task resumed")


@router.post("/tasks/{task_id}/abort", response_model=StateResponse)
def abort_task(task_id: str) -> StateResponse:
    try:
        task_repository.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}") from exc
    execution_engine.abort(task_id)
    return StateResponse(taskId=task_id, status=TaskStatus.ABORTED, message="Task aborted")


@router.websocket("/ws/task/{task_id}/progress")
async def task_progress(task_id: str, websocket: WebSocket) -> None:
    await progress_hub.connect(task_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await progress_hub.disconnect(task_id, websocket)
