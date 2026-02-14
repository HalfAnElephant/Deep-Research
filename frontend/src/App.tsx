import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";

import {
  abortTask,
  connectProgressWs,
  createTask,
  getDag,
  getReport,
  getTask,
  listConflicts,
  listEvidence,
  pauseTask,
  resumeTask,
  startTask,
  voteConflict
} from "./api";
import type { ConflictRecord, Evidence, ProgressEvent, TaskResponse, TaskStatus } from "./types";

const initialForm = {
  title: "大语言模型幻觉问题研究",
  description: "调研幻觉成因、检测方法、缓解策略与评测基准。",
  maxDepth: 2,
  maxNodes: 8,
  sources: "arXiv,Semantic Scholar",
  priority: 4
};

type ActionKey = "start" | "pause" | "resume" | "abort" | "refresh";
type StatusTone = "idle" | "running" | "paused" | "success" | "danger";

const STATUS_TEXT: Record<TaskStatus, string> = {
  READY: "待启动",
  PLANNING: "规划中",
  EXECUTING: "执行中",
  REVIEWING: "复核中",
  SYNTHESIZING: "综合中",
  FINALIZING: "收尾中",
  COMPLETED: "已完成",
  FAILED: "失败",
  SUSPENDED: "已暂停",
  ABORTED: "已终止"
};

const STATUS_HINT: Record<TaskStatus, string> = {
  READY: "任务已创建，点击“开始执行”进入流程。",
  PLANNING: "系统正在规划任务结构，可暂停或等待进入执行。",
  EXECUTING: "系统正在检索与分析证据，可实时查看进度和事件。",
  REVIEWING: "系统正在处理冲突或等待复核，可继续执行或暂停。",
  SYNTHESIZING: "系统正在写作报告，建议等待完成。",
  FINALIZING: "系统正在收尾，暂不建议操作。",
  COMPLETED: "任务已结束，可下滑查看报告结果。",
  FAILED: "任务执行失败，建议刷新后查看日志并重新创建任务。",
  SUSPENDED: "任务已暂停，点击“继续执行”恢复。",
  ABORTED: "任务已终止，如需继续请重新创建任务。"
};

const STATUS_TONE: Record<TaskStatus, StatusTone> = {
  READY: "idle",
  PLANNING: "running",
  EXECUTING: "running",
  REVIEWING: "running",
  SYNTHESIZING: "running",
  FINALIZING: "running",
  COMPLETED: "success",
  FAILED: "danger",
  SUSPENDED: "paused",
  ABORTED: "danger"
};

const RUNNING_STATUSES = new Set<TaskStatus>(["PLANNING", "EXECUTING", "REVIEWING", "SYNTHESIZING", "FINALIZING"]);
const REFRESH_TIMEOUT_MS = Number(import.meta.env.VITE_REFRESH_TIMEOUT_MS ?? "60000");
const AUTO_REFRESH_INTERVAL_MS = Number(import.meta.env.VITE_AUTO_REFRESH_INTERVAL_MS ?? "3000");

const ACTION_TEXT: Record<ActionKey, string> = {
  start: "开始执行",
  pause: "暂停任务",
  resume: "继续执行",
  abort: "终止任务",
  refresh: "刷新状态"
};

const EVENT_TEXT: Record<string, string> = {
  TASK_CREATED: "任务已创建",
  TASK_PROGRESS: "进度更新",
  TASK_STARTED: "任务开始",
  TASK_PAUSED: "任务暂停",
  TASK_RESUMED: "任务恢复",
  TASK_COMPLETED: "任务完成",
  TASK_FAILED: "任务失败",
  TASK_ABORTED: "任务终止",
  EVIDENCE_FOUND: "发现证据",
  ERROR: "执行异常"
};

function toStatusLabel(status: string): string {
  return STATUS_TEXT[status as TaskStatus] ?? status;
}

function getFlowStep(status: TaskStatus | undefined, hasTask: boolean): number {
  if (!hasTask || status === "READY" || !status) return 1;
  if (status === "COMPLETED" || status === "FAILED" || status === "ABORTED") return 3;
  return 2;
}

function getActionPlan(status: TaskStatus | undefined, hasTask: boolean): ActionKey[] {
  if (!hasTask || !status) return [];
  if (status === "READY") return ["start", "abort", "refresh"];
  if (status === "PLANNING" || status === "EXECUTING" || status === "REVIEWING" || status === "SYNTHESIZING") {
    return ["pause", "abort", "refresh"];
  }
  if (status === "SUSPENDED") return ["resume", "abort", "refresh"];
  return ["refresh"];
}

