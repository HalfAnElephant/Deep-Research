import { useMemo, useState } from "react";

import type { ConversationMessage, ConversationStatus } from "../types";
import { ReportViewer } from "./ReportViewer";

interface ChatTimelineProps {
  messages: ConversationMessage[];
  draftMode: boolean;
  activeStatus: ConversationStatus | null;
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

export function ChatTimeline(props: ChatTimelineProps) {
  const {
    messages,
    draftMode,
    activeStatus,
    startingResearch,
    downloadingReport,
    onApplyPlan,
    onOpenPlanDrawer,
    onStartResearch,
    onFocusComposer,
    onDownloadReport
  } = props;
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const ordered = useMemo(() => messages, [messages]);
  const latestPlanMessageId = useMemo(() => {
    for (let i = ordered.length - 1; i >= 0; i -= 1) {
      if (isPlanMessage(ordered[i].kind)) {
        return ordered[i].messageId;
      }
    }
    return null;
  }, [ordered]);

  const progressBundle = useMemo<ProgressBundle | null>(() => {
    const progressMessages = ordered.filter((item) => item.kind === "PROGRESS_GROUP");
    if (progressMessages.length === 0) return null;

    const entries: ProgressEntry[] = [];
    let latestProgress: number | null = null;
    let latestSummary = progressMessages[progressMessages.length - 1].content || "研究进行中";

    for (const progressMessage of progressMessages) {
      const messageEntries = toProgressEntries(progressMessage);
      entries.push(...messageEntries);
      for (const entry of messageEntries) {
        if (entry.progress !== null && (latestProgress === null || entry.progress >= latestProgress)) {
          latestProgress = entry.progress;
          latestSummary = entry.summary;
        }
      }

      const metadataProgress = toProgressNumber(progressMessage.metadata.latestProgress);
      if (metadataProgress !== null && (latestProgress === null || metadataProgress >= latestProgress)) {
        latestProgress = metadataProgress;
        const metadataSummary = progressMessage.metadata.latestSummary;
        if (typeof metadataSummary === "string" && metadataSummary.trim()) {
          latestSummary = metadataSummary;
        } else if (progressMessage.content.trim()) {
          latestSummary = progressMessage.content;
        }
      }
    }

    return {
      hostMessageId: progressMessages[0].messageId,
      role: progressMessages[0].role,
      createdAt: progressMessages[progressMessages.length - 1].createdAt,
      collapsed: progressMessages.every((item) => item.collapsed),
      latestSummary,
      latestProgress: activeStatus === "COMPLETED" ? 100 : latestProgress,
      entries
    };
  }, [ordered, activeStatus]);

  const canStartResearch = activeStatus === "PLAN_READY";

  return (
    <section className="timeline">
      {ordered.length === 0 ? (
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
          <div className="timeline-empty">从左侧选择会话，或点击“新建研究”。</div>
        )
      ) : (
        ordered.map((message) => {
          const isLatestPlan = message.messageId === latestPlanMessageId;

          if (message.kind === "PROGRESS_GROUP") {
            if (!progressBundle || message.messageId !== progressBundle.hostMessageId) return null;
            const isExpanded = expanded[PROGRESS_BUNDLE_KEY] ?? !progressBundle.collapsed;
            const toggle = () => setExpanded((prev) => ({ ...prev, [PROGRESS_BUNDLE_KEY]: !isExpanded }));

            return (
              <article
                key={PROGRESS_BUNDLE_KEY}
                className={`message-row ${progressBundle.role === "user" ? "row-user" : "row-agent"}`}
              >
                <div className={`message message-${progressBundle.role}`}>
                  <header>
                    <span className="message-role">{roleLabel(progressBundle.role)}</span>
                    <span className="mono">{progressBundle.createdAt.slice(11, 19)}</span>
                  </header>

                  <div className="progress-group">
                    <button className="progress-toggle" onClick={toggle}>
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
                            <div className="progress-entry" key={`${PROGRESS_BUNDLE_KEY}-${index}`}>
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
              className={`message-row ${message.role === "user" ? "row-user" : "row-agent"}`}
            >
              <div className={`message message-${message.role}`}>
                <header>
                  <span className="message-role">{roleLabel(message.role)}</span>
                  <span className="mono">{message.createdAt.slice(11, 19)}</span>
                </header>

                {isPlanMessage(message.kind) && (
                  <div className="plan-card">
                    <pre>{message.content}</pre>
                    <button
                      className="ghost"
                      onClick={() => {
                        onApplyPlan(message.content);
                        onOpenPlanDrawer();
                      }}
                    >
                      打开草稿抽屉
                    </button>
                    {isLatestPlan && (
                      <div className="plan-actions">
                        <button className="primary subtle" onClick={onStartResearch} disabled={!canStartResearch || startingResearch}>
                          {startingResearch ? "启动中..." : "继续执行"}
                        </button>
                        <button className="ghost" onClick={onFocusComposer}>
                          我来修改
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {message.kind === "FINAL_REPORT" && (
                  <ReportViewer markdown={message.content} downloading={downloadingReport} onDownload={onDownloadReport} />
                )}

                {message.kind === "USER_TEXT" || message.kind === "ERROR" ? (
                  <div className={`plain-text ${message.kind === "ERROR" ? "error" : ""}`}>{message.content}</div>
                ) : null}
              </div>
            </article>
          );
        })
      )}

      {!draftMode && activeStatus !== "RUNNING" && ordered.length > 0 && (
        <article className="message-row row-agent">
          <div className="message message-assistant message-hint">
            <header>
              <span className="message-role">Agent</span>
            </header>
            <div className="plain-text">发送需求给 Agent，要求它修改研究方案。</div>
          </div>
        </article>
      )}
    </section>
  );
}
