import type { ReactNode, ButtonHTMLAttributes } from "react";

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: ReactNode;
  size?: "small" | "medium" | "large";
  variant?: "default" | "primary" | "ghost" | "danger";
  active?: boolean;
  loading?: boolean;
  tooltip?: string;
}

const sizeClasses = {
  small: "icon-button-small",
  medium: "",
  large: "icon-button-large"
};

const variantClasses = {
  default: "",
  primary: "icon-button-primary",
  ghost: "icon-button-ghost",
  danger: "icon-button-danger"
};

export function IconButton({
  icon,
  size = "medium",
  variant = "default",
  active = false,
  loading = false,
  tooltip,
  children,
  className = "",
  disabled,
  ...props
}: IconButtonProps) {
  const buttonClassName = [
    "icon-button",
    sizeClasses[size],
    variantClasses[variant],
    active ? "active" : "",
    loading ? "loading" : "",
    className
  ]
    .filter(Boolean)
    .join(" ");

  const renderContent = () => {
    if (loading) {
      return (
        <svg
          className="loading-spinner"
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
      );
    }
    return icon || children;
  };

  return (
    <button
      className={buttonClassName}
      title={tooltip}
      disabled={disabled || loading}
      aria-label={tooltip}
      aria-busy={loading}
      {...props}
    >
      {renderContent()}
    </button>
  );
}
