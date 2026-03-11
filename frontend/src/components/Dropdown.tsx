import { memo, useState, useRef, useEffect, type ReactNode, type MouseEvent } from "react";

// ============================================================================
// Dropdown Component
// ============================================================================

export interface DropdownProps {
  /** Dropdown trigger element */
  children: ReactNode;
  /** Dropdown menu items */
  items: DropdownItem[];
  /** Alignment */
  align?: "left" | "right";
  /** Additional class */
  className?: string;
  /** Called when item is selected */
  onSelect?: (value: string) => void;
}

export interface DropdownItem {
  /** Item value */
  value: string;
  /** Item label */
  label: ReactNode;
  /** Item icon */
  icon?: ReactNode;
  /** Disabled state */
  disabled?: boolean;
  /** Divider before this item */
  divider?: boolean;
  /** Danger style */
  danger?: boolean;
  /** Keyboard shortcut text */
  shortcut?: string;
}

/**
 * Dropdown - Menu dropdown component.
 *
 * @example
 * ```tsx
 * <Dropdown
 *   items={[
 *     { value: "edit", label: "Edit", icon: <EditIcon /> },
 *     { value: "delete", label: "Delete", danger: true },
 *   ]}
 *   onSelect={(value) => console.log(value)}
 * >
 *   <button>Open Menu</button>
 * </Dropdown>
 * ```
 */
function DropdownBase({
  children,
  items,
  align = "right",
  className = "",
  onSelect
}: DropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleToggle = (e: MouseEvent) => {
    e.stopPropagation();
    if (!isOpen) {
      setIsMounted(true);
      // Small delay for mount animation
      setTimeout(() => setIsOpen(true), 10);
    } else {
      setIsOpen(false);
      setTimeout(() => setIsMounted(false), 200);
    }
  };

  const handleSelect = (value: string, disabled?: boolean) => {
    if (disabled) return;
    onSelect?.(value);
    setIsOpen(false);
    setTimeout(() => setIsMounted(false), 200);
  };

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e: globalThis.MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setTimeout(() => setIsMounted(false), 200);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
        setTimeout(() => setIsMounted(false), 200);
      }
    };

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
    }

    return () => {
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen]);

  return (
    <div className={`dropdown ${className}`} ref={containerRef}>
      <div className="dropdown-trigger" onClick={handleToggle}>
        {children}
      </div>
      {isMounted && (
        <div
          className={`dropdown-menu dropdown-${align} ${isOpen ? "dropdown-open" : ""}`}
          role="menu"
        >
          {items.map((item, index) => (
            <div key={item.value}>
              {item.divider && index > 0 && <div className="dropdown-divider" />}
              <button
                type="button"
                className={`dropdown-item ${item.danger ? "dropdown-item-danger" : ""} ${item.disabled ? "dropdown-item-disabled" : ""}`}
                role="menuitem"
                disabled={item.disabled}
                onClick={() => handleSelect(item.value, item.disabled)}
              >
                {item.icon && <span className="dropdown-item-icon">{item.icon}</span>}
                <span className="dropdown-item-label">{item.label}</span>
                {item.shortcut && <span className="dropdown-item-shortcut">{item.shortcut}</span>}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export const Dropdown = memo(DropdownBase);
