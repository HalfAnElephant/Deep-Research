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

  return (
    <footer className="composer">
      <div className="composer-row">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          placeholder={placeholder}
        />
        <button className="primary" onClick={onSend} disabled={disabled || sending || !value.trim()}>
          {sending ? "发送中..." : status === "RUNNING" ? "执行中" : sendLabel}
        </button>
      </div>
    </footer>
  );
}
