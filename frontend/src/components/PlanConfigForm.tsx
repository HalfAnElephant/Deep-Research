import { useCallback, useState, useMemo, useEffect, useRef } from "react";

// ============================================================================
// TypeScript Interfaces
// ============================================================================

/**
 * Research plan configuration stored in YAML frontmatter
 */
export interface PlanConfig {
  /** Title of the research plan */
  title: string;
  /** Research topic or question */
  topic: string;
  /** Maximum search depth (1-5) */
  max_depth: number;
  /** Maximum number of nodes to explore (1-20) */
  max_nodes: number;
  /** Research priority (1-10) */
  priority: number;
  /** List of search sources to query */
  search_sources: SearchSource[];
  /** Target word count for the research report (1000-50000) */
  target_word_count?: number;
}

/**
 * Available search sources
 */
export type SearchSource =
  | "Web Search"
  | "arXiv"
  | "Semantic Scholar"
  | "Google Scholar"
  | "PubMed";

/**
 * All available search source options
 */
export const SEARCH_SOURCE_OPTIONS: SearchSource[] = [
  "Web Search",
  "arXiv",
  "Semantic Scholar",
  "Google Scholar",
  "PubMed",
];

/**
 * Default configuration values
 */
export const DEFAULT_CONFIG: PlanConfig = {
  title: "",
  topic: "",
  max_depth: 3,
  max_nodes: 10,
  priority: 5,
  search_sources: ["Web Search", "arXiv", "Semantic Scholar"],
  target_word_count: 5000,
};

// ============================================================================
// YAML Parsing Utilities
// ============================================================================

/**
 * Regex pattern to match YAML frontmatter
 * Matches both --- and ... delimiters
 */
const FRONTMATTER_PATTERN = /^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$/;

/**
 * Parse YAML frontmatter from markdown content
 * @param markdown - The markdown content to parse
 * @returns Object containing the config and remaining content
 */
