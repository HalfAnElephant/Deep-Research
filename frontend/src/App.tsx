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
import type { ConflictRecord, Evidence, ProgressEvent, TaskResponse } from "./types";

const initialForm = {
  title: "大语言模型幻觉问题研究",
  description: "调研幻觉成因、检测方法、缓解策略与评测基准。",
  maxDepth: 2,
  maxNodes: 8,
  sources: "arXiv,Semantic Scholar",
  priority: 4
};

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
  const stateLabel = task?.status ?? "READY";
  const openConflicts = useMemo(() => conflicts.filter((c) => c.resolutionStatus === "OPEN"), [conflicts]);
  const progressStyle = { "--value": `${progress}%` } as CSSProperties;

  useEffect(() => {
    if (!task?.taskId) return;
    const ws = connectProgressWs(task.taskId, (msg) => {
      const payload = JSON.parse(msg.data) as ProgressEvent;
      setEvents((prev) => [`${payload.timestamp} ${payload.event}`, ...prev].slice(0, 30));
      if (payload.event === "TASK_PROGRESS" && typeof payload.data.progress === "number") {
        setProgress(payload.data.progress);
      }
      if (payload.event === "TASK_COMPLETED") {
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

  async function onAction(action: "start" | "pause" | "resume" | "abort") {
    if (!task?.taskId) return;
    setBusy(true);
    setError("");
    try {
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
      reason: "Single-user default decision."
    });
    await refreshAll(task!.taskId);
  }

  return (
    <main className="layout">
      <section className="hero">
        <h1>Deep Research Local Console</h1>
        <div>State: {stateLabel} | Task: {task?.taskId ?? "未创建"}</div>
      </section>

      <section className="grid">
        <article className="panel span-4">
          <h3>1. 创建任务</h3>
          <label className="label">标题</label>
          <input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} />
          <label className="label">描述</label>
          <textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
          <label className="label">Sources (逗号分隔)</label>
          <input value={form.sources} onChange={(e) => setForm((f) => ({ ...f, sources: e.target.value }))} />
          <div className="actions" style={{ marginTop: 10 }}>
            <button className="primary" onClick={onCreateTask} disabled={busy}>
              创建
            </button>
          </div>
        </article>

        <article className="panel span-8">
          <h3>2. 控制与进度</h3>
          <div className="actions">
            <button onClick={() => onAction("start")} disabled={!canControl || busy} className="primary">
              Start
            </button>
            <button onClick={() => onAction("pause")} disabled={!canControl || busy}>
              Pause
            </button>
            <button onClick={() => onAction("resume")} disabled={!canControl || busy}>
              Resume
            </button>
            <button onClick={() => onAction("abort")} disabled={!canControl || busy} className="warn">
              Abort
            </button>
            <button onClick={() => task?.taskId && refreshAll(task.taskId)} disabled={!canControl || busy}>
              Refresh
            </button>
          </div>
          <div style={{ marginTop: 12 }} className="progress">
            <div style={progressStyle} />
          </div>
          <div className="mono" style={{ marginTop: 6 }}>
            progress={progress}%
          </div>
          {error && (
            <div className="item" style={{ marginTop: 8, color: "#9f2a00" }}>
              {error}
            </div>
          )}
          <div className="list" style={{ marginTop: 10 }}>
            {events.map((line) => (
              <div key={line} className="item mono">
                {line}
              </div>
            ))}
          </div>
        </article>

        <article className="panel span-6">
          <h3>3. Planning / DAG</h3>
          <div className="list">
            {dag?.nodes?.map((node) => (
              <div key={node.taskId} className="item">
                <div>
                  <strong>{node.title}</strong>
                </div>
                <div className="mono">id={node.taskId}</div>
                <div className="mono">
                  status={node.status} depth={node.metadata.searchDepth} gain={node.metadata.infoGainScore}
                </div>
              </div>
            )) ?? <div className="item">暂无 DAG 数据</div>}
          </div>
        </article>

        <article className="panel span-6">
          <h3>4. Executing / Evidence</h3>
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
          <h3>5. Reviewing / Conflicts</h3>
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
          <h3>6. Synthesizing / Report</h3>
          <pre>{report || "报告尚未生成"}</pre>
        </article>
      </section>
    </main>
  );
}
