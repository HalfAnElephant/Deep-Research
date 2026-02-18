import { useEffect, useId, useRef, type ReactNode } from "react";

interface DialogProps {
  open: boolean;
  title: string;
  description?: string;
  dismissable?: boolean;
  children?: ReactNode;
  actions: ReactNode;
  onClose: () => void;
}

export function Dialog(props: DialogProps) {
  const { open, title, description, dismissable = true, children, actions, onClose } = props;
  const titleId = useId();
  const descriptionId = useId();
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || !dismissable) return;
      event.preventDefault();
      onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, dismissable, onClose]);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="dialog-overlay"
      role="presentation"
      onMouseDown={(event) => {
        if (!dismissable) return;
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section
        ref={panelRef}
        className="dialog-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
      >
        <header className="dialog-head">
          <h2 id={titleId}>{title}</h2>
          <button
            className="ghost icon-button small"
            type="button"
            aria-label="关闭弹窗"
            onClick={onClose}
            disabled={!dismissable}
          >
            ×
          </button>
        </header>

        {description && (
          <p className="dialog-description" id={descriptionId}>
            {description}
          </p>
        )}

        {children && <div className="dialog-body">{children}</div>}

        <footer className="dialog-actions">{actions}</footer>
      </section>
    </div>
  );
}