export function parseYamlFrontmatter(markdown: string): {
  config: Partial<PlanConfig>;
  content: string;
  hasFrontmatter: boolean;
} {
  const match = markdown.match(FRONTMATTER_PATTERN);

  if (!match) {
    return {
      config: {},
      content: markdown,
      hasFrontmatter: false,
    };
  }

  const yamlContent = match[1];
  const remainingContent = match[2] || "";

  const config: Partial<PlanConfig> = {};

  // Parse key-value pairs from YAML
  const lines = yamlContent.split("\n");
  for (const line of lines) {
    const trimmedLine = line.trim();
    if (!trimmedLine || trimmedLine.startsWith("#")) continue;

    const colonIndex = trimmedLine.indexOf(":");
    if (colonIndex === -1) continue;

    const key = trimmedLine.slice(0, colonIndex).trim();
    const valueStr = trimmedLine.slice(colonIndex + 1).trim();

    switch (key) {
      case "title":
      case "topic":
        (config as Record<string, unknown>)[key] = valueStr.replace(/^["']|["']$/g, "");
        break;

      case "max_depth":
      case "max_nodes":
      case "priority": {
        const numValue = parseInt(valueStr, 10);
        if (!Number.isNaN(numValue)) {
          (config as Record<string, unknown>)[key] = numValue;
        }
        break;
      }

      case "search_sources": {
        // Parse array format: ['arXiv', 'Semantic Scholar']
        const arrayMatch = valueStr.match(/^\[(.*)\]$/);
        if (arrayMatch) {
          const items = arrayMatch[1]
            .split(",")
            .map((s) => s.trim().replace(/^["']|["']$/g, ""))
            .filter((s) => SEARCH_SOURCE_OPTIONS.includes(s as SearchSource));
          config.search_sources = items as SearchSource[];
        }
        break;
      }

      case "target_word_count": {
        const numValue = parseInt(valueStr, 10);
        if (!Number.isNaN(numValue)) {
          (config as Record<string, unknown>)[key] = numValue;
        }
        break;
      }
    }
  }

  return {
    config,
    content: remainingContent,
    hasFrontmatter: true,
  };
}

/**
 * Serialize config and content back to markdown with YAML frontmatter
 * @param config - The plan configuration
 * @param content - The markdown content after frontmatter
 * @returns Complete markdown string with YAML frontmatter
 */
export function serializeYamlFrontmatter(
  config: Partial<PlanConfig>,
  content: string
): string {
  const lines: string[] = ["---"];

  // Only include keys that have meaningful values
  if (config.title) {
    lines.push(`title: ${escapeYamlString(config.title)}`);
  }
  if (config.topic) {
    lines.push(`topic: ${escapeYamlString(config.topic)}`);
  }
  if (config.max_depth !== undefined && config.max_depth > 0) {
    lines.push(`max_depth: ${config.max_depth}`);
  }
  if (config.max_nodes !== undefined && config.max_nodes > 0) {
    lines.push(`max_nodes: ${config.max_nodes}`);
  }
  if (config.priority !== undefined && config.priority > 0) {
    lines.push(`priority: ${config.priority}`);
  }
  if (config.search_sources && config.search_sources.length > 0) {
    const sourcesStr = config.search_sources
      .map((s) => `'${s}'`)
      .join(", ");
    lines.push(`search_sources: [${sourcesStr}]`);
  }
  if (config.target_word_count !== undefined && config.target_word_count > 0) {
    lines.push(`target_word_count: ${config.target_word_count}`);
  }

  lines.push("---");
  lines.push("");

  return lines.join("\n") + (content || "");
}

/**
 * Escape a string value for YAML output
 * @param value - The string to escape
 * @returns Escaped string wrapped in quotes if needed
 */
function escapeYamlString(value: string): string {
  // If the value contains special characters or is empty, wrap in quotes
  if (value === "" || /[\n\r\t'"\\]/.test(value)) {
    return JSON.stringify(value);
  }
  return value;
}

// ============================================================================
// Form Validation
// ============================================================================

export interface ValidationErrors {
  title?: string;
  topic?: string;
  max_depth?: string;
  max_nodes?: string;
  priority?: string;
  search_sources?: string;
  target_word_count?: string;
}

/**
 * Validate plan configuration
 * @param config - The configuration to validate
 * @returns Object containing validation errors (empty if valid)
 */
export function validateConfig(config: Partial<PlanConfig>): ValidationErrors {
  const errors: ValidationErrors = {};

  if (config.title !== undefined && config.title.length > 200) {
    errors.title = "标题不能超过200个字符";
  }

  if (config.topic !== undefined && config.topic.length > 500) {
    errors.topic = "主题不能超过500个字符";
  }

  if (config.max_depth !== undefined) {
    if (config.max_depth < 1) {
      errors.max_depth = "最大深度不能小于1";
    } else if (config.max_depth > 5) {
      errors.max_depth = "最大深度不能大于5";
    }
  }

  if (config.max_nodes !== undefined) {
    if (config.max_nodes < 1) {
      errors.max_nodes = "最大节点数不能小于1";
    } else if (config.max_nodes > 20) {
      errors.max_nodes = "最大节点数不能大于20";
    }
  }

  if (config.priority !== undefined) {
    if (config.priority < 1) {
      errors.priority = "优先级不能小于1";
    } else if (config.priority > 10) {
      errors.priority = "优先级不能大于10";
    }
  }

  if (config.search_sources !== undefined && config.search_sources.length === 0) {
    errors.search_sources = "请至少选择一个搜索来源";
  }

  if (config.target_word_count !== undefined) {
    if (config.target_word_count < 1000) {
      errors.target_word_count = "期望字数不能少于1000字";
    } else if (config.target_word_count > 50000) {
      errors.target_word_count = "期望字数不能大于50000字";
    }
  }

  return errors;
}

// ============================================================================
// Component Props
// ============================================================================

export interface PlanConfigFormProps {
  /** The current markdown content */
  markdown: string;
  /** Callback when markdown is updated */
  onMarkdownChange: (markdown: string) => void;
  /** Whether the form should be initially expanded */
  defaultExpanded?: boolean;
  /** Whether the form is disabled */
  disabled?: boolean;
  /** Additional CSS class name */
  className?: string;
  /** Show reset button in footer actions */
  showResetButton?: boolean;
}

// ============================================================================
// Component
// ============================================================================

export function PlanConfigForm({
  markdown,
  onMarkdownChange,
  defaultExpanded = true,
  disabled = false,
  className = "",
  showResetButton = true,
}: PlanConfigFormProps) {
  // Parse initial config from markdown
  const initialData = useMemo(() => parseYamlFrontmatter(markdown), [markdown]);

  // Form state
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [config, setConfig] = useState<PlanConfig>({
    ...DEFAULT_CONFIG,
    ...initialData.config,
  });
  const [errors, setErrors] = useState<ValidationErrors>({});
  const localMarkdownRef = useRef<string | null>(null);

  // Update config when markdown changes externally
  useEffect(() => {
    // Ignore markdown echoes generated by this form to keep slider interaction stable.
    if (localMarkdownRef.current && localMarkdownRef.current === markdown) {
      localMarkdownRef.current = null;
      return;
    }

    const data = parseYamlFrontmatter(markdown);
    if (data.hasFrontmatter) {
      setConfig((prev) => ({
        ...prev,
        ...DEFAULT_CONFIG,
        ...data.config,
      }));
    }
  }, [markdown]);

  const hasChanges = useMemo(() => {
    const currentConfig = {
      ...DEFAULT_CONFIG,
      ...initialData.config,
    };
    return JSON.stringify(config) !== JSON.stringify(currentConfig);
  }, [config, initialData.config]);

  const persistConfig = useCallback((nextConfig: PlanConfig): boolean => {
    const validationErrors = validateConfig(nextConfig);
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      return false;
    }

    const { config: existingConfig, content } = parseYamlFrontmatter(markdown);
    const mergedConfig: Partial<PlanConfig> = { ...existingConfig, ...nextConfig };

    if (!mergedConfig.title) {
      delete (mergedConfig as Partial<PlanConfig>).title;
    }
    if (!mergedConfig.topic) {
      delete (mergedConfig as Partial<PlanConfig>).topic;
    }

    const newMarkdown = serializeYamlFrontmatter(mergedConfig, content);
    localMarkdownRef.current = newMarkdown;
    onMarkdownChange(newMarkdown);
    return true;
  }, [markdown, onMarkdownChange]);

  // Update a single config field
  const updateField = useCallback(<K extends keyof PlanConfig>(
    key: K,
    value: PlanConfig[K]
  ) => {
    const next = { ...config, [key]: value };
    setConfig(next);
    persistConfig(next);
  }, [config, persistConfig]);

  // Toggle a search source
  const toggleSearchSource = useCallback((source: SearchSource) => {
    const sources = config.search_sources.includes(source)
      ? config.search_sources.filter((s) => s !== source)
      : [...config.search_sources, source];
    const next = { ...config, search_sources: sources };
    setConfig(next);
    persistConfig(next);
  }, [config, persistConfig]);

  // Handle save
  const handleSave = useCallback(() => {
    persistConfig(config);
  }, [config, persistConfig]);

  // Handle reset
  const handleReset = useCallback(() => {
    const { config: existingConfig } = parseYamlFrontmatter(markdown);
    setConfig({
      ...DEFAULT_CONFIG,
      ...existingConfig,
    });
    setErrors({});
  }, [markdown]);

  // Toggle expanded state
  const toggleExpanded = useCallback(() => {
    setExpanded((prev) => !prev);
  }, []);

  return (
    <section
      className={`plan-config-form ${expanded ? "expanded" : ""} ${
        disabled ? "disabled" : ""
      } ${className}`}
      aria-label="研究方案配置"
    >
      {/* Header */}
      <header className="config-form-header">
        <button
          type="button"
          className="config-form-toggle"
          onClick={toggleExpanded}
          aria-expanded={expanded}
          aria-controls="config-form-content"
          disabled={disabled}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
            className={`config-chevron ${expanded ? "rotated" : ""}`}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
          <span className="config-form-title">
            研究配置
            {hasChanges && (
              <span className="unsaved-indicator">
                *
              </span>
            )}
          </span>
        </button>
      </header>

      {/* Form Content */}
      {expanded && (
        <div id="config-form-content" className="config-form-content">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSave();
            }}
            noValidate
          >
            {/* Title Field */}
            <div className="config-field">
              <label htmlFor="config-title" className="config-label">
                标题
                <span className="config-label-hint">（AI生成，可编辑）</span>
              </label>
              <input
                id="config-title"
                type="text"
                className="config-input"
                value={config.title}
                onChange={(e) => updateField("title", e.target.value)}
                onBlur={() => {
                  const titleError = validateConfig({ ...config, title: config.title }).title;
                  setErrors((prev) => ({
                    ...prev,
                    title: titleError,
                  }));
                }}
                disabled={disabled}
                placeholder="AI将自动生成标题"
                aria-invalid={!!errors.title}
                aria-describedby={
                  errors.title ? "config-title-error" : "config-title-hint"
                }
              />
              {errors.title ? (
                <p id="config-title-error" className="config-error" role="alert">
                  {errors.title}
                </p>
              ) : (
                <p id="config-title-hint" className="config-hint">
                  研究方案的标题，AI会根据主题自动生成
                </p>
              )}
            </div>

            {/* Topic Field */}
            <div className="config-field">
              <label htmlFor="config-topic" className="config-label">
                研究主题
                <span className="config-label-hint">（AI生成，可编辑）</span>
              </label>
              <input
                id="config-topic"
                type="text"
                className="config-input"
                value={config.topic}
                onChange={(e) => updateField("topic", e.target.value)}
                onBlur={() => {
                  const topicError = validateConfig({ ...config, topic: config.topic }).topic;
                  setErrors((prev) => ({
                    ...prev,
                    topic: topicError,
                  }));
                }}
                disabled={disabled}
                placeholder="AI将自动生成研究主题"
                aria-invalid={!!errors.topic}
                aria-describedby={
                  errors.topic ? "config-topic-error" : "config-topic-hint"
                }
              />
              {errors.topic ? (
                <p id="config-topic-error" className="config-error" role="alert">
                  {errors.topic}
                </p>
              ) : (
                <p id="config-topic-hint" className="config-hint">
                  描述研究的核心问题，AI会根据您的需求自动生成
                </p>
              )}
            </div>

            {/* Numeric Fields Row */}
            <div className="config-field-row">
              {/* Max Depth Field */}
              <div className="config-field config-field-compact">
                <label htmlFor="config-max-depth" className="config-label">
                  最大深度
                  <span className="config-value-display">
                    {config.max_depth}
                  </span>
                </label>
                <div className="config-slider-wrapper">
                  <input
                    id="config-max-depth"
                    type="range"
                    className="config-slider"
                    min="1"
                    max="5"
                    step="1"
                    value={config.max_depth}
                    onChange={(e) => updateField("max_depth", parseInt(e.target.value, 10))}
                    disabled={disabled}
                    aria-invalid={!!errors.max_depth}
                    aria-describedby={
                      errors.max_depth ? "config-max-depth-error" : "config-max-depth-hint"
                    }
                  />
                  <div className="config-slider-marks">
                    <span>1</span>
                    <span>2</span>
                    <span>3</span>
                    <span>4</span>
                    <span>5</span>
                  </div>
                </div>
                {errors.max_depth && (
                  <p id="config-max-depth-error" className="config-error" role="alert">
                    {errors.max_depth}
                  </p>
                )}
              </div>

              {/* Max Nodes Field */}
              <div className="config-field config-field-compact">
                <label htmlFor="config-max-nodes" className="config-label">
                  最大节点
                  <span className="config-value-display">
                    {config.max_nodes}
                  </span>
                </label>
                <div className="config-slider-wrapper">
                  <input
                    id="config-max-nodes"
                    type="range"
                    className="config-slider"
                    min="1"
                    max="20"
                    step="1"
                    value={config.max_nodes}
                    onChange={(e) => updateField("max_nodes", parseInt(e.target.value, 10))}
                    disabled={disabled}
                    aria-invalid={!!errors.max_nodes}
                    aria-describedby={
                      errors.max_nodes ? "config-max-nodes-error" : "config-max-nodes-hint"
                    }
                  />
                  <div className="config-slider-marks">
                    <span>1</span>
                    <span>5</span>
                    <span>10</span>
                    <span>15</span>
                    <span>20</span>
                  </div>
                </div>
                {errors.max_nodes && (
                  <p id="config-max-nodes-error" className="config-error" role="alert">
                    {errors.max_nodes}
                  </p>
                )}
              </div>

              {/* Priority Field */}
              <div className="config-field config-field-compact">
                <label htmlFor="config-priority" className="config-label">
                  优先级
                  <span className="config-value-display">
                    {config.priority}
                  </span>
                </label>
                <div className="config-slider-wrapper">
                  <input
                    id="config-priority"
                    type="range"
                    className="config-slider"
                    min="1"
                    max="10"
                    step="1"
                    value={config.priority}
                    onChange={(e) => updateField("priority", parseInt(e.target.value, 10))}
                    disabled={disabled}
                    aria-invalid={!!errors.priority}
                    aria-describedby={
                      errors.priority ? "config-priority-error" : "config-priority-hint"
                    }
                  />
                  <div className="config-slider-marks">
                    <span>1</span>
                    <span>3</span>
                    <span>5</span>
                    <span>7</span>
                    <span>10</span>
                  </div>
                </div>
                {errors.priority && (
                  <p id="config-priority-error" className="config-error" role="alert">
                    {errors.priority}
                  </p>
                )}
              </div>

              {/* Target Word Count Field */}
              <div className="config-field config-field-compact">
                <label htmlFor="config-word-count" className="config-label">
                  期望字数
                  <span className="config-value-display">
                    {(config.target_word_count ?? 5000).toLocaleString()}
                  </span>
                </label>
                <div className="config-slider-wrapper">
                  <input
                    id="config-word-count"
                    type="range"
                    className="config-slider"
                    min="1000"
                    max="50000"
                    step="1000"
                    value={config.target_word_count ?? 5000}
                    onChange={(e) => updateField("target_word_count", parseInt(e.target.value, 10))}
                    disabled={disabled}
                    aria-invalid={!!errors.target_word_count}
                    aria-describedby={
                      errors.target_word_count ? "config-word-count-error" : "config-word-count-hint"
                    }
                  />
                  <div className="config-slider-marks">
                    <span>1K</span>
                    <span>10K</span>
                    <span>25K</span>
                    <span>50K</span>
                  </div>
                </div>
                {errors.target_word_count ? (
                  <p id="config-word-count-error" className="config-error" role="alert">
                    {errors.target_word_count}
                  </p>
                ) : (
                  <p id="config-word-count-hint" className="config-hint">
                    最终字数允许 ±20% 浮动
                  </p>
                )}
              </div>
            </div>

            {/* Search Sources Field */}
            <fieldset
              className="config-fieldset"
              disabled={disabled}
              aria-invalid={!!errors.search_sources}
            >
              <legend className="config-legend">
                搜索来源
                <span className="config-label-hint">（多选）</span>
              </legend>
              <div className="config-checkbox-group">
                {SEARCH_SOURCE_OPTIONS.map((source) => (
                  <label
                    key={source}
                    className={`config-checkbox ${config.search_sources.includes(source) ? "checked" : ""}`}
                  >
                    <input
                      type="checkbox"
                      className="config-checkbox-input"
                      checked={config.search_sources.includes(source)}
                      onChange={() => toggleSearchSource(source)}
                      disabled={disabled}
                    />
                    <span className="config-checkbox-label">{source}</span>
                  </label>
                ))}
              </div>
              {errors.search_sources && (
                <p className="config-error" role="alert">
                  {errors.search_sources}
                </p>
              )}
            </fieldset>

            {showResetButton && (
              <div className="config-form-actions" role="toolbar" aria-label="表单操作">
                <button
                  type="button"
                  className="ghost"
                  onClick={handleReset}
                  disabled={disabled || !hasChanges}
                >
                  重置
                </button>
              </div>
            )}
          </form>
        </div>
      )}
    </section>
  );
}
