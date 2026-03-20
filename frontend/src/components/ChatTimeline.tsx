import { useState, useEffect } from "react";

import type { ConversationMessage, ConversationStatus } from "../types";
import {
  useMessageTimeline,
  isPlanMessageKind,
  roleLabel,
  type ProgressBundle,
  type DagNodeLiveState,
} from "../hooks";
import { formatLocalTime } from "../utils/formatTime";
import { ReportViewer } from "./ReportViewer";
import { ProgressBar } from "./ProgressIndicator";
import { DAGEditorModal } from "./DAGEditorModal";
import { getDag } from "../api";
import type { DAGGraph, TaskNode, DAGEdge, TaskNodeStatus } from "../hooks/useDAGEditor";

interface ChatTimelineProps {
  messages: ConversationMessage[];
  currentTaskId: string | null;
  draftMode: boolean;
  activeStatus: ConversationStatus | null;
  pendingAssistantText: string | null;
  startingResearch: boolean;
  downloadingReport: boolean;
  onApplyPlan: (markdown: string) => void;
  onOpenPlanDrawer: () => void;
  onStartResearch: () => void;
  onFocusComposer: () => void;
  onDownloadReport: () => void;
  onExportReport?: () => void;
  streamStatus?: "idle" | "connecting" | "connected" | "reconnecting" | "fallback";
  lastProgressEventAt?: string | null;
  idleSeconds?: number;
}

