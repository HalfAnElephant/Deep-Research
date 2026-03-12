import { useState } from "react";

import type { ConversationMessage, ConversationStatus } from "../types";
import {
  useMessageTimeline,
  isPlanMessageKind,
  roleLabel,
  type ProgressBundle
} from "../hooks";
import { formatLocalTime } from "../utils/formatTime";
import { ReportViewer } from "./ReportViewer";
import { ProgressBar } from "./ProgressIndicator";

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
  const currentPhase = activeEntries[0]?.phase ?? "";
  const idleWarning = idleSeconds >= 20;

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
    </section>
  );
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