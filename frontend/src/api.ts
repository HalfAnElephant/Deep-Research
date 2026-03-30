import type {
  BranchAction,
  BranchRepairAttempt,
  ConflictRecord,
  ConversationBulkDeleteResponse,
  ConversationDeleteResponse,
  ConversationDetail,
  ConversationSummary,
  Evidence,
  ExperimentRun,
  LLMSettingsResponse,
  RevisePlanResponse,
  SearchBranch,
  RunConversationResponse,
  TaskResponse
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const API_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? "30000");
const PLAN_API_TIMEOUT_MS = Number(import.meta.env.VITE_PLAN_API_TIMEOUT_MS ?? "120000");

interface RequestOptions {
  timeoutMs?: number;
}

// Library types
export interface LibraryItem extends Evidence {
  favorited: boolean;
}

export interface LibraryResponse {
  items: LibraryItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface LibraryFilters {
  page?: number;
  page_size?: number;
  source_type?: string;
  search?: string;
  date_from?: string;
  date_to?: string;
  min_score?: number;
  favorited_only?: boolean;
  sort_by?: string;
  sort_order?: string;
}

export interface TrendAnalysis {
  timeRange: { from: string; to: string };
  timeSeries: Array<{ date: string; count: number }>;
  sourceDistribution: Record<string, number>;
  scoreDistribution: Record<string, number>;
  totalItems: number;
  favoritedItems: number;
}

export interface KeywordAnalysis {
  totalDocuments: number;
  analyzedDocuments: number;
  topKeywords: Array<{ word: string; count: number }>;
  topPhrases: Array<{ phrase: string; count: number }>;
  vocabularySize: number;
}

export interface LibrarySummary {
  totalEvidences: number;
  favoritedEvidences: number;
  sourceDistribution: Record<string, number>;
  scoreDistribution: Record<string, number>;
  lastUpdated: string;
}

function parseErrorMessage(rawText: string, statusCode: number): string {
  const text = rawText.trim();
  if (!text) return `Request failed: ${statusCode}`;
  try {
    const parsed = JSON.parse(text) as unknown;
    if (parsed && typeof parsed === "object") {
      const detail = (parsed as Record<string, unknown>).detail;
      if (typeof detail === "string" && detail.trim()) {
        return detail;
      }
    }
  } catch {
    // Fall back to the raw server text when response is not JSON.
  }
  return text;
}

async function json<T>(input: RequestInfo | URL, init?: RequestInit, options?: RequestOptions): Promise<T> {
  const timeoutMs = options?.timeoutMs ?? API_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(input, { ...init, signal: controller.signal });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(parseErrorMessage(text, response.status));
    }
    return (await response.json()) as T;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`请求超时（${Math.floor(timeoutMs / 1000)}s），请重试`);
    }
    throw err instanceof Error ? err : new Error(String(err));
  } finally {
    clearTimeout(timer);
  }
}

export async function createTask(payload: {
  title: string;
  description: string;
  config: { maxDepth: number; maxNodes: number; searchSources: string[]; priority: number };
}): Promise<TaskResponse> {
  return json<TaskResponse>(`${API_BASE}/api/v1/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function getTask(taskId: string, options?: RequestOptions): Promise<TaskResponse> {
  return json<TaskResponse>(`${API_BASE}/api/v1/tasks/${taskId}`, undefined, options);
}

export async function getDag(taskId: string, options?: RequestOptions): Promise<TaskResponse["dag"]> {
  return json<TaskResponse["dag"]>(`${API_BASE}/api/v1/tasks/${taskId}/dag`, undefined, options);
}

export async function startTask(taskId: string): Promise<void> {
  await json(`${API_BASE}/api/v1/tasks/${taskId}/start`, { method: "POST" });
}

export async function pauseTask(taskId: string): Promise<void> {
  await json(`${API_BASE}/api/v1/tasks/${taskId}/pause`, { method: "POST" });
}

export async function resumeTask(taskId: string): Promise<void> {
  await json(`${API_BASE}/api/v1/tasks/${taskId}/resume`, { method: "POST" });
}

export async function abortTask(taskId: string): Promise<void> {
  await json(`${API_BASE}/api/v1/tasks/${taskId}/abort`, { method: "POST" });
}

export async function listEvidence(taskId: string, options?: RequestOptions): Promise<Evidence[]> {
  const result = await json<{ items: Evidence[] }>(`${API_BASE}/api/v1/evidence?taskId=${taskId}`, undefined, options);
  return result.items;
}

export async function listConflicts(taskId: string, options?: RequestOptions): Promise<ConflictRecord[]> {
  return json<ConflictRecord[]>(`${API_BASE}/api/v1/tasks/${taskId}/conflicts`, undefined, options);
}

export async function listSearchBranches(taskId: string, options?: RequestOptions): Promise<SearchBranch[]> {
  return json<SearchBranch[]>(`${API_BASE}/api/v1/tasks/${taskId}/search-branches`, undefined, options);
}

export async function listBranchActions(
  taskId: string,
  branchId?: string,
  options?: RequestOptions
): Promise<BranchAction[]> {
  const suffix = branchId ? `?branchId=${encodeURIComponent(branchId)}` : "";
  return json<BranchAction[]>(`${API_BASE}/api/v1/tasks/${taskId}/branch-actions${suffix}`, undefined, options);
}

export async function listBranchRepairs(
  taskId: string,
  branchId?: string,
  options?: RequestOptions
): Promise<BranchRepairAttempt[]> {
  const suffix = branchId ? `?branchId=${encodeURIComponent(branchId)}` : "";
  return json<BranchRepairAttempt[]>(`${API_BASE}/api/v1/tasks/${taskId}/branch-repairs${suffix}`, undefined, options);
}

export async function listExperiments(taskId: string, options?: RequestOptions): Promise<ExperimentRun[]> {
  return json<ExperimentRun[]>(`${API_BASE}/api/v1/tasks/${taskId}/experiments`, undefined, options);
}

export async function voteConflict(payload: {
  evidenceId: string;
  conflictId: string;
  selectedEvidenceId: string;
  reason: string;
}): Promise<void> {
  await json(`${API_BASE}/api/v1/evidence/${payload.evidenceId}/vote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conflictId: payload.conflictId,
      selectedEvidenceId: payload.selectedEvidenceId,
      reason: payload.reason
    })
  });
}

