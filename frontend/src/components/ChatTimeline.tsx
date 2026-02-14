import { useMemo, useState } from "react";

import type { ConversationMessage } from "../types";
import { ReportViewer } from "./ReportViewer";

interface ChatTimelineProps {
  messages: ConversationMessage[];
  downloadingReport: boolean;
  onApplyPlan: (markdown: string) => void;
  onDownloadReport: () => void;
}

interface ProgressEntry {
  summary: string;
  phase: string;
  state: string;
  progress: number | null;
}

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

function roleLabel(role: ConversationMessage["role"]): string {
  if (role === "assistant") return "Agent";
  if (role === "system") return "System";
  return "你";
}

export function ChatTimeline(props: ChatTimelineProps) {
  const { messages, downloadingReport, onApplyPlan, onDownloadReport } = props;
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const ordered = useMemo(() => messages, [messages]);

  return (
    <section className="timeline">
      {ordered.length === 0 ? (
        <div className="timeline-empty">先在左侧创建一个研究会话。</div>
      ) : (
        ordered.map((message) => {
          const isExpanded = expanded[message.messageId] ?? !message.collapsed;
          const entries = message.kind === "PROGRESS_GROUP" ? toProgressEntries(message) : [];
          const toggle = () => setExpanded((prev) => ({ ...prev, [message.messageId]: !isExpanded }));

          return (
            <article key={message.messageId} className={`message message-${message.role}`}>
              <header>
                <span className="message-role">{roleLabel(message.role)}</span>
                <span className="mono">{message.createdAt.slice(11, 19)}</span>
              </header>

              {message.kind === "PROGRESS_GROUP" ? (
                <div className="progress-group">
                  <button className="progress-toggle" onClick={toggle}>
                    <span>{isExpanded ? "收起" : "展开"}研究进度</span>
                    <strong>{message.content}</strong>
                  </button>
                  {isExpanded && (
                    <div className="progress-entries">
                      {entries.length === 0 ? (
                        <div className="progress-entry">暂无明细</div>
                      ) : (
                        entries.map((entry, index) => (
                          <div className="progress-entry" key={`${message.messageId}-${index}`}>
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
              ) : null}

              {(message.kind === "PLAN_DRAFT" || message.kind === "PLAN_REVISION" || message.kind === "PLAN_EDITED") && (
                <div className="plan-card">
                  <pre>{message.content}</pre>
                  <button className="ghost" onClick={() => onApplyPlan(message.content)}>
                    同步到右侧草稿
                  </button>
                </div>
              )}

              {message.kind === "FINAL_REPORT" && (
                <ReportViewer markdown={message.content} downloading={downloadingReport} onDownload={onDownloadReport} />
              )}

              {message.kind === "USER_TEXT" || message.kind === "ERROR" ? (
                <div className={`plain-text ${message.kind === "ERROR" ? "error" : ""}`}>{message.content}</div>
              ) : null}
            </article>
          );
        })
      )}
    </section>
  );
}
