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

  // Calculate character count for visual feedback
  const charCount = value.length;
  const maxLength = 500;

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
          aria-describedby={charCount > 0 ? "composer-char-count" : undefined}
          onKeyDown={(event) => {
            if (event.key !== "Enter" || event.shiftKey) return;
            event.preventDefault();
            if (canSend) onSend();
          }}
        />
        <button
          className="primary"
          type="button"
          onClick={onSend}
          disabled={!canSend}
          aria-label={canSend ? "发送消息" : "请输入消息内容"}
          title={canSend ? "按 Enter 发送，Shift + Enter 换行" : "请输入消息内容"}
        >
          {sending ? "发送中..." : status === "RUNNING" ? "执行中" : sendLabel}
        </button>
      </div>
      {charCount > 0 && (
        <div className="composer-footer" id="composer-char-count">
          <span className={`char-count ${charCount > maxLength ? "char-count-warning" : ""}`}>
            {charCount}
          </span>
          <span className="char-count-divider">/</span>
          <span className="char-count-max">{maxLength}</span>
        </div>
      )}
    </footer>
  );
}
