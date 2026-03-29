from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


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


class LLMProvider(StrEnum):
    OPENROUTER = "openrouter"
    DEEPSEEK = "deepseek"
    OPENAI = "openai"


class ResearchMode(StrEnum):
    SURVEY = "survey"
    EVIDENCE_REPORT = "evidence_report"
    EXPERIMENTAL_RESEARCH = "experimental_research"
    PAPER_WRITEUP = "paper_writeup"


class IdeaStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"


class TaskConfig(BaseModel):
    maxDepth: int = Field(default=3, ge=1, le=8)
    maxNodes: int = Field(default=50, ge=1, le=500)
    searchSources: list[str] = Field(
        default_factory=lambda: ["Web Search",
                                 "arXiv", "Semantic Scholar", "OpenAlex"]
    )
    priority: int = Field(default=3, ge=1, le=5)
    researchMode: ResearchMode = Field(default=ResearchMode.EVIDENCE_REPORT)
    numReflections: int = Field(default=2, ge=1, le=6)
    numInitialIdeas: int = Field(default=3, ge=1, le=8)
    branchPruneThreshold: float = Field(default=0.25, ge=0.0, le=1.0)
    requiresNoveltyCheck: bool = False
    targetWordCount: int = Field(default=5000, ge=1000, le=50000)
    llmProvider: LLMProvider = Field(default=LLMProvider.OPENROUTER)

    @model_validator(mode="before")
    @classmethod
    def _apply_research_defaults(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        raw_mode = payload.get("researchMode", ResearchMode.EVIDENCE_REPORT)
        try:
            mode = raw_mode if isinstance(
                raw_mode, ResearchMode) else ResearchMode(str(raw_mode))
        except Exception:
            mode = ResearchMode.EVIDENCE_REPORT
            payload["researchMode"] = mode
        if payload.get("requiresNoveltyCheck") is None or "requiresNoveltyCheck" not in payload:
            payload["requiresNoveltyCheck"] = mode in {
                ResearchMode.EXPERIMENTAL_RESEARCH,
                ResearchMode.PAPER_WRITEUP,
            }
        return payload


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
    branchId: str | None = None
    branchScore: float = Field(default=0.0, ge=0.0, le=1.0)
    branchDepth: int = Field(default=0, ge=0)
    positionX: float | None = None
    positionY: float | None = None
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


class BranchScore(BaseModel):
    infoGain: float = Field(default=0.0, ge=0.0, le=1.0)
    evidenceStrength: float = Field(default=0.0, ge=0.0, le=1.0)
    feasibility: float = Field(default=0.0, ge=0.0, le=1.0)
    total: float = Field(default=0.0, ge=0.0, le=1.0)


class SearchBranch(BaseModel):
    branchId: str
    parentBranchId: str | None = None
    rootNodeId: str
    depth: int = Field(default=0, ge=0)
    status: NodeStatus = Field(default=NodeStatus.PENDING)
    score: BranchScore = Field(default_factory=BranchScore)
    nodeIds: list[str] = Field(default_factory=list)


class SearchTree(BaseModel):
    taskId: str
    rootBranchId: str
    branches: list[SearchBranch] = Field(default_factory=list)


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
    ASSISTANT_TEXT = "ASSISTANT_TEXT"
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


class RelatedWorkItem(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(default="", max_length=1000)
    url: str = ""
    relevanceScore: float = Field(default=0.0, ge=0.0, le=1.0)


class NoveltyAssessment(BaseModel):
    summary: str = ""
    noveltyScore: float = Field(default=0.0, ge=0.0, le=1.0)
    isNovel: bool = False
    similarWork: list[str] = Field(default_factory=list)
    differentiationNotes: list[str] = Field(default_factory=list)


class FeasibilityAssessment(BaseModel):
    summary: str = ""
    feasibilityScore: float = Field(default=0.0, ge=0.0, le=1.0)
    isFeasible: bool = False
    blockers: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class ExperimentProposal(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(default="", max_length=1000)
    method: str = Field(default="", max_length=2000)
    metrics: list[str] = Field(default_factory=list)
    expectedOutcome: str = Field(default="", max_length=1000)


class RiskAssessment(BaseModel):
    risk: str = Field(min_length=1, max_length=500)
    severity: str = Field(default="medium", pattern="^(low|medium|high)$")
    mitigation: str = Field(default="", max_length=1000)


class ResearchScoreCard(BaseModel):
    noveltyScore: float = Field(default=0.0, ge=0.0, le=1.0)
    feasibilityScore: float = Field(default=0.0, ge=0.0, le=1.0)
    evidenceStrengthScore: float = Field(default=0.0, ge=0.0, le=1.0)
    writeupReadinessScore: float = Field(default=0.0, ge=0.0, le=1.0)
    overallScore: float = Field(default=0.0, ge=0.0, le=1.0)


class ResearchIdea(BaseModel):
    ideaId: str
    title: str = Field(min_length=1, max_length=200)
    problemStatement: str = Field(default="", max_length=2000)
    shortHypothesis: str = Field(default="", max_length=1000)
    abstract: str = Field(default="", max_length=3000)
    relatedWork: list[RelatedWorkItem] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    noveltyAssessment: NoveltyAssessment = Field(
        default_factory=NoveltyAssessment)
    feasibilityAssessment: FeasibilityAssessment = Field(
        default_factory=FeasibilityAssessment)
    experimentProposals: list[ExperimentProposal] = Field(default_factory=list)
    riskFactors: list[RiskAssessment] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    scoreCard: ResearchScoreCard = Field(default_factory=ResearchScoreCard)
    sourceEvidenceIds: list[str] = Field(default_factory=list)
    status: IdeaStatus = Field(default=IdeaStatus.CANDIDATE)


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
    currentIdeas: list[ResearchIdea] = Field(default_factory=list)


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


class LLMOption(BaseModel):
    provider: LLMProvider
    label: str
    model: str
    configured: bool


class LLMSettingsResponse(BaseModel):
    defaultProvider: LLMProvider
    options: list[LLMOption]


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
    favorited: bool = Field(default=False)


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
