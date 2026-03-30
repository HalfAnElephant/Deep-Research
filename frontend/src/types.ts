export type TaskStatus =
  | "READY"
  | "PLANNING"
  | "EXECUTING"
  | "REVIEWING"
  | "SYNTHESIZING"
  | "FINALIZING"
  | "COMPLETED"
  | "FAILED"
  | "SUSPENDED"
  | "ABORTED";

export type ResearchMode =
  | "survey"
  | "evidence_report"
  | "experimental_research"
  | "paper_writeup";

export type IdeaStatus = "CANDIDATE" | "SELECTED" | "REJECTED";

export interface TaskConfig {
  maxDepth: number;
  maxNodes: number;
  searchSources: string[];
  priority: number;
  branchPruneThreshold?: number;
  researchMode?: ResearchMode;
  numReflections?: number;
  numInitialIdeas?: number;
  requiresNoveltyCheck?: boolean;
  requiresExperimentLoop?: boolean;
  requiresPeerReview?: boolean;
  deliverableTypes?: string[];
}

export interface ResearchScoreCard {
  noveltyScore: number;
  feasibilityScore: number;
  evidenceStrengthScore: number;
  executionSuccessScore: number;
  writeupReadinessScore: number;
  reviewScore: number;
  overallScore: number;
}

export interface TaskResponse {
  taskId: string;
  title: string;
  description: string;
  status: TaskStatus;
  createdAt: string;
  updatedAt: string;
  config: TaskConfig;
  reportPath?: string | null;
  researchScoreCard?: ResearchScoreCard | null;
  dag?: {
    nodes: Array<{
      taskId: string;
      parentTaskId?: string | null;
      title: string;
      description: string;
      status: string;
      priority: number;
      dependencies: string[];
      children: string[];
      metadata: {
        estimatedTokenCost: number;
        searchDepth: number;
        infoGainScore: number;
        branchId?: string | null;
        branchScore?: number;
        branchDepth?: number;
        createdAt: string;
        updatedAt: string;
      };
      output: Array<Record<string, unknown>>;
    }>;
    edges: Array<{ from: string; to: string; type: string }>;
  };
}

export interface Evidence {
  id: string;
  taskId: string;
  nodeId: string;
  sourceType: string;
  url: string;
  content: string;
  metadata: {
    title: string;
    publishDate: string;
    relevanceScore: number;
    authors?: string[];
    abstract?: string;
    citationCount?: number;
    impactFactor?: number;
    isPeerReviewed?: boolean;
  };
  score: number;
  extractedData?: {
    tables?: Array<Record<string, unknown>>;
    images?: Array<Record<string, unknown>>;
    numericalValues?: Array<Record<string, unknown>>;
  };
  favorited?: boolean;
}

export interface ConflictRecord {
  conflictId: string;
  parameter: string;
  variance: number;
  context: string;
  resolutionStatus: "OPEN" | "RESOLVED" | "IGNORED";
  disputedValues: Array<{ evidenceId: string; value: number; unit: string; source: string }>;
}

export interface BranchScore {
  infoGain: number;
  evidenceStrength: number;
  feasibility: number;
  total: number;
}

export interface SearchBranch {
  branchId: string;
  parentBranchId?: string | null;
  rootNodeId: string;
  branchType: string;
  branchGoal: string;
  depth: number;
  status: string;
  score: BranchScore;
  pruneReason?: string | null;
  debugDepth: number;
  workerId?: string | null;
  nodeIds: string[];
}

export interface BranchAction {
  actionId: string;
  taskId: string;
  branchId: string;
  actionType: string;
  actionInput: Record<string, unknown>;
  actionOutput: Record<string, unknown>;
  scoreBefore: number;
  scoreAfter: number;
  status: string;
  createdAt: string;
}

export interface BranchRepairAttempt {
  repairId: string;
  taskId: string;
  branchId: string;
  nodeId: string;
  attempt: number;
  diagnosis: string;
  proposal: string;
  succeeded: boolean;
  createdAt: string;
}

export interface ExperimentMetric {
  name: string;
  value: number;
  unit: string;
}

