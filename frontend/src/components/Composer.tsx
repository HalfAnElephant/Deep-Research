import type { ConversationStatus } from "../types";

interface ComposerProps {
  value: string;
  status: ConversationStatus | null;
  sending: boolean;
  disabled: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
}

export function Composer(props: ComposerProps) {
  const { value, status, sending, disabled, onChange, onSend } = props;
  const readOnlyHint = status === "RUNNING" ? "研究执行中，输入框只读。可在完成后继续修订方案。" : "";

  return (
    <footer className="composer">
      <div className="composer-hint">{readOnlyHint || "发送需求给 Agent，要求它修改研究方案。"} </div>
      <div className="composer-row">
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          placeholder="例如：请补充研究方法中的定量评估指标，并给出里程碑。"
        />
        <button className="primary" onClick={onSend} disabled={disabled || sending || !value.trim()}>
          {sending ? "发送中..." : "发送"}
        </button>
      </div>
    </footer>
  );
}
