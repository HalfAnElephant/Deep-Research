/**
 * YAML Frontmatter utilities for parsing and serializing plan configuration
 */

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
