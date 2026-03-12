/**
 * Global constants for the Deep Research frontend
 */

import type { ConversationStatus } from "./types";

/**
 * Human-readable labels for conversation statuses
 */
export const STATUS_LABEL: Record<ConversationStatus, string> = {
  DRAFTING_PLAN: "草稿生成中",
  PLAN_READY: "方案可执行",
  RUNNING: "处理中",
  COMPLETED: "研究完成",
  FAILED: "执行失败",
};

/**
 * Status descriptions for tooltips and aria-labels
 */
export const STATUS_DESCRIPTION: Record<ConversationStatus, string> = {
  DRAFTING_PLAN: "Agent 正在生成研究方案",
  PLAN_READY: "方案已就绪，可以开始研究",
  RUNNING: "研究任务正在执行中",
  COMPLETED: "研究已完成",
  FAILED: "执行失败，请重试",
};

/**
 * App configuration constants
 */
export const APP_CONFIG = {
  FIRST_MESSAGE_LIMIT: 500,
  LEFT_SIDEBAR_KEY: "dr:left-sidebar-visible",
  RIGHT_SIDEBAR_KEY: "dr:right-sidebar-visible",
  WS_BASE_BACKOFF_MS: 1200,
  WS_MAX_RETRY: 4,
} as const;

/**
 * Default research task configuration
 */
export const DEFAULT_TASK_CONFIG = {
  maxDepth: 2,
  maxNodes: 8,
  searchSources: ["Web Search", "arXiv", "Semantic Scholar"],
  priority: 4,
} as const;
