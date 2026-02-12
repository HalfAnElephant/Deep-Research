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
  TASK_ABORTED: "任务终止"
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

function formatEvent(payload: ProgressEvent): string {
  const label = EVENT_TEXT[payload.event] ?? payload.event;
  if (payload.event === "TASK_PROGRESS" && typeof payload.data.progress === "number") {
    return `${payload.timestamp} ${label}：${payload.data.progress}%`;
  }
  return `${payload.timestamp} ${label}`;
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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>("");

  const canControl = Boolean(task?.taskId);
  const taskStatus = task?.status;
  const stateLabel = taskStatus ? STATUS_TEXT[taskStatus] : "未创建任务";
  const statusHint = taskStatus ? STATUS_HINT[taskStatus] : "请先在左侧创建任务。";
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
    const ws = connectProgressWs(task.taskId, (msg) => {
      const payload = JSON.parse(msg.data) as ProgressEvent;
      setEvents((prev) => [formatEvent(payload), ...prev].slice(0, 30));
      if (payload.event === "TASK_PROGRESS" && typeof payload.data.progress === "number") {
        setProgress(payload.data.progress);
      }
      if (payload.event === "TASK_COMPLETED" || payload.event === "TASK_FAILED" || payload.event === "TASK_ABORTED") {
        refreshAll(task.taskId);
      }
    });
    return () => ws.close();
  }, [task?.taskId]);

  async function refreshAll(taskId: string) {
    const [nextTask, nextDag, nextEvidence, nextConflicts] = await Promise.all([
      getTask(taskId),
      getDag(taskId),
      listEvidence(taskId),
      listConflicts(taskId)
    ]);
    setTask(nextTask);
    setDag(nextDag ?? null);
    setEvidence(nextEvidence);
    setConflicts(nextConflicts);
    if (nextTask.reportPath) {
      try {
        setReport(await getReport(taskId));
      } catch {
        setReport("");
      }
    }
  }

  async function onCreateTask() {
    setBusy(true);
    setError("");
    try {
      setProgress(0);
      setEvents([]);
      setReport("");
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
      await refreshAll(created.taskId);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onAction(action: ActionKey) {
    if (!task?.taskId) return;
    setBusy(true);
    setError("");
    try {
      if (action === "refresh") {
        await refreshAll(task.taskId);
        return;
      }
      if (action === "start") await startTask(task.taskId);
      if (action === "pause") await pauseTask(task.taskId);
      if (action === "resume") await resumeTask(task.taskId);
      if (action === "abort") await abortTask(task.taskId);
      await refreshAll(task.taskId);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onResolveConflict(conflict: ConflictRecord) {
    const selected = conflict.disputedValues[0]?.evidenceId;
    if (!selected) return;
    await voteConflict({
      evidenceId: selected,
      conflictId: conflict.conflictId,
      selectedEvidenceId: selected,
      reason: "单用户默认采信决策。"
    });
    await refreshAll(task!.taskId);
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
              创建
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
          </div>
          <div className="control-block">
            <div className="label">推荐操作</div>
            {primaryAction ? (
              <button
                onClick={() => onAction(primaryAction)}
                disabled={!canControl || busy}
                className={`action-main ${primaryAction === "abort" ? "warn" : "primary"}`}
              >
                {busy ? "处理中..." : ACTION_TEXT[primaryAction]}
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
                  {ACTION_TEXT[action]}
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
                <div>{ev.content}</div>
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
                  <button onClick={() => onResolveConflict(c)}>一键采信第一个证据</button>
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
