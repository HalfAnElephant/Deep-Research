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