export async function getReport(taskId: string, options?: RequestOptions): Promise<string> {
  const result = await json<{ content: string }>(`${API_BASE}/api/v1/tasks/${taskId}/report`, undefined, options);
  return result.content;
}

export async function listConversations(options?: RequestOptions): Promise<ConversationSummary[]> {
  return json<ConversationSummary[]>(`${API_BASE}/api/v1/conversations`, undefined, options);
}

export async function createConversation(payload: {
  topic: string;
  config: { maxDepth: number; maxNodes: number; searchSources: string[]; priority: number };
}): Promise<ConversationDetail> {
  return json<ConversationDetail>(`${API_BASE}/api/v1/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }, { timeoutMs: PLAN_API_TIMEOUT_MS });
}

export async function getConversation(conversationId: string, options?: RequestOptions): Promise<ConversationDetail> {
  return json<ConversationDetail>(`${API_BASE}/api/v1/conversations/${conversationId}`, undefined, options);
}

export async function deleteConversation(conversationId: string): Promise<ConversationDeleteResponse> {
  return json<ConversationDeleteResponse>(`${API_BASE}/api/v1/conversations/${conversationId}`, {
    method: "DELETE"
  });
}

export async function deleteAllConversations(): Promise<ConversationBulkDeleteResponse> {
  return json<ConversationBulkDeleteResponse>(`${API_BASE}/api/v1/conversations`, {
    method: "DELETE"
  });
}

export async function renameConversation(
  conversationId: string,
  payload: { topic: string; syncCurrentPlan?: boolean }
): Promise<ConversationDetail> {
  return json<ConversationDetail>(`${API_BASE}/api/v1/conversations/${conversationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      topic: payload.topic,
      syncCurrentPlan: payload.syncCurrentPlan ?? true
    })
  });
}

export async function reviseConversationPlan(
  conversationId: string,
  instruction: string
): Promise<RevisePlanResponse> {
  return json<RevisePlanResponse>(`${API_BASE}/api/v1/conversations/${conversationId}/plan/revise`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction })
  }, { timeoutMs: PLAN_API_TIMEOUT_MS });
}

export async function updateConversationPlan(
  conversationId: string,
  markdown: string
): Promise<ConversationDetail["currentPlan"]> {
  return json<ConversationDetail["currentPlan"]>(`${API_BASE}/api/v1/conversations/${conversationId}/plan`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ markdown })
  });
}

