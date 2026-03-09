import { useEffect, useState, useCallback } from "react";

export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastMessage {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface ToastProps {
  toast: ToastMessage;
  onDismiss: (id: string) => void;
}

function Toast(props: ToastProps) {
  const { toast, onDismiss } = props;
  const [isExiting, setIsExiting] = useState(false);

  const handleDismiss = useCallback(() => {
    setIsExiting(true);
    setTimeout(() => onDismiss(toast.id), 200);
  }, [onDismiss, toast.id]);

  useEffect(() => {
    if (toast.duration === 0) return;
    const timer = setTimeout(handleDismiss, toast.duration ?? 5000);
    return () => clearTimeout(timer);
  }, [toast.duration, handleDismiss]);

  const getIcon = () => {
    switch (toast.type) {
      case "success":
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
        );
      case "error":
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
        );
      case "warning":
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        );
      case "info":
      default:
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
        );
    }
  };

  return (
    <div
      className={`toast toast-${toast.type} ${isExiting ? "toast-exiting" : ""}`}
      role="alert"
      aria-live="polite"
    >
      <div className="toast-icon">{getIcon()}</div>
      <div className="toast-content">
        <p className="toast-title">{toast.title}</p>
        {toast.description && <p className="toast-description">{toast.description}</p>}
      </div>
      {toast.action && (
        <button className="toast-action" type="button" onClick={toast.action.onClick}>
          {toast.action.label}
        </button>
      )}
      <button
        className="toast-dismiss"
        type="button"
        onClick={handleDismiss}
        aria-label="关闭通知"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  );
}

interface ToastContainerProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
  position?: "top-right" | "top-center" | "bottom-right" | "bottom-center";
}

export function ToastContainer(props: ToastContainerProps) {
  const { toasts, onDismiss, position = "bottom-right" } = props;

  if (toasts.length === 0) return null;

  return (
    <div className={`toast-container toast-container-${position}`} aria-label="通知">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

// Hook for managing toasts
export function useToast() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((toast: Omit<ToastMessage, "id">) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    setToasts((prev) => [...prev, { ...toast, id }]);
    return id;
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const success = useCallback(
    (title: string, description?: string, options?: Partial<ToastMessage>) =>
      addToast({ type: "success", title, description, ...options }),
    [addToast]
  );

  const error = useCallback(
    (title: string, description?: string, options?: Partial<ToastMessage>) =>
      addToast({ type: "error", title, description, duration: 0, ...options }),
    [addToast]
  );

  const warning = useCallback(
    (title: string, description?: string, options?: Partial<ToastMessage>) =>
      addToast({ type: "warning", title, description, ...options }),
    [addToast]
  );

  const info = useCallback(
    (title: string, description?: string, options?: Partial<ToastMessage>) =>
      addToast({ type: "info", title, description, ...options }),
    [addToast]
  );

  return {
    toasts,
    addToast,
    removeToast,
    success,
    error,
    warning,
    info
  };
}

// Inline feedback component for form validation and immediate feedback
interface InlineFeedbackProps {
  type: "success" | "error" | "warning" | "info" | "loading";
  message: string;
  className?: string;
}

export function InlineFeedback(props: InlineFeedbackProps) {
  const { type, message, className = "" } = props;

  return (
    <div className={`inline-feedback inline-feedback-${type} ${className}`} role="status" aria-live="polite">
      {type === "loading" && <span className="feedback-spinner" aria-hidden="true" />}
      <span className="feedback-message">{message}</span>
    </div>
  );
}

// Operation status indicator for buttons and actions
interface OperationStatusProps {
  status: "idle" | "loading" | "success" | "error";
  idleLabel: string;
  loadingLabel?: string;
  successLabel?: string;
  errorLabel?: string;
  onSuccess?: () => void;
  onError?: () => void;
}

export function OperationStatus(props: OperationStatusProps) {
  const { status, idleLabel, loadingLabel, successLabel, errorLabel, onSuccess, onError } = props;

  useEffect(() => {
    if (status === "success" && onSuccess) {
      const timer = setTimeout(onSuccess, 2000);
      return () => clearTimeout(timer);
    }
    if (status === "error" && onError) {
      const timer = setTimeout(onError, 3000);
      return () => clearTimeout(timer);
    }
  }, [status, onSuccess, onError]);

  const getStatusDisplay = () => {
    switch (status) {
      case "loading":
        return (
          <>
            <span className="op-spinner" aria-hidden="true" />
            {loadingLabel || "处理中..."}
          </>
        );
      case "success":
        return (
          <>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            {successLabel || "成功"}
          </>
        );
      case "error":
        return (
          <>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
            {errorLabel || "失败"}
          </>
        );
      default:
        return idleLabel;
    }
  };

  return (
    <span className={`operation-status operation-status-${status}`}>
      {getStatusDisplay()}
    </span>
  );
}