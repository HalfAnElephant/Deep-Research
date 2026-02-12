from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    READY = "READY"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    REVIEWING = "REVIEWING"
    SYNTHESIZING = "SYNTHESIZING"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SUSPENDED = "SUSPENDED"
    ABORTED = "ABORTED"


class NodeStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SUSPENDED = "SUSPENDED"
    PRUNED = "PRUNED"


class TaskConfig(BaseModel):
    maxDepth: int = Field(default=3, ge=1, le=8)
    maxNodes: int = Field(default=50, ge=1, le=500)
    searchSources: list[str] = Field(default_factory=lambda: ["arXiv", "Semantic Scholar"])
    priority: int = Field(default=3, ge=1, le=5)


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=5000)
    config: TaskConfig = Field(default_factory=TaskConfig)


class UpdateTaskRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=3, max_length=5000)
    config: TaskConfig | None = None


class TaskMetadata(BaseModel):
    estimatedTokenCost: int = 0
    searchDepth: int = 0
    infoGainScore: float = 0.0
    createdAt: str
    updatedAt: str


class TaskNode(BaseModel):
    taskId: str
    parentTaskId: str | None
    title: str
    description: str
    status: NodeStatus
    priority: int
    dependencies: list[str] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)
    metadata: TaskMetadata
    output: list[dict[str, Any]] = Field(default_factory=list)


class DAGEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    type: str = "DEPENDS_ON"


class DAGGraph(BaseModel):
    nodes: list[TaskNode]
    edges: list[DAGEdge]


class TaskResponse(BaseModel):
    taskId: str
    title: str
    description: str
    status: TaskStatus
    createdAt: str
    updatedAt: str
    config: TaskConfig
    dag: DAGGraph | None = None


class StateResponse(BaseModel):
    taskId: str
    status: TaskStatus
    message: str


class DeleteResponse(BaseModel):
    taskId: str
    deleted: bool


class ProgressEvent(BaseModel):
    event: str
    timestamp: str
    data: dict[str, Any]
