import { useState, useCallback, useMemo } from "react";
import type {
  ConversationDetail,
  ConversationMessage,
  ConversationStatus,
  ConversationSummary,
} from "../types";

const STATUS_LABEL: Record<ConversationStatus, string> = {
  DRAFTING_PLAN: "草稿生成中",
  PLAN_READY: "方案可执行",
  RUNNING: "处理中",
  COMPLETED: "研究完成",
  FAILED: "执行失败",
};

interface PendingAssistantBubble {
  conversationId: string | null;
  content: string;
}

/**
 * Custom hook for managing conversation state.
 * Handles conversation list, active conversation, draft mode, and pending assistant messages.
 */
export function useConversationState() {
  // Conversation list state
  const [summaries, setSummaries] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [activeDetail, setActiveDetail] = useState<ConversationDetail | null>(null);

  // Draft mode state
  const [draftMode, setDraftMode] = useState(false);
  const [draftMessages, setDraftMessages] = useState<ConversationMessage[]>([]);

  // Pending assistant bubble for loading state
  const [pendingAssistantBubble, setPendingAssistantBubble] =
    useState<PendingAssistantBubble | null>(null);

  // Derived state
  const activeStatus = activeDetail?.status ?? null;
  const statusLabel = draftMode
    ? "等待输入研究主题"
    : activeStatus
      ? STATUS_LABEL[activeStatus]
      : "未选择会话";

  const activeSummary = useMemo(
    () => summaries.find((item) => item.conversationId === activeConversationId) ?? null,
    [summaries, activeConversationId]
  );

  const timelineMessages = useMemo(() => {
    if (activeDetail) return activeDetail.messages;
    if (draftMode && !activeConversationId) return draftMessages;
    return [];
  }, [activeDetail, draftMode, activeConversationId, draftMessages]);

  const pendingAssistantText = useMemo(() => {
    if (!pendingAssistantBubble) return null;
    if (pendingAssistantBubble.conversationId === null) {
      return draftMode && !activeConversationId ? pendingAssistantBubble.content : null;
    }
    return pendingAssistantBubble.conversationId === activeConversationId
      ? pendingAssistantBubble.content
      : null;
  }, [pendingAssistantBubble, draftMode, activeConversationId]);

  const composerDisabled =
    activeStatus === "RUNNING" ||
    activeStatus === "DRAFTING_PLAN" ||
    (!activeConversationId && !draftMode);

  /**
   * Start a new draft conversation.
   */
  const startDraftMode = useCallback(() => {
    setDraftMode(true);
    setActiveConversationId(null);
    setActiveDetail(null);
    setDraftMessages([]);
    setPendingAssistantBubble(null);
  }, []);

  /**
   * Exit draft mode and select an existing conversation.
   */
  const selectConversation = useCallback((conversationId: string) => {
    setDraftMode(false);
    setActiveConversationId(conversationId);
    setDraftMessages([]);
    setPendingAssistantBubble((prev) =>
      prev?.conversationId === null ? null : prev
    );
  }, []);

  /**
   * Clear active conversation state.
   */
  const clearActiveConversation = useCallback(() => {
    setActiveConversationId(null);
    setActiveDetail(null);
    setDraftMessages([]);
    setPendingAssistantBubble(null);
  }, []);

  /**
   * Reset all conversation state.
   */
  const resetAllState = useCallback(() => {
    setSummaries([]);
    setActiveConversationId(null);
    setActiveDetail(null);
    setDraftMode(false);
    setDraftMessages([]);
    setPendingAssistantBubble(null);
  }, []);

  /**
   * Update pending assistant bubble for loading state.
   */
  const setPendingAssistant = useCallback(
    (conversationId: string | null, content: string) => {
      setPendingAssistantBubble({ conversationId, content });
    },
    []
  );

  /**
   * Clear pending assistant bubble.
   */
  const clearPendingAssistant = useCallback(() => {
    setPendingAssistantBubble(null);
  }, []);

  /**
   * Clear pending assistant for a specific conversation.
   */
  const clearPendingAssistantForConversation = useCallback((conversationId: string) => {
    setPendingAssistantBubble((prev) =>
      prev?.conversationId === conversationId ? null : prev
    );
  }, []);

  return {
    // State
    summaries,
    activeConversationId,
    activeDetail,
    draftMode,
    draftMessages,
    pendingAssistantBubble,
    activeStatus,
    statusLabel,
    activeSummary,
    timelineMessages,
    pendingAssistantText,
    composerDisabled,

    // Setters
    setSummaries,
    setActiveConversationId,
    setActiveDetail,
    setDraftMode,
    setDraftMessages,
    setPendingAssistantBubble,

    // Actions
    startDraftMode,
    selectConversation,
    clearActiveConversation,
    resetAllState,
    setPendingAssistant,
    clearPendingAssistant,
    clearPendingAssistantForConversation,
  };
}