function pickText(data: Record<string, unknown>, key: string): string {
  const value = data[key];
  return typeof value === "string" ? value.trim() : "";
}

function pickNumber(data: Record<string, unknown>, key: string): number | null {
  const value = data[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function pickObject(data: Record<string, unknown>, key: string): Record<string, unknown> | null {
  const value = data[key];
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function summarizeText(text: string, maxLength = 180): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!normalized) return "";
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength)}...`;
}

function getDefaultProgressDetail(status: TaskStatus | undefined): string {
  if (!status) return "等待创建任务。";
  if (status === "READY") return "任务已创建，等待开始执行。";
  if (status === "PLANNING") return "正在规划任务结构与执行路径。";
  if (status === "EXECUTING") return "正在检索和分析资料。";
  if (status === "REVIEWING") return "正在复核证据冲突。";
  if (status === "SYNTHESIZING") return "正在写作报告内容。";
  if (status === "FINALIZING") return "正在落盘报告与引用文件。";
  if (status === "COMPLETED") return "任务已完成，可查看最终报告。";
  if (status === "FAILED") return "任务失败，请刷新后查看错误信息。";
  if (status === "SUSPENDED") return "任务已暂停，等待继续执行。";
  return "任务已终止，如需继续请重新创建任务。";
}

function formatProgressDetail(payload: ProgressEvent): string {
  if (payload.event === "TASK_COMPLETED") {
    return "报告已生成，可在下方查看。";
  }
  if (payload.event === "TASK_ABORTED") {
    return "任务已终止。";
  }
  if (payload.event === "TASK_FAILED") {
    return "任务执行失败。";
  }
  if (payload.event === "ERROR") {
    const err = pickText(payload.data, "error");
    return err ? `执行异常：${err}` : "执行出现异常。";
  }
  if (payload.event !== "TASK_PROGRESS") return "";

  const state = pickText(payload.data, "state");
  const phase = pickText(payload.data, "phase");
  const nodeTitle = pickText(payload.data, "currentNodeTitle");
  const query = pickText(payload.data, "searchQuery");
  const sectionTitle = pickText(payload.data, "currentSectionTitle");
  const conflictCount = pickNumber(payload.data, "conflictCount");
  const evidenceCount = pickNumber(payload.data, "evidenceCount");

  if (state === "PLANNING") return "正在拆解问题并构建研究计划。";
  if (state === "EXECUTING" && phase === "SEARCHING") {
    if (nodeTitle && query) return `正在检索「${nodeTitle}」：${query}`;
    if (nodeTitle) return `正在检索「${nodeTitle}」相关资料。`;
    return "正在检索资料。";
  }
  if (state === "EXECUTING" && phase === "NODE_COMPLETED") {
    if (nodeTitle && evidenceCount !== null) return `已完成「${nodeTitle}」，新增 ${evidenceCount} 条证据。`;
    if (nodeTitle) return `已完成「${nodeTitle}」检索。`;
    return "当前节点检索已完成。";
  }
  if (state === "EXECUTING") return nodeTitle ? `正在处理板块「${nodeTitle}」。` : "正在处理执行节点。";
  if (state === "REVIEWING") {
    if (conflictCount !== null) return `正在复核冲突证据，待处理 ${conflictCount} 条。`;
    return "正在复核冲突证据。";
  }
  if (state === "SYNTHESIZING" && phase === "WRITING_SECTION" && sectionTitle) {
    return `正在写作板块「${sectionTitle}」。`;
  }
  if (state === "SYNTHESIZING") return "正在整合证据并生成报告正文。";
  if (state === "FINALIZING") return "正在收尾并写入报告文件。";
  return "";
}

function formatEvent(payload: ProgressEvent): string {
  const label = EVENT_TEXT[payload.event] ?? payload.event;
  if (payload.event === "TASK_PROGRESS" && typeof payload.data.progress === "number") {
    const detail = formatProgressDetail(payload);
    return `${payload.timestamp} ${label}：${payload.data.progress}%${detail ? ` | ${detail}` : ""}`;
  }
  if (payload.event === "EVIDENCE_FOUND") {
    const evidenceData = pickObject(payload.data, "evidence");
    if (!evidenceData) return `${payload.timestamp} ${label}`;
    const metadata = pickObject(evidenceData, "metadata") ?? {};
    const title = pickText(metadata, "title");
    const source = pickText(evidenceData, "sourceType");
    const content = summarizeText(pickText(evidenceData, "content"));
    const details = [
      title ? `标题：${title}` : "",
      source ? `来源：${source}` : "",
      content ? `内容：${content}` : ""
    ].filter(Boolean);
    return `${payload.timestamp} ${label}${details.length > 0 ? ` | ${details.join(" | ")}` : ""}`;
  }
  return `${payload.timestamp} ${label}`;
}

function toErrorText(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

interface RefreshOptions {
  keepLiveDetail?: boolean;
}

export function App() {
  const [form, setForm] = useState(initialForm);
  const [task, setTask] = useState<TaskResponse | null>(null);
  const [dag, setDag] = useState<TaskResponse["dag"] | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [conflicts, setConflicts] = useState<ConflictRecord[]>([]);
  const [progress, setProgress] = useState(0);
  const [report, setReport] = useState<string>("");
  const [events, setEvents] = useState<string[]>([]);
  const [busyAction, setBusyAction] = useState<ActionKey | "create" | "resolve" | null>(null);
  const [liveProgressDetail, setLiveProgressDetail] = useState("等待创建任务。");
  const [error, setError] = useState<string>("");

  const busy = busyAction !== null;
  const canControl = Boolean(task?.taskId);
  const taskStatus = task?.status;
  const stateLabel = taskStatus ? STATUS_TEXT[taskStatus] : "未创建任务";
  const statusHint = taskStatus ? STATUS_HINT[taskStatus] : "请先在左侧创建任务。";
  const statusDetail = liveProgressDetail || getDefaultProgressDetail(taskStatus);
  const statusTone = taskStatus ? STATUS_TONE[taskStatus] : "idle";
  const isRunning = taskStatus ? RUNNING_STATUSES.has(taskStatus) : false;
  const flowStep = getFlowStep(taskStatus, canControl);
  const actionPlan = useMemo(() => getActionPlan(taskStatus, canControl), [taskStatus, canControl]);
  const primaryAction = actionPlan[0];
  const secondaryActions = actionPlan.slice(1);
  const openConflicts = useMemo(() => conflicts.filter((c) => c.resolutionStatus === "OPEN"), [conflicts]);
  const progressStyle = { "--value": `${progress}%` } as CSSProperties;

  useEffect(() => {
    if (!task?.taskId) return;
    let disposed = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let reconnectAttempt = 0;

    const connect = () => {
      if (disposed) return;
      ws = connectProgressWs(task.taskId, (msg) => {
        const payload = JSON.parse(msg.data) as ProgressEvent;
        const detail = formatProgressDetail(payload);
        setEvents((prev) => [formatEvent(payload), ...prev].slice(0, 30));
        if (detail) setLiveProgressDetail(detail);
        if (payload.event === "TASK_PROGRESS" && typeof payload.data.progress === "number") {
          setProgress(payload.data.progress);
        }
        if (payload.event === "TASK_COMPLETED" || payload.event === "TASK_FAILED" || payload.event === "TASK_ABORTED") {
          void refreshAll(task.taskId, { keepLiveDetail: true }).then((warnings) => {
            if (warnings.length > 0) setError(warnings.join("；"));
          });
        }
      });
      ws.addEventListener("open", () => {
        reconnectAttempt = 0;
      });
      ws.addEventListener("error", () => {
        ws?.close();
      });
      ws.addEventListener("close", () => {
        if (disposed) return;
        const delay = Math.min(10000, 1000 * 2 ** reconnectAttempt);
        reconnectAttempt += 1;
        reconnectTimer = window.setTimeout(connect, delay);
      });
    };

    connect();
    return () => {
      disposed = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [task?.taskId]);

  useEffect(() => {
    if (!task?.taskId || !taskStatus || !RUNNING_STATUSES.has(taskStatus)) return;
    let disposed = false;
    const timer = window.setInterval(() => {
      void refreshAll(task.taskId, { keepLiveDetail: true }).then((warnings) => {
        if (disposed) return;
        if (warnings.length > 0) setError(warnings.join("；"));
      });
    }, AUTO_REFRESH_INTERVAL_MS);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [task?.taskId, taskStatus]);

  async function refreshAll(taskId: string, options?: RefreshOptions): Promise<string[]> {
    const warnings: string[] = [];
    const [taskResult, dagResult, evidenceResult, conflictsResult] = await Promise.allSettled([
      getTask(taskId, { timeoutMs: REFRESH_TIMEOUT_MS }),
      getDag(taskId, { timeoutMs: REFRESH_TIMEOUT_MS }),
      listEvidence(taskId, { timeoutMs: REFRESH_TIMEOUT_MS }),
      listConflicts(taskId, { timeoutMs: REFRESH_TIMEOUT_MS })
    ]);

    if (taskResult.status === "fulfilled") {
      setTask(taskResult.value);
      if (!options?.keepLiveDetail) {
        setLiveProgressDetail(getDefaultProgressDetail(taskResult.value.status));
      }
    } else {
      warnings.push(`任务状态刷新失败：${toErrorText(taskResult.reason)}`);
    }

    if (dagResult.status === "fulfilled") {
      setDag(dagResult.value ?? null);
    } else {
      warnings.push(`规划图刷新失败：${toErrorText(dagResult.reason)}`);
    }

    if (evidenceResult.status === "fulfilled") {
      setEvidence(evidenceResult.value);
    } else {
      warnings.push(`证据列表刷新失败：${toErrorText(evidenceResult.reason)}`);
    }

    if (conflictsResult.status === "fulfilled") {
      setConflicts(conflictsResult.value);
    } else {
      warnings.push(`冲突列表刷新失败：${toErrorText(conflictsResult.reason)}`);
    }

    if (taskResult.status === "fulfilled" && taskResult.value.reportPath) {
      try {
        setReport(await getReport(taskId, { timeoutMs: REFRESH_TIMEOUT_MS }));
      } catch (err) {
        warnings.push(`报告刷新失败：${toErrorText(err)}`);
      }
    }
    return warnings;
  }

  async function onCreateTask() {
    setBusyAction("create");
    setError("");
    try {
      setProgress(0);
      setEvents([]);
      setReport("");
      setLiveProgressDetail("正在创建任务...");
      const created = await createTask({
        title: form.title,
        description: form.description,
        config: {
          maxDepth: Number(form.maxDepth),
          maxNodes: Number(form.maxNodes),
          searchSources: form.sources.split(",").map((s) => s.trim()).filter(Boolean),
          priority: Number(form.priority)
        }
      });
      setTask(created);
      const warnings = await refreshAll(created.taskId);
      if (warnings.length > 0) setError(warnings.join("；"));
    } catch (err) {
      setError(toErrorText(err));
    } finally {
      setBusyAction(null);
    }
  }

  async function onAction(action: ActionKey) {
    if (!task?.taskId) return;
    setBusyAction(action);
    setError("");
    try {
      if (action === "start") setLiveProgressDetail("已发送开始指令，正在进入执行流程...");
      if (action === "pause") setLiveProgressDetail("正在暂停任务...");
      if (action === "resume") setLiveProgressDetail("正在恢复任务...");
      if (action === "abort") setLiveProgressDetail("正在终止任务...");
      if (action === "refresh") setLiveProgressDetail("正在刷新任务状态...");
      if (action === "refresh") {
        const warnings = await refreshAll(task.taskId);
        if (warnings.length > 0) setError(warnings.join("；"));
        return;
      }
      if (action === "start") await startTask(task.taskId);
      if (action === "pause") await pauseTask(task.taskId);
      if (action === "resume") await resumeTask(task.taskId);
      if (action === "abort") await abortTask(task.taskId);
      const warnings = await refreshAll(task.taskId);
      if (warnings.length > 0) setError(warnings.join("；"));
    } catch (err) {
      setError(toErrorText(err));
    } finally {
      setBusyAction(null);
    }
  }

  async function onResolveConflict(conflict: ConflictRecord) {
    const selected = conflict.disputedValues[0]?.evidenceId;
    if (!selected || !task?.taskId) return;
    setBusyAction("resolve");
    setError("");
    try {
      await voteConflict({
        evidenceId: selected,
        conflictId: conflict.conflictId,
        selectedEvidenceId: selected,
        reason: "单用户默认采信决策。"
      });
      const warnings = await refreshAll(task.taskId);
      if (warnings.length > 0) setError(warnings.join("；"));
    } catch (err) {
      setError(toErrorText(err));
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <main className="layout">
      <section className="hero">
        <h1>Deep Research 本地控制台</h1>
        <div>任务状态：{stateLabel} | 任务 ID：{task?.taskId ?? "未创建"}</div>
      </section>

      <section className="grid">
        <article className="panel span-4">
          <h3>1. 创建任务</h3>
          <label className="label">标题</label>
          <input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} />
          <label className="label">描述</label>
          <textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
          <label className="label">数据源（逗号分隔）</label>
          <input value={form.sources} onChange={(e) => setForm((f) => ({ ...f, sources: e.target.value }))} />
          <div className="actions" style={{ marginTop: 10 }}>
            <button className="primary" onClick={onCreateTask} disabled={busy}>
              {busyAction === "create" ? "创建中..." : "创建"}
            </button>
          </div>
        </article>

        <article className="panel span-8">
          <h3>2. 控制与进度</h3>
          <div className="flow-steps">
            <div className={`flow-step ${flowStep >= 1 ? "active" : ""}`}>1 创建任务</div>
            <div className={`flow-step ${flowStep >= 2 ? "active" : ""}`}>2 执行与监控</div>
            <div className={`flow-step ${flowStep >= 3 ? "active" : ""}`}>3 查看报告</div>
          </div>
          <div className="status-board">
            <div className={`status-pill ${statusTone}`}>
              <span className={`status-dot ${isRunning ? "running" : ""}`} />
              当前状态：{stateLabel}
            </div>
            <div className="status-hint">{statusHint}</div>
            <div className="status-detail">{statusDetail}</div>
          </div>
          <div className="control-block">
            <div className="label">推荐操作</div>
            {primaryAction ? (
              <button
                onClick={() => onAction(primaryAction)}
                disabled={!canControl || busy}
                className={`action-main ${primaryAction === "abort" ? "warn" : "primary"}`}
              >
                {busyAction === primaryAction ? "处理中..." : ACTION_TEXT[primaryAction]}
              </button>
            ) : (
              <div className="item">请先创建任务后再进行控制。</div>
            )}
          </div>
          {secondaryActions.length > 0 && (
            <div className="actions secondary-actions">
              {secondaryActions.map((action) => (
                <button
                  key={action}
                  onClick={() => onAction(action)}
                  disabled={!canControl || busy}
                  className={action === "abort" ? "warn" : ""}
                >
                  {busyAction === action ? "处理中..." : ACTION_TEXT[action]}
                </button>
              ))}
            </div>
          )}
          <div className="label" style={{ marginTop: 12 }}>
            实时进度
          </div>
          <div className="progress">
            <div style={progressStyle} />
          </div>
          <div className="mono" style={{ marginTop: 6 }}>
            进度：{progress}% {isRunning ? "（运行中）" : ""}
          </div>
          {error && (
            <div className="item" style={{ marginTop: 8, color: "#9f2a00" }}>
              {error}
            </div>
          )}
          <div className="label" style={{ marginTop: 10 }}>
            实时事件
          </div>
          <div className="list" style={{ marginTop: 10 }}>
            {events.length === 0 ? (
              <div className="item">暂无事件</div>
            ) : (
              events.map((line) => (
                <div key={line} className="item mono">
                  {line}
                </div>
              ))
            )}
          </div>
        </article>

        <article className="panel span-6">
          <h3>3. 规划图（DAG）</h3>
          <div className="list">
            {dag?.nodes?.map((node) => (
              <div key={node.taskId} className="item">
                <div>
                  <strong>{node.title}</strong>
                </div>
                <div className="mono">id={node.taskId}</div>
                <div className="mono">
                  状态={toStatusLabel(node.status)} depth={node.metadata.searchDepth} gain={node.metadata.infoGainScore}
                </div>
              </div>
            )) ?? <div className="item">暂无 DAG 数据</div>}
          </div>
        </article>

        <article className="panel span-6">
          <h3>4. 执行证据</h3>
          <div className="list">
            {evidence.map((ev) => (
              <div key={ev.id} className="item">
                <div>
                  <strong>{ev.metadata.title}</strong>
                </div>
                <div className="mono">score={ev.score} source={ev.sourceType}</div>
                <a href={ev.url} target="_blank" rel="noreferrer">
                  {ev.url}
                </a>
                <div className="evidence-content">{ev.content || "该证据未返回正文内容。"}</div>
              </div>
            ))}
          </div>
        </article>

        <article className="panel span-6">
          <h3>5. 冲突复核</h3>
          {openConflicts.length === 0 ? (
            <div className="item">无待处理冲突</div>
          ) : (
            <div className="list">
              {openConflicts.map((c) => (
                <div key={c.conflictId} className="item">
                  <div>
                    <strong>{c.parameter}</strong> variance={c.variance}
                  </div>
                  <div className="mono">{c.context}</div>
                  <button onClick={() => onResolveConflict(c)} disabled={busy}>
                    {busyAction === "resolve" ? "处理中..." : "一键采信第一个证据"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="panel span-6">
          <h3>6. 报告输出</h3>
          <pre>{report || "报告尚未生成"}</pre>
        </article>
      </section>
    </main>
  );
}