export async function runConversation(conversationId: string): Promise<RunConversationResponse> {
  return json<RunConversationResponse>(`${API_BASE}/api/v1/conversations/${conversationId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({})
  });
}

async function download(url: string, fileName: string): Promise<void> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(parseErrorMessage(text, response.status));
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`请求超时（${Math.floor(API_TIMEOUT_MS / 1000)}s），请重试`);
    }
    throw err instanceof Error ? err : new Error(String(err));
  } finally {
    clearTimeout(timer);
  }
}

export async function downloadConversationReport(conversationId: string): Promise<void> {
  await download(`${API_BASE}/api/v1/conversations/${conversationId}/report/download`, `${conversationId}.md`);
}

export async function downloadTaskReport(taskId: string): Promise<void> {
  await download(`${API_BASE}/api/v1/tasks/${taskId}/report/download`, `${taskId}.md`);
}

export async function exportArticle(conversationId: string): Promise<void> {
  await download(`${API_BASE}/api/v1/conversations/${conversationId}/export/article`, `${conversationId}_article.md`);
}

export async function exportReferences(conversationId: string): Promise<void> {
  await download(`${API_BASE}/api/v1/conversations/${conversationId}/export/references`, `${conversationId}_references.md`);
}

export async function exportRis(conversationId: string): Promise<void> {
  await download(`${API_BASE}/api/v1/conversations/${conversationId}/export/ris`, `${conversationId}.ris`);
}

export async function exportBibtex(conversationId: string): Promise<void> {
  await download(`${API_BASE}/api/v1/conversations/${conversationId}/export/bibtex`, `${conversationId}.bib`);
}

export async function exportLibraryRis(favoritedOnly: boolean = false): Promise<void> {
  const url = `${API_BASE}/api/v1/library/export/ris${favoritedOnly ? "?favoritedOnly=true" : ""}`;
  await download(url, favoritedOnly ? "library_favorited.ris" : "library.ris");
}

export interface WebSocketCallbacks {
  onMessage: (event: MessageEvent<string>) => void;
  onError?: (error: Event) => void;
  onClose?: () => void;
}

export function connectProgressWs(taskId: string, callbacks: WebSocketCallbacks | ((event: MessageEvent<string>) => void)): WebSocket {
  // Support both old API (just onMessage callback) and new API (object with callbacks)
  const onMessage = typeof callbacks === "function" ? callbacks : callbacks.onMessage;
  const onError = typeof callbacks === "function" ? undefined : callbacks.onError;
  const onClose = typeof callbacks === "function" ? undefined : callbacks.onClose;

  const wsBase = API_BASE.replace("http://", "ws://").replace("https://", "wss://");
  const ws = new WebSocket(`${wsBase}/api/v1/ws/task/${taskId}/progress`);
  ws.onmessage = onMessage;

  ws.onerror = (error) => {
    console.error("WebSocket 连接错误:", error);
    onError?.(error);
  };

  ws.onclose = () => {
    onClose?.();
  };

  let heartbeatTimer: number | null = null;
  ws.onopen = () => {
    ws.send("subscribe");
    heartbeatTimer = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 15000);
  };
  ws.addEventListener("close", () => {
    if (heartbeatTimer !== null) {
      window.clearInterval(heartbeatTimer);
      heartbeatTimer = null;
    }
  });
  return ws;
}

// Library API functions
export async function getLibraryItems(filters?: LibraryFilters): Promise<LibraryResponse> {
  const params = new URLSearchParams();
  if (filters) {
    if (filters.page) params.append("page", String(filters.page));
    if (filters.page_size) params.append("page_size", String(filters.page_size));
    if (filters.source_type) params.append("sourceType", filters.source_type);
    if (filters.search) params.append("search", filters.search);
    if (filters.date_from) params.append("dateFrom", filters.date_from);
    if (filters.date_to) params.append("dateTo", filters.date_to);
    if (filters.min_score !== undefined) params.append("minScore", String(filters.min_score));
    if (filters.favorited_only) params.append("favoritedOnly", "true");
    if (filters.sort_by) params.append("sortBy", filters.sort_by);
    if (filters.sort_order) params.append("sortOrder", filters.sort_order);
  }
  const queryString = params.toString();
  const url = `${API_BASE}/api/v1/library${queryString ? `?${queryString}` : ""}`;
  return json<LibraryResponse>(url);
}

export async function toggleFavorite(evidenceId: string): Promise<LibraryItem> {
  return json<LibraryItem>(`${API_BASE}/api/v1/library/${evidenceId}/favorite`, {
    method: "POST",
  });
}

export async function getLibraryTrends(days: number = 90): Promise<TrendAnalysis> {
  return json<TrendAnalysis>(`${API_BASE}/api/v1/library/trends?days=${days}`);
}

export async function getLibraryKeywords(topN: number = 50): Promise<KeywordAnalysis> {
  return json<KeywordAnalysis>(`${API_BASE}/api/v1/library/keywords?top_n=${topN}`);
}

export async function getLibrarySummary(): Promise<LibrarySummary> {
  return json<LibrarySummary>(`${API_BASE}/api/v1/library/summary`);
}

export async function getLLMSettings(): Promise<LLMSettingsResponse> {
  return json<LLMSettingsResponse>(`${API_BASE}/api/v1/settings/llm`);
}
