import { useMemo } from "react";
import type { ConversationMessage, ConversationStatus } from "../types";

/**
 * Progress entry structure for PROGRESS_GROUP messages.
 */
export interface ProgressEntry {
  summary: string;
  phase: string;
  state: string;
  progress: number | null;
}

/**
 * Progress bundle structure that aggregates multiple progress messages.
 */
export interface ProgressBundle {
  bundleKey: string;
  taskId: string | null;
  hostMessageId: string;
  role: ConversationMessage["role"];
  createdAt: string;
  collapsed: boolean;
  latestSummary: string;
  latestProgress: number | null;
  entries: ProgressEntry[];
}

const PROGRESS_BUNDLE_KEY = "__progress_bundle__";

/**
 * Convert raw entries from message metadata to ProgressEntry array.
 */
function toProgressEntries(message: ConversationMessage): ProgressEntry[] {
  const rawEntries = message.metadata.entries;
  if (!Array.isArray(rawEntries)) return [];
  const parsed: ProgressEntry[] = [];
  for (const item of rawEntries) {
    if (!item || typeof item !== "object") continue;
    const value = item as Record<string, unknown>;
    parsed.push({
      summary: typeof value.summary === "string" ? value.summary : "进度更新",
      phase: typeof value.phase === "string" ? value.phase : "UNKNOWN",
      state: typeof value.state === "string" ? value.state : "UNKNOWN",
      progress: typeof value.progress === "number" ? value.progress : null,
    });
  }
  return parsed;
}

/**
 * Convert unknown value to valid progress number (0-100).
 */
function toProgressNumber(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const rounded = Math.round(value);
  return Math.min(100, Math.max(0, rounded));
}

/**
 * Check if a message kind is a plan message.
 */
function isPlanMessage(kind: ConversationMessage["kind"]): boolean {
  return kind === "PLAN_DRAFT" || kind === "PLAN_REVISION" || kind === "PLAN_EDITED";
}

/**
 * Extract taskId from message metadata.
 */
function extractMessageTaskId(message: ConversationMessage): string | null {
  const directTaskId = message.metadata.taskId;
  if (typeof directTaskId === "string" && directTaskId.trim()) {
    return directTaskId.trim();
  }
  const rawEntries = message.metadata.entries;
  if (!Array.isArray(rawEntries)) return null;
  for (let i = rawEntries.length - 1; i >= 0; i -= 1) {
    const entry = rawEntries[i];
    if (!entry || typeof entry !== "object") continue;
    const raw = (entry as Record<string, unknown>).raw;
    if (!raw || typeof raw !== "object") continue;
    const taskId = (raw as Record<string, unknown>).taskId;
    if (typeof taskId === "string" && taskId.trim()) {
      return taskId.trim();
    }
  }
  return null;
}

/**
 * Options for useMessageTimeline hook.
 */
export interface UseMessageTimelineOptions {
  messages: ConversationMessage[];
  currentTaskId: string | null;
  activeStatus: ConversationStatus | null;
  showHistoryRounds: boolean;
}

/**
 * Return type for useMessageTimeline hook.
 */
export interface UseMessageTimelineResult {
  /** Mapping from message ID to task ID */
  taskIdByMessageId: Map<string, string | null>;
  /** Array of historical task IDs (excluding current task) */
  historyTaskIds: string[];
  /** Messages visible in the timeline (filtered by history rounds toggle) */
  visibleMessages: ConversationMessage[];
  /** ID of the latest plan message */
  latestPlanMessageId: string | null;
  /** Aggregated progress bundles by task */
  progressBundles: Map<string, ProgressBundle>;
}

/**
 * Custom hook for computing message timeline data.
 * Extracts complex memoization logic from ChatTimeline component.
 */
