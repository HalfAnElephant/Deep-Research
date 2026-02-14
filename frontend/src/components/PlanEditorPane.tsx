import type { ConversationStatus } from "../types";

interface PlanEditorPaneProps {
  markdown: string;
  mode: "edit" | "preview";
  dirty: boolean;
  saving: boolean;
  starting: boolean;
  downloading: boolean;
  status: ConversationStatus | null;
  onModeChange: (mode: "edit" | "preview") => void;
  onChange: (value: string) => void;
  onSave: () => void;
  onStart: () => void;
  onDownload: () => void;
}

function canStart(status: ConversationStatus | null): boolean {
  return status === "PLAN_READY";
}

export function PlanEditorPane(props: PlanEditorPaneProps) {
  const {
    markdown,
    mode,
    dirty,
    saving,
    starting,
    downloading,
    status,
    onModeChange,
    onChange,
    onSave,
    onStart,
    onDownload
  } = props;

  const startDisabled = !canStart(status) || starting || saving || !markdown.trim();
  const downloadEnabled = status === "COMPLETED";

  return (
    <section className="editor-pane">
      <header className="editor-head">
        <div>
          <h3>研究方案草稿</h3>
          <p>可直接编辑 Markdown，或通过聊天让 Agent 自动修订。</p>
        </div>
        <div className="mode-switch">
          <button className={mode === "edit" ? "active" : ""} onClick={() => onModeChange("edit")}>
            编辑
          </button>
          <button className={mode === "preview" ? "active" : ""} onClick={() => onModeChange("preview")}>
            预览
          </button>
        </div>
      </header>
      <div className="editor-actions">
        <button className="primary" onClick={onSave} disabled={saving || !dirty || !markdown.trim()}>
          {saving ? "保存中..." : dirty ? "保存草稿" : "已保存"}
        </button>
        <button className="primary subtle" onClick={onStart} disabled={startDisabled}>
          {starting ? "启动中..." : "开始研究"}
        </button>
        <button className="ghost" onClick={onDownload} disabled={!downloadEnabled || downloading}>
          {downloading ? "下载中..." : "下载报告"}
        </button>
      </div>
      <div className="editor-body">
        {mode === "edit" ? (
          <textarea value={markdown} onChange={(event) => onChange(event.target.value)} />
        ) : (
          <pre>{markdown || "暂无可预览内容"}</pre>
        )}
      </div>
    </section>
  );
}
