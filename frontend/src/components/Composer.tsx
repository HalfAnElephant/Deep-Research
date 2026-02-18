import type { RefObject } from "react";

import type { ConversationStatus } from "../types";

interface ComposerProps {
  value: string;
  status: ConversationStatus | null;
  sending: boolean;
  disabled: boolean;
  placeholder: string;
  sendLabel: string;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  onChange: (value: string) => void;
  onSend: () => void;
}

export function Composer(props: ComposerProps) {
  const { value, status, sending, disabled, placeholder, sendLabel, textareaRef, onChange, onSend } = props;
  const canSend = !disabled && !sending && Boolean(value.trim());

  return (
    <footer className="composer">
      <div className="composer-row">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          placeholder={placeholder}
          aria-label="输入研究需求"
          onKeyDown={(event) => {
            if (event.key !== "Enter" || event.shiftKey) return;
            event.preventDefault();
            if (canSend) onSend();
          }}
        />
        <button className="primary" type="button" onClick={onSend} disabled={!canSend}>
          {sending ? "发送中..." : status === "RUNNING" ? "执行中" : sendLabel}
        </button>
      </div>
    </footer>
  );
}
