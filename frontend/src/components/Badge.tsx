import { memo, type ReactNode } from "react";

export interface BadgeProps {
  /** Visual variant */
  variant?: "default" | "primary" | "success" | "warning" | "danger" | "info";
  /** Badge size */
  size?: "small" | "medium";
  /** Text content */
  text?: string;
  /** Numeric count (renders as dot with number) */
  count?: number;
  /** Maximum count to display (e.g., 99+) */
  maxCount?: number;
  /** Icon to display before text */
  icon?: ReactNode;
  /** Pulse animation for live indicators */
  pulse?: boolean;
  /** Custom class name */
  className?: string;
}

const variantClasses = {
  default: "badge-default",
  primary: "badge-primary",
  success: "badge-success",
  warning: "badge-warning",
  danger: "badge-danger",
  info: "badge-info"
};

const sizeClasses = {
  small: "badge-small",
  medium: "badge-medium"
};

/**
 * BadgeBase - Status indicator and count badge component.
 *
 * Features:
 * - Multiple color variants
 * - Text or numeric count display
 * - Optional icon prefix
 * - Pulse animation for live indicators
 * - Max count overflow handling
 *
 * @example
 * ```tsx
 * <Badge variant="success" text="已完成" />
 * <Badge variant="primary" count={5} />
 * <Badge variant="danger" count={150} maxCount={99} />
 * <Badge variant="info" icon={<Icon />} text="进行中" pulse />
 * ```
 */
function BadgeBase({
  variant = "default",
  size = "medium",
  text,
  count,
  maxCount = 99,
  icon,
  pulse = false,
  className = ""
}: BadgeProps) {
  // Determine if this is a count badge (dot style)
  const isCountBadge = count !== undefined;

  // Format count with max overflow
  const displayCount = count !== undefined && count > maxCount ? `${maxCount}+` : count;

  const badgeClassName = [
    "badge",
    variantClasses[variant],
    sizeClasses[size],
    isCountBadge ? "badge-count" : "",
    pulse ? "badge-pulse" : "",
    className
  ]
    .filter(Boolean)
    .join(" ");

  // Count badge (dot style)
  if (isCountBadge) {
    return (
      <span className={badgeClassName} aria-label={`${count} notifications`}>
        {displayCount}
      </span>
    );
  }

  // Standard text badge
  return (
    <span className={badgeClassName}>
      {icon && <span className="badge-icon">{icon}</span>}
      {text && <span className="badge-text">{text}</span>}
    </span>
  );
}

/**
 * Badge - Status indicator and count badge component.
 *
 * Wrapped in React.memo for performance optimization.
 */
export const Badge = memo(BadgeBase);
