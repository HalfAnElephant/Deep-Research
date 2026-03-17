"""DAG schema definitions for API requests and responses."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.schemas import DAGEdge, TaskNode


class DAGUpdateRequest(BaseModel):
    """Request model for updating a DAG."""

    nodes: list[TaskNode]
    edges: list[DAGEdge]


class DAGValidationResponse(BaseModel):
    """Response model for DAG validation and update."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    executionOrder: Optional[list[str]] = None