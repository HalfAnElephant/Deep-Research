import type {
  ConflictRecord,
  ConversationDetail,
  ConversationSummary,
  Evidence,
  RevisePlanResponse,
  RunConversationResponse,
  TaskResponse
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const API_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? "30000");

interface RequestOptions {
  timeoutMs?: number;
}

async function json<T>(input: RequestInfo | URL, init?: RequestInit, options?: RequestOptions): Promise<T> {
  const timeoutMs = options?.timeoutMs ?? API_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(input, { ...init, signal: controller.signal });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Request failed: ${response.status}`);
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
  });
}

export async function getConversation(conversationId: string, options?: RequestOptions): Promise<ConversationDetail> {
  return json<ConversationDetail>(`${API_BASE}/api/v1/conversations/${conversationId}`, undefined, options);
}

export async function reviseConversationPlan(
  conversationId: string,
  instruction: string
): Promise<RevisePlanResponse> {
  return json<RevisePlanResponse>(`${API_BASE}/api/v1/conversations/${conversationId}/plan/revise`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction })
  });
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
      throw new Error(text || `Request failed: ${response.status}`);
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

export function connectProgressWs(taskId: string, onMessage: (event: MessageEvent<string>) => void): WebSocket {
  const wsBase = API_BASE.replace("http://", "ws://").replace("https://", "wss://");
  const ws = new WebSocket(`${wsBase}/api/v1/ws/task/${taskId}/progress`);
  ws.onmessage = onMessage;
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