export function useMessageTimeline(
  options: UseMessageTimelineOptions
): UseMessageTimelineResult {
  const { messages, currentTaskId, activeStatus, showHistoryRounds } = options;

  // All messages in order (identity for now, but allows for future sorting)
  const ordered = useMemo(() => messages, [messages]);

  // Mapping from message ID to task ID
  const taskIdByMessageId = useMemo(() => {
    const mapping = new Map<string, string | null>();
    for (const message of ordered) {
      mapping.set(message.messageId, extractMessageTaskId(message));
    }
    return mapping;
  }, [ordered]);

  // Historical task IDs (excluding current task)
  const historyTaskIds = useMemo(() => {
    if (!currentTaskId) return [];
    const ids = new Set<string>();
    for (const message of ordered) {
      const taskId = taskIdByMessageId.get(message.messageId);
      if (taskId && taskId !== currentTaskId) {
        ids.add(taskId);
      }
    }
    return Array.from(ids);
  }, [ordered, taskIdByMessageId, currentTaskId]);

  // Messages visible in timeline (filtered by history rounds toggle)
  const visibleMessages = useMemo(() => {
    if (showHistoryRounds || !currentTaskId) {
      return ordered;
    }
    return ordered.filter((message) => {
      const taskId = taskIdByMessageId.get(message.messageId);
      return !taskId || taskId === currentTaskId;
    });
  }, [ordered, taskIdByMessageId, currentTaskId, showHistoryRounds]);

  // Latest plan message ID
  const latestPlanMessageId = useMemo(() => {
    for (let i = visibleMessages.length - 1; i >= 0; i -= 1) {
      if (isPlanMessage(visibleMessages[i].kind)) {
        return visibleMessages[i].messageId;
      }
    }
    return null;
  }, [visibleMessages]);

  // Progress bundles aggregated by task
  const progressBundles = useMemo<Map<string, ProgressBundle>>(() => {
    const bundles = new Map<string, ProgressBundle>();
    const progressMessages = visibleMessages.filter(
      (item) => item.kind === "PROGRESS_GROUP"
    );
    if (progressMessages.length === 0) return bundles;

    for (const progressMessage of progressMessages) {
      const taskId = taskIdByMessageId.get(progressMessage.messageId);
      const taskKey = taskId ?? "__no_task__";
      let bundle = bundles.get(taskKey);
      if (!bundle) {
        bundle = {
          bundleKey: `${PROGRESS_BUNDLE_KEY}:${taskKey}`,
          taskId: taskId ?? null,
          hostMessageId: progressMessage.messageId,
          role: progressMessage.role,
          createdAt: progressMessage.createdAt,
          collapsed: progressMessage.collapsed,
          latestSummary: progressMessage.content || "研究进行中",
          latestProgress: null,
          entries: [],
        };
        bundles.set(taskKey, bundle);
      } else {
        bundle.createdAt = progressMessage.createdAt;
        bundle.collapsed = bundle.collapsed && progressMessage.collapsed;
      }

      const messageEntries = toProgressEntries(progressMessage);
      bundle.entries.push(...messageEntries);
      for (const entry of messageEntries) {
        if (
          entry.progress !== null &&
          (bundle.latestProgress === null || entry.progress >= bundle.latestProgress)
        ) {
          bundle.latestProgress = entry.progress;
          bundle.latestSummary = entry.summary;
        }
      }
      const metadataProgress = toProgressNumber(progressMessage.metadata.latestProgress);
      if (
        metadataProgress !== null &&
        (bundle.latestProgress === null || metadataProgress >= bundle.latestProgress)
      ) {
        bundle.latestProgress = metadataProgress;
        const metadataSummary = progressMessage.metadata.latestSummary;
        if (typeof metadataSummary === "string" && metadataSummary.trim()) {
          bundle.latestSummary = metadataSummary;
        } else if (progressMessage.content.trim()) {
          bundle.latestSummary = progressMessage.content;
        }
      }
    }
    // Set progress to 100% for completed tasks
    for (const bundle of bundles.values()) {
      if (bundle.taskId === currentTaskId && activeStatus === "COMPLETED") {
        bundle.latestProgress = 100;
      }
    }
    return bundles;
  }, [visibleMessages, taskIdByMessageId, currentTaskId, activeStatus]);

  return {
    taskIdByMessageId,
    historyTaskIds,
    visibleMessages,
    latestPlanMessageId,
    progressBundles,
  };
}

/**
 * Check if a message kind is a plan-related message.
 */
export function isPlanMessageKind(kind: ConversationMessage["kind"]): boolean {
  return isPlanMessage(kind);
}

/**
 * Get role label for display.
 */
export function roleLabel(role: ConversationMessage["role"]): string {
  if (role === "assistant") return "Agent";
  if (role === "system") return "System";
  return "你";
}