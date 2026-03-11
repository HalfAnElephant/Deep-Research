import { memo, type ReactNode } from "react";

// ============================================================================
// Avatar Component
// ============================================================================

export interface AvatarProps {
  /** Image URL */
  src?: string;
  /** Alt text for image */
  alt?: string;
  /** Fallback initials or text */
  fallback?: string;
  /** Avatar size */
  size?: "xs" | "small" | "medium" | "large" | "xl";
  /** Additional class */
  className?: string;
  /** Click handler */
  onClick?: () => void;
  /** Status indicator */
  status?: "online" | "away" | "busy" | "offline";
  /** Icon as avatar content */
  icon?: ReactNode;
  /** Shape variant */
  shape?: "circle" | "square" | "rounded";
}

const sizeClasses = {
  xs: "avatar-xs",
  small: "avatar-small",
  medium: "avatar-medium",
  large: "avatar-large",
  xl: "avatar-xl"
};

const sizeDimensions = {
  xs: 24,
  small: 32,
  medium: 40,
  large: 48,
  xl: 64
};

/**
 * Avatar - User or entity representation component.
 *
 * @example
 * ```tsx
 * <Avatar src="/avatar.jpg" alt="User" />
 * <Avatar fallback="JD" size="large" />
 * <Avatar icon={<UserIcon />} status="online" />
 * ```
 */
function AvatarBase({
  src,
  alt = "",
  fallback,
  size = "medium",
  className = "",
  onClick,
  status,
  icon,
  shape = "circle"
}: AvatarProps) {
  const hasImage = src && src.trim() !== "";
  const dimension = sizeDimensions[size];

  // Get initials from fallback text (max 2 characters)
  const initials = fallback
    ? fallback
        .split(" ")
        .map((n) => n[0])
        .join("")
        .slice(0, 2)
        .toUpperCase()
    : "";

  const avatarClassName = [
    "avatar",
    sizeClasses[size],
    `avatar-${shape}`,
    onClick ? "avatar-clickable" : "",
    className
  ]
    .filter(Boolean)
    .join(" ");

  const renderContent = () => {
    if (hasImage) {
      return (
        <img
          src={src}
          alt={alt}
          width={dimension}
          height={dimension}
          className="avatar-image"
          onError={(e) => {
            // Fallback to initials on image error
            (e.target as HTMLImageElement).style.display = "none";
          }}
        />
      );
    }
    if (icon) {
      return <span className="avatar-icon">{icon}</span>;
    }
    if (initials) {
      return <span className="avatar-initials">{initials}</span>;
    }
    // Default fallback icon
    return (
      <svg
        className="avatar-icon"
        width={dimension / 2}
        height={dimension / 2}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    );
  };

  return (
    <div className={avatarClassName} onClick={onClick} role={onClick ? "button" : undefined}>
      {renderContent()}
      {status && <span className={`avatar-status avatar-status-${status}`} />}
    </div>
  );
}

export const Avatar = memo(AvatarBase);
