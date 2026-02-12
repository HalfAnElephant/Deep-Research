import type { ConflictRecord, Evidence, TaskResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

async function json<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
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

export async function getTask(taskId: string): Promise<TaskResponse> {
  return json<TaskResponse>(`${API_BASE}/api/v1/tasks/${taskId}`);
}

export async function getDag(taskId: string): Promise<TaskResponse["dag"]> {
  return json<TaskResponse["dag"]>(`${API_BASE}/api/v1/tasks/${taskId}/dag`);
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

export async function listEvidence(taskId: string): Promise<Evidence[]> {
  const result = await json<{ items: Evidence[] }>(`${API_BASE}/api/v1/evidence?taskId=${taskId}`);
  return result.items;
}

export async function listConflicts(taskId: string): Promise<ConflictRecord[]> {
  return json<ConflictRecord[]>(`${API_BASE}/api/v1/tasks/${taskId}/conflicts`);
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

export async function getReport(taskId: string): Promise<string> {
  const result = await json<{ content: string }>(`${API_BASE}/api/v1/tasks/${taskId}/report`);
  return result.content;
}

export function connectProgressWs(taskId: string, onMessage: (event: MessageEvent<string>) => void): WebSocket {
  const wsBase = API_BASE.replace("http://", "ws://").replace("https://", "wss://");
  const ws = new WebSocket(`${wsBase}/api/v1/ws/task/${taskId}/progress`);
  ws.onmessage = onMessage;
  ws.onopen = () => ws.send("subscribe");
  return ws;
}
