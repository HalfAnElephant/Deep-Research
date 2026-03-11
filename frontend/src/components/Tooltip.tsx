import { memo, useState, useRef, useEffect, type ReactNode } from "react";

// ============================================================================
// Tooltip Component
// ============================================================================

export interface TooltipProps {
  /** Tooltip trigger element */
  children: ReactNode;
  /** Tooltip content */
  content: ReactNode;
  /** Tooltip position */
  position?: "top" | "bottom" | "left" | "right";
  /** Delay before showing (ms) */
  delay?: number;
  /** Additional class */
  className?: string;
  /** Disable tooltip */
  disabled?: boolean;
}

/**
 * Tooltip - Hover-triggered information popup.
 *
 * @example
 * ```tsx
 * <Tooltip content="This is helpful information" position="top">
 *   <button>Hover me</button>
 * </Tooltip>
 * ```
 */
function TooltipBase({
  children,
  content,
  position = "top",
  delay = 200,
  className = "",
  disabled = false
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const triggerRef = useRef<HTMLDivElement>(null);

  const show = () => {
    if (disabled) return;
    setIsMounted(true);
    timeoutRef.current = setTimeout(() => {
      setIsVisible(true);
    }, delay);
  };

  const hide = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setIsVisible(false);
    // Delay unmounting for exit animation
    setTimeout(() => setIsMounted(false), 200);
  };

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return (
    <div
      className={`tooltip-wrapper ${className}`}
      ref={triggerRef}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {isMounted && (
        <div
          className={`tooltip tooltip-${position} ${isVisible ? "tooltip-visible" : ""}`}
          role="tooltip"
        >
          <div className="tooltip-content">{content}</div>
          <div className="tooltip-arrow" />
        </div>
      )}
    </div>
  );
}

export const Tooltip = memo(TooltipBase);