export interface ExperimentArtifact {
  artifactId: string;
  runId: string;
  taskId: string;
  branchId: string;
  nodeId: string;
  artifactType: string;
  path: string;
  summary: string;
  createdAt: string;
}

export interface ExperimentRun {
  runId: string;
  taskId: string;
  branchId: string;
  nodeId: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
  objective: string;
  stdout: string;
  stderr: string;
  exitCode?: number | null;
  metrics: ExperimentMetric[];
  artifacts: ExperimentArtifact[];
  startedAt: string;
  completedAt?: string | null;
}

export interface ProgressEvent {
  event: string;
  timestamp: string;
  data: Record<string, unknown>;
}

export type ConversationStatus = "DRAFTING_PLAN" | "PLAN_READY" | "RUNNING" | "COMPLETED" | "FAILED";

export type MessageRole = "user" | "assistant" | "system";

export type MessageKind =
  | "USER_TEXT"
  | "PLAN_DRAFT"
  | "PLAN_EDITED"
  | "PLAN_REVISION"
  | "PROGRESS_GROUP"
  | "FINAL_REPORT"
  | "ERROR";

export interface PlanRevision {
  conversationId: string;
  version: number;
  author: MessageRole;
  markdown: string;
  createdAt: string;
}

export interface ConversationMessage {
  messageId: string;
  conversationId: string;
  role: MessageRole;
  kind: MessageKind;
  content: string;
  metadata: Record<string, unknown>;
  collapsed: boolean;
  createdAt: string;
}

export interface ConversationSummary {
  conversationId: string;
  topic: string;
  status: ConversationStatus;
  taskId?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ConversationDetail extends ConversationSummary {
  currentPlan?: PlanRevision | null;
  messages: ConversationMessage[];
  agentStates?: AgentState[];
  currentIdeas?: ResearchIdea[];
}

export interface RevisePlanResponse {
  plan: PlanRevision;
  message: ConversationMessage;
}

export interface RunConversationResponse {
  conversationId: string;
  taskId: string;
  status: ConversationStatus;
}

export interface ConversationDeleteResponse {
  conversationId: string;
  deleted: boolean;
}

export interface ConversationBulkDeleteResponse {
  deleted: boolean;
  deletedCount: number;
}

// Agent-related types
export type AgentType = "IDEATION" | "PLANNING" | "WRITING" | "CHECKING";

export type AgentStatus = "IDLE" | "RUNNING" | "COMPLETED" | "FAILED" | "WAITING_INPUT";

export interface AgentState {
  agentType: AgentType;
  status: AgentStatus;
  startedAt?: string;
  completedAt?: string;
  progress: number;
  currentActivity: string;
  output?: Record<string, unknown>;
  error?: string;
}

export interface ResearchHypothesis {
  hypothesisId: string;
  title: string;
  description: string;
  sources: string[];
  confidence: number;
  createdAt: string;
}

export interface ResearchIdea {
  ideaId: string;
  title: string;
  problemStatement: string;
  shortHypothesis: string;
  abstract: string;
  scoreCard: ResearchScoreCard;
  status: IdeaStatus;
}

export interface ResearchPlan {
  planId: string;
  hypothesisId: string;
  steps: Array<{
    step_id: number;
    title: string;
    description: string;
    type: string;
    estimated_time: string;
  }>;
  createdAt: string;
}

// LLM Settings types
export type LLMProvider = "openrouter" | "deepseek" | "openai";

export interface LLMOption {
  provider: LLMProvider;
  label: string;
  model: string;
  configured: boolean;
}

export interface LLMSettingsResponse {
  defaultProvider: LLMProvider;
  options: LLMOption[];
}

// Extended provider config for settings UI
export interface ProviderConfigResponse {
  provider: LLMProvider;
  label: string;
  apiKey: string; // Masked
  baseUrl: string;
  model: string;
  configured: boolean;
  isDefault: boolean;
}

export interface ProviderConfigUpdate {
  apiKey?: string;
  baseUrl?: string;
  model?: string;
  isDefault?: boolean;
}

export interface TaskMappingResponse {
  draft: LLMProvider;
  chat: LLMProvider;
  article: LLMProvider;
}

export interface TaskMappingUpdate {
  draft?: LLMProvider;
  chat?: LLMProvider;
  article?: LLMProvider;
}
