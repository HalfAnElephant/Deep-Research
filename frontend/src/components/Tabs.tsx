import { memo, useState, createContext, useContext, type ReactNode } from "react";

// ============================================================================
// Tabs Component
// ============================================================================

interface TabsContextValue {
  value: string;
  onChange: (value: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabs() {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error("Tabs components must be used within a Tabs provider");
  }
  return context;
}

export interface TabsProps {
  /** Default selected tab value */
  defaultValue: string;
  /** Controlled value */
  value?: string;
  /** Change handler */
  onValueChange?: (value: string) => void;
  /** Tab children */
  children: ReactNode;
  /** Additional class */
  className?: string;
}

export interface TabsListProps {
  children: ReactNode;
  className?: string;
}

export interface TabsTriggerProps {
  /** Tab value */
  value: string;
  children: ReactNode;
  className?: string;
  /** Disabled state */
  disabled?: boolean;
}

export interface TabsContentProps {
  /** Tab value to match */
  value: string;
  children: ReactNode;
  className?: string;
}

/**
 * Tabs - Accessible tab navigation component.
 *
 * @example
 * ```tsx
 * <Tabs defaultValue="tab1">
 *   <TabsList>
 *     <TabsTrigger value="tab1">Tab 1</TabsTrigger>
 *     <TabsTrigger value="tab2">Tab 2</TabsTrigger>
 *   </TabsList>
 *   <TabsContent value="tab1">Content 1</TabsContent>
 *   <TabsContent value="tab2">Content 2</TabsContent>
 * </Tabs>
 * ```
 */
function TabsBase({
  defaultValue,
  value: controlledValue,
  onValueChange,
  children,
  className = ""
}: TabsProps) {
  const [internalValue, setInternalValue] = useState(defaultValue);

  const value = controlledValue ?? internalValue;
  const onChange = (newValue: string) => {
    setInternalValue(newValue);
    onValueChange?.(newValue);
  };

  return (
    <TabsContext.Provider value={{ value, onChange }}>
      <div className={`tabs ${className}`}>{children}</div>
    </TabsContext.Provider>
  );
}

function TabsListBase({ children, className = "" }: TabsListProps) {
  return (
    <div className={`tabs-list ${className}`} role="tablist">
      {children}
    </div>
  );
}

function TabsTriggerBase({
  value: tabValue,
  children,
  className = "",
  disabled = false
}: TabsTriggerProps) {
  const { value, onChange } = useTabs();
  const isActive = value === tabValue;

  return (
    <button
      type="button"
      role="tab"
      aria-selected={isActive}
      aria-controls={`tabpanel-${tabValue}`}
      tabIndex={isActive ? 0 : -1}
      disabled={disabled}
      className={`tabs-trigger ${isActive ? "tabs-trigger-active" : ""} ${className}`}
      onClick={() => onChange(tabValue)}
    >
      {children}
    </button>
  );
}

function TabsContentBase({
  value: tabValue,
  children,
  className = ""
}: TabsContentProps) {
  const { value } = useTabs();
  const isActive = value === tabValue;

  if (!isActive) return null;

  return (
    <div
      id={`tabpanel-${tabValue}`}
      role="tabpanel"
      tabIndex={0}
      className={`tabs-content ${className}`}
    >
      {children}
    </div>
  );
}

export const Tabs = Object.assign(memo(TabsBase), {
  List: memo(TabsListBase),
  Trigger: memo(TabsTriggerBase),
  Content: memo(TabsContentBase)
});
