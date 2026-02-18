import { useMemo, useState } from "react";

import type { ConversationMessage, ConversationStatus } from "../types";
import { formatLocalTime } from "../utils/formatTime";
import { ReportViewer } from "./ReportViewer";

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
}

interface ProgressEntry {
  summary: string;
  phase: string;
  state: string;
  progress: number | null;
}

interface ProgressBundle {
  bundleKey: string;
  taskId: string | null;
  hostMessageId: string;
  role: ConversationMessage["role"];
  createdAt: string;
  collapsed: boolean;
  latestSummary: string;
  latestProgress: number | null;
  entries: ProgressEntry[];
}

const PROGRESS_BUNDLE_KEY = "__progress_bundle__";

function toProgressEntries(message: ConversationMessage): ProgressEntry[] {
  const rawEntries = message.metadata.entries;
  if (!Array.isArray(rawEntries)) return [];
  const parsed: ProgressEntry[] = [];
  for (const item of rawEntries) {
    if (!item || typeof item !== "object") continue;
    const value = item as Record<string, unknown>;
    parsed.push({
      summary: typeof value.summary === "string" ? value.summary : "进度更新",
      phase: typeof value.phase === "string" ? value.phase : "UNKNOWN",
      state: typeof value.state === "string" ? value.state : "UNKNOWN",
      progress: typeof value.progress === "number" ? value.progress : null
    });
  }
  return parsed;
}

function toProgressNumber(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const rounded = Math.round(value);
  return Math.min(100, Math.max(0, rounded));
}

function roleLabel(role: ConversationMessage["role"]): string {
  if (role === "assistant") return "Agent";
  if (role === "system") return "System";
  return "你";
}

function isPlanMessage(kind: ConversationMessage["kind"]): boolean {
  return kind === "PLAN_DRAFT" || kind === "PLAN_REVISION" || kind === "PLAN_EDITED";
}

