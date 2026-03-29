import { memo, type RefObject } from "react";

import type { ConversationStatus } from "../types";

export interface ComposerProps {
  value: string;
  status: ConversationStatus | null;
  sending: boolean;
  disabled: boolean;
  placeholder: string;
  sendLabel: string;
  textareaRef: RefObject<HTMLTextAreaElement>;
  onChange: (value: string) => void;
  onSend: () => void;
}

/**
 * ComposerBase - Internal implementation wrapped with React.memo.
 *
 * Performance optimization:
 * - Wrapped in React.memo to prevent unnecessary re-renders
 * - Critical for chat interface where parent state changes frequently
 * - Only re-renders when message content or sending state changes
 */
function ComposerBase(props: ComposerProps) {
  const { value, status, sending, disabled, placeholder, sendLabel, textareaRef, onChange, onSend } = props;
  const maxLength = 500;
  const charCount = value.length;
  const canSend = !disabled && !sending && Boolean(value.trim()) && charCount <= maxLength;

  // Progressive warning levels for character count
  // Warning: >400 chars (80%), Error: >500 chars (exceeds limit)
  const getCharCountStatus = () => {
    if (charCount > maxLength) return "error";
    if (charCount > maxLength * 0.8) return "warning"; // 400+ characters
    return "normal";
  };

  const charCountStatus = getCharCountStatus();
  const isOverLimit = charCount > maxLength;

  // Detect platform for keyboard shortcut display
  const isMac = typeof navigator !== "undefined" && navigator.platform.toUpperCase().indexOf("MAC") >= 0;
  const shortcutKey = isMac ? "Cmd" : "Ctrl";

  // Get button state for visual feedback
  const getButtonState = () => {
    if (sending) return { label: "发送中...", icon: "loading", disabled: true };
    if (status === "RUNNING") return { label: "执行中", icon: "blocked", disabled: true };
    if (disabled) return { label: sendLabel, icon: "blocked", disabled: true };
    if (!value.trim()) return { label: sendLabel, icon: "empty", disabled: true };
    if (isOverLimit) return { label: "字数超限", icon: "error", disabled: true };
    return { label: sendLabel, icon: "ready", disabled: false };
  };

  const buttonState = getButtonState();

  // Handle keyboard shortcuts: Cmd/Ctrl + Enter to send
  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Cmd/Ctrl + Enter to send
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      if (canSend) onSend();
      return;
    }
    // Plain Enter to send (without Shift, without Cmd/Ctrl)
    if (event.key === "Enter" && !event.shiftKey && !event.metaKey && !event.ctrlKey) {
      event.preventDefault();
      if (canSend) onSend();
      return;
    }
  };

  return (
    <footer className="composer">
      <div className="composer-row">
        <div className={`composer-textarea-wrap ${isOverLimit ? "over-limit" : ""}`}>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder={placeholder}
            maxLength={maxLength}
            aria-label="输入研究需求"
            aria-describedby="composer-char-count"
          />
          {/* Character counter - always visible */}
          <div className="composer-char-overlay" id="composer-char-count" aria-live="polite">
            <span className={`char-count char-count-${charCountStatus}`}>
              {charCount}/{maxLength}
            </span>
            {charCount > maxLength * 0.8 && charCount <= maxLength && (
              <span className="char-hint">接近上限</span>
            )}
            {isOverLimit && (
              <span className="char-hint error">超出 {charCount - maxLength} 字</span>
            )}
          </div>
        </div>
        <button
          className={`primary composer-send-btn ${buttonState.disabled ? "disabled" : ""} ${sending ? "loading" : ""} ${buttonState.icon === "error" ? "error-state" : ""}`}
          type="button"
          onClick={onSend}
          disabled={!canSend}
          aria-label={canSend ? "发送消息" : buttonState.icon === "error" ? "字数超出限制" : "请输入消息内容"}
          title={canSend ? `按 ${shortcutKey}+Enter 发送，Shift+Enter 换行` : "请输入消息内容"}
        >
          {sending ? (
            <>
              <span className="btn-spinner" aria-hidden="true" />
              {buttonState.label}
            </>
          ) : buttonState.icon === "error" ? (
            <>
              <svg className="btn-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              {buttonState.label}
            </>
          ) : (
            <>
              {!disabled && value.trim() && !isOverLimit && (
                <svg className="btn-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              )}
              {buttonState.label}
            </>
          )}
        </button>
      </div>
      {/* Help text - always visible for guidance */}
      <div className="composer-footer">
        <span className="composer-hint">
          {disabled ? "当前状态不允许输入" : (
            <>
              <kbd className="kbd">{shortcutKey}</kbd> + <kbd className="kbd">Enter</kbd> 发送
              <span className="hint-divider">|</span>
              <kbd className="kbd">Shift</kbd> + <kbd className="kbd">Enter</kbd> 换行
            </>
          )}
        </span>
      </div>
    </footer>
  );
}

/**
 * Export memoized Composer component.
 * Prevents re-renders when parent App component state changes but Composer props remain stable.
 * This is important because App has many state updates (timers, data fetching, etc.)
 */
export const Composer = memo(ComposerBase);
