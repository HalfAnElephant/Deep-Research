import type { ConversationStatus } from "../types";

interface PlanEditorPaneProps {
  markdown: string;
  mode: "edit" | "preview";
  dirty: boolean;
  showMobileClose: boolean;
  saving: boolean;
  starting: boolean;
  downloading: boolean;
  status: ConversationStatus | null;
  onModeChange: (mode: "edit" | "preview") => void;
  onRequestCloseMobile: () => void;
  onChange: (value: string) => void;
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

export function PlanEditorPane(props: PlanEditorPaneProps) {
  const {
    markdown,
    mode,
    dirty,
    showMobileClose,
    saving,
    starting,
    downloading,
    status,
    onModeChange,
    onRequestCloseMobile,
    onChange,
    onSave,
    onStart,
    onDownload
  } = props;

  const startDisabled = !canStart(status) || starting || saving || !markdown.trim();
  const downloadEnabled = status === "COMPLETED";
  const saveDisabled = saving || !dirty || !markdown.trim();

  // Character and line count for display
  const lineCount = markdown.split("\n").length;
  const charCount = markdown.length;

  return (
    <section className="editor-pane" aria-label="研究方案编辑器">
      <header className="editor-head">
        <div>
          <h3>研究方案草稿</h3>
          <p>可直接编辑 Markdown，或在聊天中让 Agent 改报告/补检索/修订方案。</p>
        </div>
        <div className="editor-head-actions">
          <div
            className="mode-switch"
            role="radiogroup"
            aria-label="编辑模式"
          >
            <button
              className={mode === "edit" ? "active" : ""}
              type="button"
              role="radio"
              aria-checked={mode === "edit"}
              onClick={() => onModeChange("edit")}
            >
              编辑
            </button>
            <button
              className={mode === "preview" ? "active" : ""}
              type="button"
              role="radio"
              aria-checked={mode === "preview"}
              onClick={() => onModeChange("preview")}
            >
              预览
            </button>
          </div>
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
      <div className="editor-body">
        <div className="editor-meta" aria-live="polite" aria-atomic="true">
          {lineCount} 行 · {charCount} 字
        </div>
        {mode === "edit" ? (
          <textarea
            value={markdown}
            onChange={(event) => onChange(event.target.value)}
            placeholder="在此输入研究方案..."
            aria-label="研究方案编辑"
            spellCheck={false}
          />
        ) : (
          <pre
            className="preview-content"
            role="region"
            aria-label="方案预览"
            tabIndex={0}
          >
            {markdown || "暂无可预览内容"}
          </pre>
        )}
      </div>
    </section>
  );
}
