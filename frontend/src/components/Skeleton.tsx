import { memo, type CSSProperties } from "react";

export interface SkeletonProps {
  /** CSS class name */
  className?: string;
  /** Inline styles */
  style?: CSSProperties;
  /** Animation variant */
  animation?: "shimmer" | "pulse" | "none";
}

export interface SkeletonTextProps extends SkeletonProps {
  /** Number of lines to render */
  lines?: number;
  /** Line height */
  lineHeight?: number | string;
  /** Gap between lines */
  gap?: number | string;
}

export interface SkeletonCircleProps extends SkeletonProps {
  /** Diameter of the circle in pixels */
  size?: number;
}

export interface SkeletonCardProps extends SkeletonProps {
  /** Card header with title skeleton */
  showHeader?: boolean;
  /** Number of content lines */
  contentLines?: number;
  /** Show footer skeleton */
  showFooter?: boolean;
}

/**
 * SkeletonBase - Base skeleton component with shimmer animation.
 *
 * Features:
 * - Shimmer animation effect
 * - Pulse animation variant
 * - Reduced motion support
 * - Customizable via CSS classes
 */
function SkeletonBase({
  className = "",
  style,
  animation = "shimmer"
}: SkeletonProps) {
  return (
    <div
      className={`skeleton ${animation !== "none" ? `skeleton-${animation}` : ""} ${className}`}
      style={style}
      aria-hidden="true"
    />
  );
}

/**
 * SkeletonText - Multi-line text skeleton.
 *
 * @example
 * ```tsx
 * <Skeleton.Text lines={3} />
 * ```
 */
function SkeletonTextBase({
  lines = 1,
  lineHeight = 16,
  gap = 8,
  className = "",
  animation = "shimmer"
}: SkeletonTextProps) {
  return (
    <div
      className={`skeleton-text ${className}`}
      style={{ display: "flex", flexDirection: "column", gap }}
      aria-hidden="true"
    >
      {Array.from({ length: lines }).map((_, index) => (
        <SkeletonBase
          key={index}
          style={{
            height: lineHeight,
            width: index === lines - 1 && lines > 1 ? "75%" : "100%",
            borderRadius: 4
          }}
          animation={animation}
        />
      ))}
    </div>
  );
}

/**
 * SkeletonCircle - Circular skeleton for avatars, icons, etc.
 *
 * @example
 * ```tsx
 * <Skeleton.Circle size={40} />
 * ```
 */
function SkeletonCircleBase({
  size = 40,
  className = "",
  animation = "shimmer"
}: SkeletonCircleProps) {
  return (
    <SkeletonBase
      className={`skeleton-circle ${className}`}
      style={{
        width: size,
        height: size,
        borderRadius: "50%"
      }}
      animation={animation}
    />
  );
}

/**
 * SkeletonCard - Card-shaped skeleton with header, content, and footer.
 *
 * @example
 * ```tsx
 * <Skeleton.Card showHeader contentLines={3} showFooter />
 * ```
 */
function SkeletonCardBase({
  showHeader = true,
  contentLines = 3,
  showFooter = false,
  className = "",
  animation = "shimmer"
}: SkeletonCardProps) {
  return (
    <div className={`skeleton-card ${className}`} aria-hidden="true">
      {showHeader && (
        <div className="skeleton-card-header">
          <SkeletonCircleBase size={40} animation={animation} />
          <div style={{ flex: 1 }}>
            <SkeletonBase
              style={{ height: 16, width: "60%", marginBottom: 8, borderRadius: 4 }}
              animation={animation}
            />
            <SkeletonBase
              style={{ height: 12, width: "40%", borderRadius: 4 }}
              animation={animation}
            />
          </div>
        </div>
      )}

      <div className="skeleton-card-content">
        <SkeletonTextBase
          lines={contentLines}
          lineHeight={14}
          gap={10}
          animation={animation}
        />
      </div>

      {showFooter && (
        <div className="skeleton-card-footer">
          <SkeletonBase
            style={{ height: 32, width: "100%", borderRadius: 6 }}
            animation={animation}
          />
        </div>
      )}
    </div>
  );
}

// Export memoized components
export const Skeleton = Object.assign(memo(SkeletonBase), {
  Text: memo(SkeletonTextBase),
  Circle: memo(SkeletonCircleBase),
  Card: memo(SkeletonCardBase)
});
