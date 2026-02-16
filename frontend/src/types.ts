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

export interface TaskConfig {
  maxDepth: number;
  maxNodes: number;
  searchSources: string[];
  priority: number;
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
  dag?: {
    nodes: Array<{
      taskId: string;
      title: string;
      status: string;
      metadata: { searchDepth: number; infoGainScore: number };
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
  };
  score: number;
}

export interface ConflictRecord {
  conflictId: string;
  parameter: string;
  variance: number;
  context: string;
  resolutionStatus: "OPEN" | "RESOLVED" | "IGNORED";
  disputedValues: Array<{ evidenceId: string; value: number; unit: string; source: string }>;
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