export function ChatTimeline(props: ChatTimelineProps) {
  const {
    messages,
    currentTaskId,
    draftMode,
    activeStatus,
    pendingAssistantText,
    startingResearch,
    downloadingReport,
    onApplyPlan,
    onOpenPlanDrawer,
    onStartResearch,
    onFocusComposer,
    onDownloadReport,
    onExportReport,
    streamStatus = "idle",
    lastProgressEventAt = null,
    idleSeconds = 0,
  } = props;

  // UI state for expanded/collapsed sections
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [expandedReport, setExpandedReport] = useState<Record<string, boolean>>({});
  const [closedReport, setClosedReport] = useState<Record<string, boolean>>({});
  const [showHistoryRounds, setShowHistoryRounds] = useState(true);

  // DAG Editor modal state
  const [isDAGEditorOpen, setIsDAGEditorOpen] = useState(false);
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);

  // DAG state for PLAN_READY phase (fetched from API)
  const [planReadyDag, setPlanReadyDag] = useState<DAGGraph>({ nodes: [], edges: [] });

  // Fetch DAG when in PLAN_READY state with taskId
  useEffect(() => {
    if (activeStatus !== "PLAN_READY" || !currentTaskId) {
      setPlanReadyDag({ nodes: [], edges: [] });
      return;
    }

    let cancelled = false;
    const fetchDag = async () => {
      try {
        const dagData = await getDag(currentTaskId);
        if (cancelled || !dagData || !dagData.nodes) return;

        // Convert backend format to frontend format
        const taskNodes: TaskNode[] = dagData.nodes.map((node) => ({
          nodeId: node.taskId,  // Backend uses taskId as nodeId
          taskId: node.taskId,
          title: node.title,
          description: node.description || "",
          status: (node.status || "PENDING") as TaskNodeStatus,
          priority: node.priority || 0,
          searchDepth: node.metadata?.searchDepth ?? 0,
          infoGainScore: node.metadata?.infoGainScore ?? 0,
          elapsedMs: 0,
          retryCount: 0,
        }));

        // Convert edges from backend format (from/to) to frontend format (source/target)
        const dagEdges: DAGEdge[] = (dagData.edges || []).map((edge, index) => ({
          id: `edge-${edge.from}-${edge.to}`,
          source: edge.from,  // Backend uses 'from', frontend uses 'source'
          target: edge.to,    // Backend uses 'to', frontend uses 'target'
        }));

        if (!cancelled) {
          setPlanReadyDag({ nodes: taskNodes, edges: dagEdges });
        }
      } catch (error) {
        console.error("Failed to fetch DAG for PLAN_READY state:", error);
      }
    };
    fetchDag();
    return () => { cancelled = true; };
  }, [activeStatus, currentTaskId]);

  // DAG save handler
  const handleSaveDAG = async (dag: DAGGraph) => {
    if (!editingTaskId) return;

    try {
      const response = await fetch(`/api/v1/tasks/${editingTaskId}/dag`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(dag),
      });

      if (!response.ok) {
        throw new Error("Failed to save DAG");
      }

      // Close modal
      setIsDAGEditorOpen(false);
      setEditingTaskId(null);
    } catch (error) {
      console.error("Failed to save DAG:", error);
      // TODO: Show error to user via toast or alert
    }
  };

  // Use the custom hook for timeline calculations
  const {
    taskIdByMessageId,
    historyTaskIds,
    visibleMessages,
    latestPlanMessageId,
    progressBundles
  } = useMessageTimeline({
    messages,
    currentTaskId,
    activeStatus,
    showHistoryRounds
  });

  const canStartResearch =
    activeStatus === "PLAN_READY" || activeStatus === "COMPLETED" || activeStatus === "FAILED";
  const activeBundle = currentTaskId ? progressBundles.get(currentTaskId) ?? null : null;
  const activeEntries = activeBundle ? activeBundle.entries.slice(-6).reverse() : [];

  // Get DAG nodes: prefer API-fetched DAG in PLAN_READY state, otherwise from progress bundle
  const progressDagNodes = activeBundle
    ? [...activeBundle.entries]
        .reverse()
        .find((entry) => Array.isArray(entry.dagNodes) && entry.dagNodes.length > 0)?.dagNodes ?? []
    : [];

  // For DAG editor: use planReadyDag (already in DAGGraph format) or convert from progress
  const editorDag: DAGGraph = activeStatus === "PLAN_READY" && planReadyDag.nodes.length > 0
    ? planReadyDag
    : convertToDAGGraph(progressDagNodes, currentTaskId);

  // For display: convert DAGGraph nodes to DagNodeLiveState format
  const latestDagNodes = activeStatus === "PLAN_READY" && planReadyDag.nodes.length > 0
    ? planReadyDag.nodes.map(n => ({
        nodeId: n.nodeId,
        title: n.title,
        status: n.status,
        searchDepth: n.searchDepth,
        dependencies: [],
        elapsedMs: n.elapsedMs,
        retryCount: n.retryCount,
      }))
    : progressDagNodes;

  const currentPhase = activeEntries[0]?.phase ?? "";
  const idleWarning = idleSeconds >= 20;
  const dagColumns = groupDagNodesByDepth(latestDagNodes);
  const dagSummary = summarizeDagNodes(latestDagNodes);

  // Helper to render progress bundle
  const renderProgressBundle = (bundle: ProgressBundle) => {
    const isExpanded = expanded[bundle.bundleKey] ?? !bundle.collapsed;
    const toggle = () =>
      setExpanded((prev) => ({ ...prev, [bundle.bundleKey]: !isExpanded }));

    return (
      <article
        key={bundle.bundleKey}
        className={`message-row ${bundle.role === "user" ? "row-user" : "row-agent"}`}
      >
        <div className={`message message-${bundle.role}`}>
          <header>
            <span className="message-role">{roleLabel(bundle.role)}</span>
            <span className="mono">{formatLocalTime(bundle.createdAt)}</span>
          </header>

          <div className="progress-group">
            <button className="progress-toggle" type="button" onClick={toggle}>
              <div className="progress-toggle-head">
                <span>{isExpanded ? "收起研究进度" : "展开研究进度"}</span>
                {!isExpanded && (
                  <span className="mono progress-percent">
                    {bundle.latestProgress !== null ? `${bundle.latestProgress}%` : "--"}
                  </span>
                )}
              </div>
              <strong>{bundle.latestSummary}</strong>
              {isExpanded && (
                <div className="mono progress-current">
                  当前进度：{bundle.latestProgress !== null ? `${bundle.latestProgress}%` : "--"}
                </div>
              )}
            </button>
            {isExpanded && (
              <div className="progress-entries">
                {bundle.entries.length === 0 ? (
                  <div className="progress-entry">暂无明细</div>
                ) : (
                  bundle.entries.map((entry) => (
                    <div
                      className="progress-entry"
                      key={`${bundle.bundleKey}-${entry.phase}-${entry.state}-${entry.summary}-${entry.progress ?? "na"}-${entry.detail ?? ""}`}
                    >
                      <div>{entry.summary}</div>
                      <div className="mono">
                        {entry.state}/{entry.phase} {entry.progress !== null ? `| ${entry.progress}%` : ""}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      </article>
    );
  };

  return (
    <section className="timeline">
      {(activeStatus === "RUNNING" || activeBundle) && (
        <article className="live-progress-rail" aria-live="polite">
          <header className="live-progress-head">
            <div>
              <strong>实时研究进度</strong>
              <span className={`live-stream-status stream-${streamStatus}`}>
                {streamStatusLabel(streamStatus)}
              </span>
            </div>
            <span className="mono live-progress-time">
              {lastProgressEventAt ? `最近更新 ${formatLocalTime(lastProgressEventAt)}` : "等待首个进度事件"}
            </span>
          </header>
          <div className="live-progress-main">
            <ProgressBar
              progress={activeBundle?.latestProgress ?? 0}
              status={activeStatus === "FAILED" ? "failed" : activeStatus === "COMPLETED" ? "completed" : "running"}
              phase={currentPhase}
            />
            <p className="live-progress-summary">{activeBundle?.latestSummary ?? "任务启动中，正在等待执行事件。"}</p>
            {(idleWarning || streamStatus === "fallback") && (
              <div className="live-progress-warning">
                {streamStatus === "fallback"
                  ? "实时通道暂不可用，已自动切换为轮询更新。"
                  : `当前阶段已持续 ${idleSeconds} 秒无新进展，系统仍在运行。`}
              </div>
            )}
          </div>
          {activeEntries.length > 0 && (
            <div className="live-progress-events">
              {activeEntries.map((entry) => (
                    <div
                      className="live-progress-event"
                      key={`${entry.phase}-${entry.state}-${entry.summary}-${entry.progress ?? "na"}-${entry.detail ?? ""}`}
                    >
                  <span className="event-phase">{entry.phase}</span>
                  <span className="event-summary">{entry.detail || entry.summary}</span>
                  <span className="event-progress mono">{entry.progress !== null ? `${entry.progress}%` : "--"}</span>
                </div>
              ))}
            </div>
          )}
          {latestDagNodes.length > 0 && (
            <div className="live-progress-dag">
              <div className="live-progress-dag-head">
                <strong>任务 DAG 实时视图</strong>
                <span className="mono live-progress-dag-summary">
                  总计 {dagSummary.total} | 运行中 {dagSummary.running} | 已完成 {dagSummary.completed} | 失败 {dagSummary.failed}
                </span>
              </div>
              <div className="live-progress-dag-grid">
                {dagColumns.map((column) => (
                  <section key={`dag-depth-${column.depth}`} className="live-progress-dag-column">
                    <header className="live-progress-dag-column-head">
                      深度 {column.depth}
                    </header>
                    <div className="live-progress-dag-column-body">
                      {column.nodes.map((node) => (
                        <article
                          key={node.nodeId}
                          className={`dag-node dag-node-${node.status.toLowerCase()}`}
                        >
                          <div className="dag-node-title">{node.title}</div>
                          <div className="dag-node-meta mono">
                            <span>{statusLabel(node.status)}</span>
                            <span>耗时 {formatElapsed(node.elapsedMs)}</span>
                            <span>重试 {node.retryCount}</span>
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            </div>
          )}
        </article>
      )}

      {visibleMessages.length === 0 ? (
        draftMode ? (
          <article className="message-row row-agent">
            <div className="message message-assistant message-hint">
              <header>
                <span className="message-role">Agent</span>
              </header>
              <div className="plain-text">请先输入研究主题，我会先生成第一版研究方案，再由你决定继续执行或修改。</div>
            </div>
          </article>
        ) : (
          <div className="timeline-empty">
            {historyTaskIds.length > 0 && !showHistoryRounds
              ? "当前仅展示最新轮次，点击下方按钮可展开历史轮次。"
              : '从左侧选择会话，或点击"新建研究"。'}
          </div>
        )
      ) : (
        visibleMessages.map((message) => {
          const isLatestPlan = message.messageId === latestPlanMessageId;
          const isReportExpanded = message.kind === "FINAL_REPORT" ? Boolean(expandedReport[message.messageId]) : false;
          const isReportClosed = message.kind === "FINAL_REPORT" ? Boolean(closedReport[message.messageId]) : false;

          // Handle progress group messages
          if (message.kind === "PROGRESS_GROUP") {
            const taskId = taskIdByMessageId.get(message.messageId) ?? "__no_task__";
            const progressBundle = progressBundles.get(taskId);
            if (!progressBundle || message.messageId !== progressBundle.hostMessageId) return null;
            return renderProgressBundle(progressBundle);
          }

          return (
            <article
              key={message.messageId}
              className={`message-row ${message.role === "user" ? "row-user" : "row-agent"} ${
                isReportExpanded ? "row-report-wide" : ""
              }`}
            >
              <div className={`message message-${message.role} ${isReportExpanded ? "message-report-wide" : ""}`}>
                <header>
                  <span className="message-role">{roleLabel(message.role)}</span>
                  <span className="mono">{formatLocalTime(message.createdAt)}</span>
                </header>

                {isPlanMessageKind(message.kind) && (
                  <div className="plan-card">
                    <pre>{message.content}</pre>
                    <button
                      className="ghost"
                      type="button"
                      onClick={() => {
                        onApplyPlan(message.content);
                        onOpenPlanDrawer();
                      }}
                    >
                      打开草稿抽屉
                    </button>
                    {isLatestPlan && currentTaskId && editorDag.nodes.length > 0 && (activeStatus === "RUNNING" || activeStatus === "PLAN_READY") && (
                      <button
                        className="ghost"
                        type="button"
                        onClick={() => {
                          setEditingTaskId(currentTaskId);
                          setIsDAGEditorOpen(true);
                        }}
                      >
                        Edit DAG
                      </button>
                    )}
                    {isLatestPlan && (
                      <div className="plan-actions">
                        <button
                          className="primary subtle"
                          type="button"
                          onClick={onStartResearch}
                          disabled={!canStartResearch || startingResearch}
                        >
                          {startingResearch ? "启动中..." : "继续执行"}
                        </button>
                        <button className="ghost" type="button" onClick={onFocusComposer}>
                          我来修改
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {message.kind === "FINAL_REPORT" && (
                  <ReportViewer
                    markdown={message.content}
                    downloading={downloadingReport}
                    expanded={isReportExpanded}
                    closed={isReportClosed}
                    onDownload={onDownloadReport}
                    onExport={onExportReport}
                    onToggleExpand={() =>
                      setExpandedReport((prev) => ({ ...prev, [message.messageId]: !(prev[message.messageId] ?? false) }))
                    }
                    onToggleClose={() =>
                      setClosedReport((prev) => ({ ...prev, [message.messageId]: !(prev[message.messageId] ?? false) }))
                    }
                  />
                )}

                {message.kind === "USER_TEXT" || message.kind === "ERROR" ? (
                  <div className={`plain-text ${message.kind === "ERROR" ? "error" : ""}`}>{message.content}</div>
                ) : null}
              </div>
            </article>
          );
        })
      )}

      {historyTaskIds.length > 0 && (
        <article className="message-row row-agent">
          <div className="message message-system">
            <button className="ghost" type="button" onClick={() => setShowHistoryRounds((show) => !show)}>
              {showHistoryRounds ? "隐藏历史轮次" : `展开历史轮次（${historyTaskIds.length} 轮）`}
            </button>
          </div>
        </article>
      )}

      {pendingAssistantText && (
        <article className="message-row row-agent">
          <div className="message message-assistant message-pending" aria-live="polite">
            <header>
              <span className="message-role">Agent</span>
            </header>
            <div className="plain-text pending-text">{pendingAssistantText}</div>
            <div className="typing-dots" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
          </div>
        </article>
      )}

      {!draftMode && activeStatus !== "RUNNING" && activeStatus !== "DRAFTING_PLAN" && messages.length > 0 && (
        <article className="message-row row-agent">
          <div className="message message-assistant message-hint">
            <header>
              <span className="message-role">Agent</span>
            </header>
            <div className="plain-text">发送需求给 Agent，可改报告、补检索或修订研究方案。</div>
          </div>
        </article>
      )}

      {/* DAG Editor Modal */}
      {isDAGEditorOpen && editingTaskId && (
        <DAGEditorModal
          taskId={editingTaskId}
          dag={editorDag}
          isOpen={isDAGEditorOpen}
          onClose={() => {
            setIsDAGEditorOpen(false);
            setEditingTaskId(null);
          }}
          onSave={handleSaveDAG}
        />
      )}
    </section>
  );
}

function formatElapsed(elapsedMs: number): string {
  const seconds = Math.max(0, Math.floor(elapsedMs / 1000));
  const mins = Math.floor(seconds / 60);
  const remain = seconds % 60;
  if (mins <= 0) return `${seconds}s`;
  return `${mins}m ${remain}s`;
}

function statusLabel(status: string): string {
  switch (status) {
    case "RUNNING":
      return "进行中";
    case "COMPLETED":
      return "已完成";
    case "FAILED":
      return "失败";
    case "SUSPENDED":
      return "暂停";
    default:
      return "待处理";
  }
}

function summarizeDagNodes(nodes: Array<{ status: string }>) {
  const summary = { total: nodes.length, running: 0, completed: 0, failed: 0 };
  for (const node of nodes) {
    if (node.status === "RUNNING") summary.running += 1;
    if (node.status === "COMPLETED") summary.completed += 1;
    if (node.status === "FAILED") summary.failed += 1;
  }
  return summary;
}

function groupDagNodesByDepth<T extends { searchDepth: number }>(nodes: T[]): Array<{ depth: number; nodes: T[] }> {
  const grouped = new Map<number, T[]>();
  for (const node of nodes) {
    const depth = Number.isFinite(node.searchDepth) ? node.searchDepth : 0;
    const bucket = grouped.get(depth) ?? [];
    bucket.push(node);
    grouped.set(depth, bucket);
  }
  return Array.from(grouped.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([depth, depthNodes]) => ({ depth, nodes: depthNodes }));
}

function streamStatusLabel(status: "idle" | "connecting" | "connected" | "reconnecting" | "fallback"): string {
  switch (status) {
    case "connecting":
      return "连接中";
    case "connected":
      return "实时连接正常";
    case "reconnecting":
      return "重连中";
    case "fallback":
      return "轮询降级";
    default:
      return "未连接";
  }
}

/**
 * Convert DagNodeLiveState array to DAGGraph format for the editor.
 * Derives edges from node dependencies.
 */
function convertToDAGGraph(nodes: DagNodeLiveState[], taskId: string | null): DAGGraph {
  if (!nodes || nodes.length === 0 || !taskId) {
    return { nodes: [], edges: [] };
  }

  const taskNodes: TaskNode[] = nodes.map((node) => ({
    nodeId: node.nodeId,
    taskId: taskId,
    title: node.title,
    description: "",
    status: (node.status || "PENDING") as TaskNode["status"],
    priority: 0,
    searchDepth: node.searchDepth || 0,
    infoGainScore: 0,
    elapsedMs: node.elapsedMs || 0,
    retryCount: node.retryCount || 0,
  }));

  // Derive edges from dependencies
  const edges: DAGEdge[] = [];
  for (const node of nodes) {
    if (node.dependencies && Array.isArray(node.dependencies)) {
      for (const depId of node.dependencies) {
        edges.push({
          id: `edge-${depId}-${node.nodeId}`,
          source: depId,
          target: node.nodeId,
        });
      }
    }
  }

  return { nodes: taskNodes, edges };
}