import type { ConflictRecord, Evidence, TaskResponse } from "./types";

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
