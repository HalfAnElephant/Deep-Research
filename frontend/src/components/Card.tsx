import { memo, type ReactNode, type CSSProperties } from "react";

// ============================================================================
// Card Component
// ============================================================================

export interface CardProps {
  /** Card children */
  children: ReactNode;
  /** Additional CSS class */
  className?: string;
  /** Inline styles */
  style?: CSSProperties;
  /** Hover effect enabled */
  hoverable?: boolean;
  /** 3D tilt effect on hover */
  tilt?: boolean;
  /** Click handler */
  onClick?: () => void;
}

export interface CardHeaderProps {
  children: ReactNode;
  className?: string;
}

export interface CardTitleProps {
  children: ReactNode;
  className?: string;
}

export interface CardDescriptionProps {
  children: ReactNode;
  className?: string;
}

export interface CardContentProps {
  children: ReactNode;
  className?: string;
}

export interface CardFooterProps {
  children: ReactNode;
  className?: string;
}

/**
 * Card - Container component with elevation and optional 3D hover effect.
 *
 * @example
 * ```tsx
 * <Card hoverable tilt>
 *   <CardHeader>
 *     <CardTitle>Card Title</CardTitle>
 *   </CardHeader>
 *   <CardContent>Content goes here</CardContent>
 *   <CardFooter>Footer actions</CardFooter>
 * </Card>
 * ```
 */
function CardBase({
  children,
  className = "",
  style,
  hoverable = false,
  tilt = false,
  onClick
}: CardProps) {
  const cardClassName = [
    "card",
    hoverable ? "card-hoverable" : "",
    tilt ? "card-tilt" : "",
    onClick ? "card-clickable" : "",
    className
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={cardClassName} style={style} onClick={onClick} role={onClick ? "button" : undefined}>
      {children}
    </div>
  );
}

function CardHeaderBase({ children, className = "" }: CardHeaderProps) {
  return <div className={`card-header ${className}`}>{children}</div>;
}

function CardTitleBase({ children, className = "" }: CardTitleProps) {
  return <h3 className={`card-title ${className}`}>{children}</h3>;
}

function CardDescriptionBase({ children, className = "" }: CardDescriptionProps) {
  return <p className={`card-description ${className}`}>{children}</p>;
}

function CardContentBase({ children, className = "" }: CardContentProps) {
  return <div className={`card-content ${className}`}>{children}</div>;
}

function CardFooterBase({ children, className = "" }: CardFooterProps) {
  return <div className={`card-footer ${className}`}>{children}</div>;
}

export const Card = Object.assign(memo(CardBase), {
  Header: memo(CardHeaderBase),
  Title: memo(CardTitleBase),
  Description: memo(CardDescriptionBase),
  Content: memo(CardContentBase),
  Footer: memo(CardFooterBase)
});
