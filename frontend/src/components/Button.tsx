import { memo, type ReactNode, type ButtonHTMLAttributes } from "react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Button visual variant */
  variant?: "primary" | "secondary" | "ghost" | "text" | "danger";
  /** Button size */
  size?: "small" | "medium" | "large";
  /** Loading state */
  loading?: boolean;
  /** Icon to display before text */
  iconPrefix?: ReactNode;
  /** Icon to display after text */
  iconSuffix?: ReactNode;
  /** Full width button */
  fullWidth?: boolean;
}

const sizeClasses = {
  small: "btn-small",
  medium: "btn-medium",
  large: "btn-large"
};

const variantClasses = {
  primary: "btn-primary",
  secondary: "btn-secondary",
  ghost: "btn-ghost",
  text: "btn-text",
  danger: "btn-danger"
};

/**
 * ButtonBase - Internal implementation wrapped with React.memo.
 *
 * Features:
 * - Multiple variants: primary, secondary, ghost, text, danger
 * - Three sizes: small, medium, large
 * - Loading state with spinner
 * - Icon prefix/suffix support
 * - Ripple effect on click (via CSS)
 * - Full accessibility support
 */
function ButtonBase({
  variant = "primary",
  size = "medium",
  loading = false,
  iconPrefix,
  iconSuffix,
  fullWidth = false,
  children,
  className = "",
  disabled,
  ...props
}: ButtonProps) {
  const buttonClassName = [
    "btn",
    sizeClasses[size],
    variantClasses[variant],
    fullWidth ? "btn-full-width" : "",
    loading ? "btn-loading" : "",
    className
  ]
    .filter(Boolean)
    .join(" ");

  const renderContent = () => {
    if (loading) {
      return (
        <>
          <svg
            className="btn-spinner"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10" opacity="0.25" />
            <path d="M12 2a10 10 0 0 1 10 10" />
          </svg>
          {children}
        </>
      );
    }
    return (
      <>
        {iconPrefix && <span className="btn-icon-prefix">{iconPrefix}</span>}
        {children}
        {iconSuffix && <span className="btn-icon-suffix">{iconSuffix}</span>}
      </>
    );
  };

  return (
    <button
      className={buttonClassName}
      disabled={disabled || loading}
      aria-busy={loading}
      {...props}
    >
      {renderContent()}
    </button>
  );
}

/**
 * Button - Unified button component with multiple variants and sizes.
 *
 * Wrapped in React.memo for performance optimization.
 *
 * @example
 * ```tsx
 * <Button variant="primary" size="medium">Click me</Button>
 * <Button variant="ghost" iconPrefix={<Icon />}>With Icon</Button>
 * <Button loading>Loading...</Button>
 * ```
 */
export const Button = memo(ButtonBase);