function extractMessageTaskId(message: ConversationMessage): string | null {
  const directTaskId = message.metadata.taskId;
  if (typeof directTaskId === "string" && directTaskId.trim()) {
    return directTaskId.trim();
  }
  const rawEntries = message.metadata.entries;
  if (!Array.isArray(rawEntries)) return null;
  for (let i = rawEntries.length - 1; i >= 0; i -= 1) {
    const entry = rawEntries[i];
    if (!entry || typeof entry !== "object") continue;
    const raw = (entry as Record<string, unknown>).raw;
    if (!raw || typeof raw !== "object") continue;
    const taskId = (raw as Record<string, unknown>).taskId;
    if (typeof taskId === "string" && taskId.trim()) {
      return taskId.trim();
    }
  }
  return null;
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
    onDownloadReport
  } = props;
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [expandedReport, setExpandedReport] = useState<Record<string, boolean>>({});
  const [closedReport, setClosedReport] = useState<Record<string, boolean>>({});
  const [showHistoryRounds, setShowHistoryRounds] = useState(true);

  const ordered = useMemo(() => messages, [messages]);
  const taskIdByMessageId = useMemo(() => {
    const mapping = new Map<string, string | null>();
    for (const message of ordered) {
      mapping.set(message.messageId, extractMessageTaskId(message));
    }
    return mapping;
  }, [ordered]);

  const historyTaskIds = useMemo(() => {
    if (!currentTaskId) return [];
    const ids = new Set<string>();
    for (const message of ordered) {
      const taskId = taskIdByMessageId.get(message.messageId);
      if (taskId && taskId !== currentTaskId) {
        ids.add(taskId);
      }
    }
    return Array.from(ids);
  }, [ordered, taskIdByMessageId, currentTaskId]);

  const visibleMessages = useMemo(() => {
    if (showHistoryRounds || !currentTaskId) {
      return ordered;
    }
    return ordered.filter((message) => {
      const taskId = taskIdByMessageId.get(message.messageId);
      return !taskId || taskId === currentTaskId;
    });
  }, [ordered, taskIdByMessageId, currentTaskId, showHistoryRounds]);

  const latestPlanMessageId = useMemo(() => {
    for (let i = visibleMessages.length - 1; i >= 0; i -= 1) {
      if (isPlanMessage(visibleMessages[i].kind)) {
        return visibleMessages[i].messageId;
      }
    }
    return null;
  }, [visibleMessages]);

  const progressBundles = useMemo<Map<string, ProgressBundle>>(() => {
    const bundles = new Map<string, ProgressBundle>();
    const progressMessages = visibleMessages.filter((item) => item.kind === "PROGRESS_GROUP");
    if (progressMessages.length === 0) return bundles;

    for (const progressMessage of progressMessages) {
      const taskId = taskIdByMessageId.get(progressMessage.messageId);
      const taskKey = taskId ?? "__no_task__";
      let bundle = bundles.get(taskKey);
      if (!bundle) {
        bundle = {
          bundleKey: `${PROGRESS_BUNDLE_KEY}:${taskKey}`,
          taskId: taskId ?? null,
          hostMessageId: progressMessage.messageId,
          role: progressMessage.role,
          createdAt: progressMessage.createdAt,
          collapsed: progressMessage.collapsed,
          latestSummary: progressMessage.content || "研究进行中",
          latestProgress: null,
          entries: []
        };
        bundles.set(taskKey, bundle);
      } else {
        bundle.createdAt = progressMessage.createdAt;
        bundle.collapsed = bundle.collapsed && progressMessage.collapsed;
      }

      const messageEntries = toProgressEntries(progressMessage);
      bundle.entries.push(...messageEntries);
      for (const entry of messageEntries) {
        if (entry.progress !== null && (bundle.latestProgress === null || entry.progress >= bundle.latestProgress)) {
          bundle.latestProgress = entry.progress;
          bundle.latestSummary = entry.summary;
        }
      }
      const metadataProgress = toProgressNumber(progressMessage.metadata.latestProgress);
      if (metadataProgress !== null && (bundle.latestProgress === null || metadataProgress >= bundle.latestProgress)) {
        bundle.latestProgress = metadataProgress;
        const metadataSummary = progressMessage.metadata.latestSummary;
        if (typeof metadataSummary === "string" && metadataSummary.trim()) {
          bundle.latestSummary = metadataSummary;
        } else if (progressMessage.content.trim()) {
          bundle.latestSummary = progressMessage.content;
        }
      }
    }
    for (const bundle of bundles.values()) {
      if (bundle.taskId === currentTaskId && activeStatus === "COMPLETED") {
        bundle.latestProgress = 100;
      }
    }
    return bundles;
  }, [visibleMessages, taskIdByMessageId, currentTaskId, activeStatus]);

  const canStartResearch = activeStatus === "PLAN_READY" || activeStatus === "COMPLETED" || activeStatus === "FAILED";

  return (
    <section className="timeline">
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
              : "从左侧选择会话，或点击“新建研究”。"}
          </div>
        )
      ) : (
        visibleMessages.map((message) => {
          const isLatestPlan = message.messageId === latestPlanMessageId;
          const isReportExpanded = message.kind === "FINAL_REPORT" ? Boolean(expandedReport[message.messageId]) : false;
          const isReportClosed = message.kind === "FINAL_REPORT" ? Boolean(closedReport[message.messageId]) : false;

          if (message.kind === "PROGRESS_GROUP") {
            const taskId = taskIdByMessageId.get(message.messageId) ?? "__no_task__";
            const progressBundle = progressBundles.get(taskId);
            if (!progressBundle || message.messageId !== progressBundle.hostMessageId) return null;
            const isExpanded = expanded[progressBundle.bundleKey] ?? !progressBundle.collapsed;
            const toggle = () => setExpanded((prev) => ({ ...prev, [progressBundle.bundleKey]: !isExpanded }));

            return (
              <article
                key={progressBundle.bundleKey}
                className={`message-row ${progressBundle.role === "user" ? "row-user" : "row-agent"}`}
              >
                <div className={`message message-${progressBundle.role}`}>
                  <header>
                    <span className="message-role">{roleLabel(progressBundle.role)}</span>
                    <span className="mono">{formatLocalTime(progressBundle.createdAt)}</span>
                  </header>

                  <div className="progress-group">
                    <button className="progress-toggle" type="button" onClick={toggle}>
                      <div className="progress-toggle-head">
                        <span>{isExpanded ? "收起研究进度" : "展开研究进度"}</span>
                        {!isExpanded && (
                          <span className="mono progress-percent">
                            {progressBundle.latestProgress !== null ? `${progressBundle.latestProgress}%` : "--"}
                          </span>
                        )}
                      </div>
                      <strong>{progressBundle.latestSummary}</strong>
                      {isExpanded && (
                        <div className="mono progress-current">
                          当前进度：{progressBundle.latestProgress !== null ? `${progressBundle.latestProgress}%` : "--"}
                        </div>
                      )}
                    </button>
                    {isExpanded && (
                      <div className="progress-entries">
                        {progressBundle.entries.length === 0 ? (
                          <div className="progress-entry">暂无明细</div>
                        ) : (
                          progressBundle.entries.map((entry, index) => (
                            <div className="progress-entry" key={`${progressBundle.bundleKey}-${index}`}>
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

                {isPlanMessage(message.kind) && (
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
          <div className="message message-assistant message-pending" role="status" aria-live="polite">
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

      {!draftMode && activeStatus !== "RUNNING" && activeStatus !== "DRAFTING_PLAN" && ordered.length > 0 && (
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
