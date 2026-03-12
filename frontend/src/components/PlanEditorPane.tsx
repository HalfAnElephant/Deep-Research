import { memo } from "react";
import type { ConversationStatus } from "../types";
import { PlanConfigForm, parseYamlFrontmatter, serializeYamlFrontmatter } from "./PlanConfigForm";

interface PlanEditorPaneProps {
  markdown: string;
  dirty: boolean;
  showMobileClose: boolean;
  saving: boolean;
  starting: boolean;
  downloading: boolean;
  status: ConversationStatus | null;
  onRequestCloseMobile: () => void;
  onChange: (value: string) => void;
  onReset: () => void;
  onSave: () => void;
  onStart: () => void;
  onDownload: () => void;
}

function canStart(status: ConversationStatus | null): boolean {
  return status === "PLAN_READY" || status === "COMPLETED" || status === "FAILED";
}

function getStatusDescription(status: ConversationStatus | null): string {
  switch (status) {
    case "DRAFTING_PLAN":
      return "正在生成研究方案，请稍候";
    case "PLAN_READY":
      return "方案已就绪，可以开始研究";
    case "RUNNING":
      return "研究正在执行中";
    case "COMPLETED":
      return "研究已完成";
    case "FAILED":
      return "执行失败，请修改方案后重试";
    default:
      return "无活动会话";
  }
}

/**
 * PlanEditorPaneBase - Internal implementation wrapped with React.memo.
 *
 * Performance optimization:
 * - Wrapped in React.memo to prevent unnecessary re-renders
 * - Editor pane only updates when markdown content or status changes
 * - Important for avoiding re-renders during polling/timer updates
 */
function PlanEditorPaneBase(props: PlanEditorPaneProps) {
  const {
    markdown,
    dirty,
    showMobileClose,
    saving,
    starting,
    downloading,
    status,
    onRequestCloseMobile,
    onChange,
    onReset,
    onSave,
    onStart,
    onDownload
  } = props;

  const startDisabled = !canStart(status) || starting || saving || !markdown.trim();
  const downloadEnabled = status === "COMPLETED";
  const saveDisabled = saving || !dirty || !markdown.trim();
  const parsedMarkdown = parseYamlFrontmatter(markdown);
  const planBodyMarkdown = parsedMarkdown.content;

  const handleConfigMarkdownChange = (nextMarkdown: string) => {
    const { config } = parseYamlFrontmatter(nextMarkdown);
    const mergedMarkdown = serializeYamlFrontmatter(config, planBodyMarkdown);
    onChange(mergedMarkdown);
  };

  const handlePlanBodyChange = (nextBody: string) => {
    const mergedMarkdown = serializeYamlFrontmatter(parsedMarkdown.config, nextBody);
    onChange(mergedMarkdown);
  };

  return (
    <section className="editor-pane" aria-label="研究方案编辑器">
      <header className="editor-head">
        <div>
          <h3>研究方案草稿</h3>
          <p>使用图形化配置调整研究参数，避免 Markdown 文本编辑冲突。</p>
        </div>
        <div className="editor-head-actions">
          {showMobileClose && (
            <button
              className="ghost pane-close mobile-only"
              type="button"
              onClick={onRequestCloseMobile}
              aria-label="关闭编辑器"
            >
              关闭
            </button>
          )}
        </div>
      </header>
      <div className="editor-actions" role="toolbar" aria-label="编辑器操作">
        <div className="editor-action-buttons">
          <button
            className="ghost"
            type="button"
            onClick={onReset}
            disabled={saving || starting || !dirty}
            aria-label={dirty ? "重置到已保存草稿" : "没有可重置的改动"}
          >
            重置
          </button>
          <button
            className="primary"
            type="button"
            onClick={onSave}
            disabled={saveDisabled}
            aria-label={dirty ? "保存草稿" : "已保存，无需操作"}
            aria-busy={saving}
          >
            {saving ? "保存中..." : dirty ? "保存草稿" : "已保存"}
          </button>
          <button
            className="primary subtle"
            type="button"
            onClick={onStart}
            disabled={startDisabled}
            aria-label={canStart(status) ? "开始执行研究" : "无法开始研究"}
            aria-busy={starting}
            title={getStatusDescription(status)}
          >
            {starting ? "启动中..." : "开始研究"}
          </button>
          <button
            className="ghost"
            type="button"
            onClick={onDownload}
            disabled={!downloadEnabled || downloading}
            aria-label={downloadEnabled ? "下载研究报告" : "研究完成后可下载"}
            aria-busy={downloading}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }}>
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            {downloading ? "下载中..." : "下载报告"}
          </button>
        </div>
        <PlanConfigForm
          markdown={markdown}
          onMarkdownChange={handleConfigMarkdownChange}
          defaultExpanded={true}
          disabled={saving || starting}
          showResetButton={false}
        />
      </div>
      <div className="editor-body">
        <textarea
          aria-label="研究方案正文 Markdown 编辑器"
          value={planBodyMarkdown}
          onChange={(event) => handlePlanBodyChange(event.target.value)}
          disabled={saving || starting}
          placeholder="在这里直接编辑研究方案正文（Markdown 文本）。"
          spellCheck={false}
        />
      </div>
    </section>
  );
}

export const PlanEditorPane = memo(PlanEditorPaneBase);
