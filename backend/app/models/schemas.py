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


class ConversationStatus(StrEnum):
    DRAFTING_PLAN = "DRAFTING_PLAN"
    PLAN_READY = "PLAN_READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class NodeStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SUSPENDED = "SUSPENDED"
    PRUNED = "PRUNED"


class AgentType(StrEnum):
    """四 Agent 架构的智能体类型。"""
    IDEATION = "IDEATION"      # 构思智能体
    PLANNING = "PLANNING"      # 规划智能体
    WRITING = "WRITING"        # 写作智能体
    CHECKING = "CHECKING"      # 检查智能体


class AgentStatus(StrEnum):
    """智能体执行状态。"""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    WAITING_INPUT = "WAITING_INPUT"


class TaskConfig(BaseModel):
    maxDepth: int = Field(default=3, ge=1, le=8)
    maxNodes: int = Field(default=50, ge=1, le=500)
    searchSources: list[str] = Field(
        default_factory=lambda: ["Web Search", "arXiv", "Semantic Scholar"]
    )
    priority: int = Field(default=3, ge=1, le=5)
    targetWordCount: int = Field(default=5000, ge=1000, le=50000)


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=5000)
    config: TaskConfig = Field(default_factory=TaskConfig)


class UpdateTaskRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(
        default=None, min_length=3, max_length=5000)
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
    reportPath: str | None = None
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


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageKind(StrEnum):
    USER_TEXT = "USER_TEXT"
    PLAN_DRAFT = "PLAN_DRAFT"
    PLAN_EDITED = "PLAN_EDITED"
    PLAN_REVISION = "PLAN_REVISION"
    PROGRESS_GROUP = "PROGRESS_GROUP"
    FINAL_REPORT = "FINAL_REPORT"
    ERROR = "ERROR"


class PlanRevision(BaseModel):
    conversationId: str
    version: int
    author: MessageRole
    markdown: str
    createdAt: str


class ConversationMessage(BaseModel):
    messageId: str
    conversationId: str
    role: MessageRole
    kind: MessageKind
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    collapsed: bool = False
    createdAt: str


class ConversationSummary(BaseModel):
    conversationId: str
    topic: str
    status: ConversationStatus
    taskId: str | None = None
    createdAt: str
    updatedAt: str


class AgentStateRecord(BaseModel):
    """智能体状态记录。"""
    agentType: AgentType
    status: AgentStatus
    startedAt: str | None = None
    completedAt: str | None = None
    progress: int = Field(default=0, ge=0, le=100)
    currentActivity: str = ""
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ResearchHypothesis(BaseModel):
    """研究假设模型。"""
    hypothesisId: str
    title: str
    description: str
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    createdAt: str


class ResearchPlan(BaseModel):
    """研究计划模型。"""
    planId: str
    hypothesisId: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    createdAt: str


class ConversationDetail(ConversationSummary):
    currentPlan: PlanRevision | None = None
    messages: list[ConversationMessage] = Field(default_factory=list)
    agentStates: list[AgentStateRecord] = Field(default_factory=list)
    currentHypothesis: ResearchHypothesis | None = None


class CreateConversationRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=500)
    config: TaskConfig | None = None


class UpdateConversationRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=500)
    syncCurrentPlan: bool = True


class RevisePlanRequest(BaseModel):
    instruction: str = Field(min_length=2, max_length=4000)


class UpdatePlanRequest(BaseModel):
    markdown: str = Field(min_length=10, max_length=60000)


class RunConversationRequest(BaseModel):
    pass


class RevisePlanResponse(BaseModel):
    plan: PlanRevision
    message: ConversationMessage


class RunConversationResponse(BaseModel):
    conversationId: str
    taskId: str
    status: ConversationStatus


class ConversationDeleteResponse(BaseModel):
    conversationId: str
    deleted: bool


class ConversationBulkDeleteResponse(BaseModel):
    deleted: bool
    deletedCount: int


class SourceType(StrEnum):
    PAPER = "PAPER"
    WEB = "WEB"
    PATENT = "PATENT"
    MCP = "MCP"


class EvidenceMetadata(BaseModel):
    authors: list[str] = Field(default_factory=list)
    publishDate: str = ""
    title: str
    abstract: str = ""
    impactFactor: float = 0.0
    isPeerReviewed: bool = False
    relevanceScore: float = Field(default=0.0, ge=0, le=1)
    citationCount: int = 0


class ExtractedData(BaseModel):
    tables: list[dict[str, Any]] = Field(default_factory=list)
    images: list[dict[str, Any]] = Field(default_factory=list)
    numericalValues: list[dict[str, Any]] = Field(default_factory=list)


class Evidence(BaseModel):
    id: str
    taskId: str
    nodeId: str
    sourceType: SourceType
    url: str
    content: str
    metadata: EvidenceMetadata
    score: float = Field(ge=0, le=1)
    extractedData: ExtractedData = Field(default_factory=ExtractedData)


class EvidenceListResponse(BaseModel):
    items: list[Evidence]
    total: int


class ResolutionStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


class ConflictResolution(BaseModel):
    selectedEvidenceId: str
    reason: str
    resolvedAt: str


class DisputedValue(BaseModel):
    value: float
    unit: str
    evidenceId: str
    source: str


class ConflictRecord(BaseModel):
    conflictId: str
    taskId: str
    parameter: str
    disputedValues: list[DisputedValue]
    variance: float
    context: str
    resolutionStatus: ResolutionStatus
    resolution: ConflictResolution | None = None


class VoteRequest(BaseModel):
    conflictId: str
    selectedEvidenceId: str
    reason: str = Field(min_length=3, max_length=500)


class VoteResponse(BaseModel):
    conflictId: str
    resolutionStatus: ResolutionStatus
    selectedEvidenceId: str


class Citation(BaseModel):
    id: str
    authors: list[str]
    title: str
    year: int
    source: str
    url: str


class WritingSectionPlan(BaseModel):
    sectionId: str
    heading: str = Field(min_length=1, max_length=120)
    brief: str = Field(min_length=1, max_length=2000)
    sourceNodeIds: list[str] = Field(default_factory=list)
    priority: int = Field(default=1, ge=1, le=10)
    requiredEvidenceCount: int = Field(default=2, ge=0, le=6)
    rewritePolicy: str = Field(default="section", pattern="^(section|global)$")


class SectionDraft(BaseModel):
    sectionId: str
    heading: str
    body: str = ""
    usedEvidenceIds: list[str] = Field(default_factory=list)
    status: str = Field(
        default="pending", pattern="^(pending|generated|rewritten|reused|failed)$")
    attempts: int = Field(default=0, ge=0, le=10)
    issues: list[str] = Field(default_factory=list)


class ReportDraft(BaseModel):
    body: str = ""
    sections: list[SectionDraft] = Field(default_factory=list)
    status: str = Field(default="empty", pattern="^(empty|partial|complete)$")
    issues: list[str] = Field(default_factory=list)
    suppressedSegments: list[str] = Field(default_factory=list)


class MCPExecutionRequest(BaseModel):
    toolName: str
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    mode: str = Field(default="read", pattern="^(read|write|execute)$")


class MCPExecutionResult(BaseModel):
    status: str
    result: dict[str, Any] | None = None
    jobId: str | None = None
    error: str | None = None
