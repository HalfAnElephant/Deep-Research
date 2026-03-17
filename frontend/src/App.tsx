import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  connectProgressWs,
  createConversation,
  deleteAllConversations,
  deleteConversation,
  downloadConversationReport,
  getConversation,
  listConversations,
  renameConversation,
  reviseConversationPlan,
  runConversation,
  updateConversationPlan
} from "./api";
import { AgentStatusPanel } from "./components/AgentStatusPanel";
import { ChatTimeline } from "./components/ChatTimeline";
import { Composer } from "./components/Composer";
import { ConversationSidebar } from "./components/ConversationSidebar";
import { Dialog } from "./components/Dialog";
import { ExportModal } from "./components/ExportModal";
import { LibraryPage } from "./components/LibraryPage";
import { PlanEditorPane } from "./components/PlanEditorPane";
import { WorkflowNavigator } from "./components/WorkflowNavigator";
import { APP_CONFIG, STATUS_LABEL } from "./constants";
import type {
  AgentState,
  AgentType,
  ConversationDetail,
  ConversationMessage,
  ConversationStatus,
  ConversationSummary,
  ProgressEvent,
} from "./types";

const FIRST_MESSAGE_LIMIT = APP_CONFIG.FIRST_MESSAGE_LIMIT;
const REFRESH_INTERVAL_MS = Number(import.meta.env.VITE_CONVERSATION_REFRESH_MS ?? "2500");
const LEFT_SIDEBAR_KEY = APP_CONFIG.LEFT_SIDEBAR_KEY;
const RIGHT_SIDEBAR_KEY = APP_CONFIG.RIGHT_SIDEBAR_KEY;
const WS_BASE_BACKOFF_MS = APP_CONFIG.WS_BASE_BACKOFF_MS;
const WS_MAX_RETRY = APP_CONFIG.WS_MAX_RETRY;

type StreamStatus = "idle" | "connecting" | "connected" | "reconnecting" | "fallback";

const DEFAULT_CONFIG = {
  maxDepth: 2,
  maxNodes: 8,
  searchSources: ["Web Search", "arXiv", "Semantic Scholar"],
  priority: 4
};

function toErrorText(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

function getActiveAgentPhases(agents: AgentState[]): AgentType[] {
  return agents
    .filter((agent) => agent.status === "RUNNING")
    .map((agent) => agent.agentType);
}

function readStoredFlag(key: string, fallback: boolean): boolean {
  if (typeof window === "undefined") return fallback;
  const raw = window.localStorage.getItem(key);
  if (raw === "1") return true;
  if (raw === "0") return false;
  return fallback;
}

function isProgressEventKind(event: string): boolean {
  return event === "TASK_PROGRESS" || event === "TASK_HEARTBEAT" || event === "STALL_WARNING";
}

function summarizeRealtimeEvent(data: Record<string, unknown>, event: string): string {
  const state = typeof data.state === "string" ? data.state : "RUNNING";
  const phase = typeof data.phase === "string" ? data.phase : event;
  const detail = typeof data.detail === "string" ? data.detail.trim() : "";
  const writingContent = typeof data.currentWritingContent === "string" ? data.currentWritingContent.trim() : "";
  const nodeTitle = typeof data.currentNodeTitle === "string" ? data.currentNodeTitle.trim() : "";
  const sectionTitle = typeof data.currentSectionTitle === "string" ? data.currentSectionTitle.trim() : "";
  const rawProgress = data.progress;
  const progressText = typeof rawProgress === "number" ? `${Math.max(0, Math.min(100, Math.round(rawProgress)))}%` : "--";
  if (event === "STALL_WARNING" && detail) {
    return `[${state}/STALL_WARNING] ${progressText} ${detail}`;
  }
  if (detail) {
    return `[${state}/${phase}] ${progressText} ${detail}`;
  }
  if (writingContent) {
    return `[${state}/${phase}] ${progressText} 写作内容：${writingContent}`;
  }
  if (sectionTitle) {
    return `[${state}/${phase}] ${progressText} 正在写作：${sectionTitle}`;
  }
  if (nodeTitle) {
    return `[${state}/${phase}] ${progressText} 节点：${nodeTitle}`;
  }
  return `[${state}/${phase}] ${progressText}`;
}

function deriveAgentStatesFromMessages(messages: ConversationMessage[]): AgentState[] {
  const base: AgentState[] = [
    { agentType: "IDEATION", status: "IDLE", progress: 0, currentActivity: "等待任务开始" },
    { agentType: "PLANNING", status: "IDLE", progress: 0, currentActivity: "等待任务开始" },
    { agentType: "WRITING", status: "IDLE", progress: 0, currentActivity: "等待任务开始" },
    { agentType: "CHECKING", status: "IDLE", progress: 0, currentActivity: "等待任务开始" },
  ];
  const latestProgress = [...messages]
    .reverse()
    .find((message) => message.kind === "PROGRESS_GROUP");
  if (!latestProgress) return base;

  const entries = Array.isArray(latestProgress.metadata.entries) ? latestProgress.metadata.entries : [];
  const latest = entries.length > 0 ? entries[entries.length - 1] as Record<string, unknown> : latestProgress.metadata;
  const latestRaw = (latest.raw && typeof latest.raw === "object") ? latest.raw as Record<string, unknown> : {};

  if (typeof latestRaw.agentType === "string") {
    const normalizedType = latestRaw.agentType.toUpperCase() as AgentType;
    if (base.some((agent) => agent.agentType === normalizedType)) {
      const normalizedStatus = typeof latestRaw.status === "string" ? latestRaw.status.toUpperCase() : "RUNNING";
      return base.map((agent) => {
        if (agent.agentType !== normalizedType) return agent;
        return {
          ...agent,
          status: normalizedStatus === "FAILED" ? "FAILED" : normalizedStatus === "COMPLETED" ? "COMPLETED" : "RUNNING",
          progress: typeof latestRaw.progress === "number" ? Math.max(0, Math.min(100, Math.round(latestRaw.progress))) : agent.progress,
          currentActivity: typeof latestRaw.currentActivity === "string" && latestRaw.currentActivity.trim()
            ? latestRaw.currentActivity
            : "处理中",
        };
      });
    }
  }

  const phase = typeof latest.phase === "string" ? latest.phase.toUpperCase() : "";
  const state = typeof latest.state === "string" ? latest.state.toUpperCase() : "RUNNING";
  const detail = typeof latest.detail === "string" ? latest.detail : latestProgress.content;
  const progress = typeof latest.progress === "number" ? Math.max(0, Math.min(100, Math.round(latest.progress))) : 0;

  const runningAgent: AgentType =
    phase.includes("WRIT") || phase.includes("SYNTH") || phase.includes("FINAL")
      ? "WRITING"
      : phase.includes("REVIEW") || phase.includes("CHECK")
        ? "CHECKING"
        : phase.includes("PLAN") || phase.includes("BUILD")
          ? "PLANNING"
          : "IDEATION";

  const updated = base.map((agent) => {
    if (agent.agentType === runningAgent) {
      return {
        ...agent,
        status: state === "FAILED" ? "FAILED" : state === "COMPLETED" ? "COMPLETED" : "RUNNING",
        progress,
        currentActivity: detail || "处理中",
      };
    }
    if (agent.agentType === "IDEATION" && runningAgent !== "IDEATION") {
      return { ...agent, status: "COMPLETED", progress: 100, currentActivity: "阶段完成" };
    }
    if (agent.agentType === "PLANNING" && (runningAgent === "WRITING" || runningAgent === "CHECKING")) {
      return { ...agent, status: "COMPLETED", progress: 100, currentActivity: "阶段完成" };
    }
    if (agent.agentType === "WRITING" && runningAgent === "CHECKING") {
      return { ...agent, status: "COMPLETED", progress: 100, currentActivity: "阶段完成" };
    }
    if (agent.agentType === "CHECKING" && state === "COMPLETED") {
      return { ...agent, status: "COMPLETED", progress: 100, currentActivity: "阶段完成" };
    }
    return agent;
  });
  return updated;
}

interface PendingAssistantBubble {
  conversationId: string | null;
  content: string;
}

type ConfirmDialogState =
  | {
      kind: "deleteConversation";
      conversationId: string;
      topic: string;
    }
  | {
      kind: "deleteAll";
      total: number;
    };

interface RenameDialogState {
  conversationId: string;
  value: string;
}

export function App() {
  const [summaries, setSummaries] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [activeDetail, setActiveDetail] = useState<ConversationDetail | null>(null);
  const [draftMode, setDraftMode] = useState(false);
  const [draftMessages, setDraftMessages] = useState<ConversationMessage[]>([]);
  const [pendingAssistantBubble, setPendingAssistantBubble] = useState<PendingAssistantBubble | null>(null);

  const [composerText, setComposerText] = useState("");
  const [planDraft, setPlanDraft] = useState("");
  const [draftDirty, setDraftDirty] = useState(false);

  const [sending, setSending] = useState(false);
  const [saving, setSaving] = useState(false);
  const [starting, setStarting] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);
  const [deletingConversationId, setDeletingConversationId] = useState<string | null>(null);
  const [renamingConversationId, setRenamingConversationId] = useState<string | null>(null);
  const [deletingAll, setDeletingAll] = useState(false);
  const [refreshingList, setRefreshingList] = useState(false);
  const [error, setError] = useState("");
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState | null>(null);
  const [renameDialog, setRenameDialog] = useState<RenameDialogState | null>(null);

  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [mobileEditorOpen, setMobileEditorOpen] = useState(false);
  const [leftSidebarVisible, setLeftSidebarVisible] = useState(() => readStoredFlag(LEFT_SIDEBAR_KEY, true));
  const [rightSidebarVisible, setRightSidebarVisible] = useState(() => readStoredFlag(RIGHT_SIDEBAR_KEY, false));
  const [streamStatus, setStreamStatus] = useState<StreamStatus>("idle");
  const [lastProgressEventAt, setLastProgressEventAt] = useState<string | null>(null);
  const [currentPhase, setCurrentPhase] = useState<string | null>(null);
  const [streamClock, setStreamClock] = useState(() => Date.now());
  const [showLibrary, setShowLibrary] = useState(false);

  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const progressWsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const draftDirtyRef = useRef(false);

  const setDraftDirtyState = useCallback((value: boolean) => {
    draftDirtyRef.current = value;
    setDraftDirty(value);
  }, []);

  const activeStatus = activeDetail?.status ?? null;
  const statusLabel = draftMode ? "等待输入研究主题" : activeStatus ? STATUS_LABEL[activeStatus] : "未选择会话";
  const composerDisabled = activeStatus === "RUNNING" || activeStatus === "DRAFTING_PLAN" || (!activeConversationId && !draftMode);

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
    return pendingAssistantBubble.conversationId === activeConversationId ? pendingAssistantBubble.content : null;
  }, [pendingAssistantBubble, draftMode, activeConversationId]);

  const effectiveAgentStates = useMemo(() => {
    if (!activeDetail) return [] as AgentState[];
    if (activeDetail.agentStates && activeDetail.agentStates.length > 0) {
      return activeDetail.agentStates;
    }
    return deriveAgentStatesFromMessages(activeDetail.messages);
  }, [activeDetail]);

  const idleSeconds = useMemo(() => {
    if (!lastProgressEventAt) return 0;
    const delta = streamClock - Date.parse(lastProgressEventAt);
    if (!Number.isFinite(delta) || delta < 0) return 0;
    return Math.floor(delta / 1000);
  }, [lastProgressEventAt, streamClock]);

  const refreshConversations = useCallback(async (options?: { autoSelectFirst?: boolean }) => {
    setRefreshingList(true);
    try {
      const items = await listConversations();
      setSummaries(items);
      if (options?.autoSelectFirst && !activeConversationId && !draftMode && items.length > 0) {
        setActiveConversationId(items[0].conversationId);
      }
      if (activeConversationId && !items.some((item) => item.conversationId === activeConversationId)) {
        setActiveConversationId(null);
        setActiveDetail(null);
        setPendingAssistantBubble((prev) => (prev?.conversationId === activeConversationId ? null : prev));
      }
    } catch (err) {
      setError(toErrorText(err));
    } finally {
      setRefreshingList(false);
    }
  }, [activeConversationId, draftMode]);

  const refreshConversationDetail = useCallback(async (
    conversationId: string,
    options?: { syncDraft?: boolean; forceDraft?: boolean }
  ) => {
    try {
      const detail = await getConversation(conversationId);
      setActiveDetail(detail);
      setPendingAssistantBubble((prev) => {
        if (detail.status === "DRAFTING_PLAN") {
          if (!prev || prev.conversationId === conversationId || prev.conversationId === null) {
            return {
              conversationId,
              content: prev?.content ?? "正在规划中，请等待，方案生成后会自动显示。"
            };
          }
          return prev;
        }
        if (!prev) return prev;
        if (prev.conversationId === conversationId || prev.conversationId === null) {
          return null;
        }
        return prev;
      });
      const currentPlan = detail.currentPlan;
      if (!currentPlan) return;
      const shouldSync =
        Boolean(options?.forceDraft) ||
        Boolean(options?.syncDraft) ||
        !draftDirtyRef.current;
      if (shouldSync) {
        setPlanDraft(currentPlan.markdown);
        setDraftDirtyState(false);
      }
    } catch (err) {
      setError(toErrorText(err));
    }
  }, [setDraftDirtyState]);

  useEffect(() => {
    if (activeStatus !== "RUNNING") return;
    const timer = window.setInterval(() => {
      setStreamClock(Date.now());
    }, 1000);
    return () => window.clearInterval(timer);
  }, [activeStatus]);

  useEffect(() => {
    void refreshConversations({ autoSelectFirst: true });
  }, [refreshConversations]);

  useEffect(() => {
    if (!activeConversationId) return;
    void refreshConversationDetail(activeConversationId, { syncDraft: true });
  }, [activeConversationId, refreshConversationDetail]);

  // Reset current phase when conversation changes or task completes
  useEffect(() => {
    if (!activeConversationId || activeStatus === "COMPLETED" || activeStatus === "FAILED") {
      setCurrentPhase(null);
    }
  }, [activeConversationId, activeStatus]);

  useEffect(() => {
    if (!activeConversationId || (activeStatus !== "RUNNING" && activeStatus !== "DRAFTING_PLAN")) return;
    const shouldPollRunning = activeStatus === "RUNNING" && streamStatus === "fallback";
    const shouldPollDrafting = activeStatus === "DRAFTING_PLAN";
    if (!shouldPollRunning && !shouldPollDrafting) return;
    const timer = window.setInterval(() => {
      void refreshConversationDetail(activeConversationId, { syncDraft: false });
      void refreshConversations();
    }, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [activeConversationId, activeStatus, streamStatus, refreshConversationDetail, refreshConversations]);

  useEffect(() => {
    if (!activeConversationId || !activeDetail?.taskId || activeStatus !== "RUNNING") {
      setStreamStatus((prev) => (prev === "idle" ? prev : "idle"));
      if (progressWsRef.current) {
        progressWsRef.current.close();
        progressWsRef.current = null;
      }
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      reconnectAttemptRef.current = 0;
      return;
    }

    const taskId = activeDetail.taskId;
    let disposed = false;

    const closeCurrentSocket = () => {
      if (progressWsRef.current) {
        progressWsRef.current.close();
        progressWsRef.current = null;
      }
    };

    const applyRealtimeProgress = (eventName: string, payload: Record<string, unknown>, timestamp: string) => {
      const summary = summarizeRealtimeEvent(payload, eventName);
      const phase = typeof payload.phase === "string" ? payload.phase : eventName;
      const state = typeof payload.state === "string" ? payload.state : "RUNNING";
      const progress = typeof payload.progress === "number" ? Math.max(0, Math.min(100, Math.round(payload.progress))) : null;
      const detail = typeof payload.detail === "string" ? payload.detail : "";
      const message: ConversationMessage = {
        messageId: `rt-${eventName.toLowerCase()}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        conversationId: activeConversationId,
        role: "system",
        kind: "PROGRESS_GROUP",
        content: summary,
        collapsed: true,
        createdAt: timestamp,
        metadata: {
          taskId,
          phase,
          state,
          latestProgress: progress,
          latestSummary: summary,
          entries: [
            {
              summary,
              phase,
              state,
              progress,
              detail,
              raw: payload,
            },
          ],
        },
      };
      setActiveDetail((prev) => {
        if (!prev || prev.conversationId !== activeConversationId) return prev;
        const previousMessages = prev.messages;
        const dedupeHit = previousMessages.length > 0 ? previousMessages[previousMessages.length - 1] : null;
        if (
          dedupeHit &&
          dedupeHit.kind === "PROGRESS_GROUP" &&
          dedupeHit.content === message.content &&
          dedupeHit.metadata.phase === message.metadata.phase
        ) {
          return prev;
        }
        const nextMessages = [...previousMessages, message].slice(-320);
        return {
          ...prev,
          messages: nextMessages,
          updatedAt: timestamp,
        };
      });
      if (eventName === "STALL_WARNING") {
        setPendingAssistantBubble({
          conversationId: activeConversationId,
          content: detail || "当前阶段耗时较长，系统仍在处理中。",
        });
      }
    };

    const applyRealtimeAgentStatus = (payload: Record<string, unknown>, timestamp: string) => {
      const rawType = typeof payload.agentType === "string" ? payload.agentType.toUpperCase() : "";
      const rawStatus = typeof payload.status === "string" ? payload.status.toUpperCase() : "IDLE";
      if (!rawType) return;
      if (!["IDEATION", "PLANNING", "WRITING", "CHECKING"].includes(rawType)) return;

      const nextStatus: AgentState["status"] =
        rawStatus === "FAILED"
          ? "FAILED"
          : rawStatus === "COMPLETED"
            ? "COMPLETED"
            : rawStatus === "WAITING_INPUT"
              ? "WAITING_INPUT"
              : rawStatus === "RUNNING"
                ? "RUNNING"
                : "IDLE";

      const nextProgress = typeof payload.progress === "number"
        ? Math.max(0, Math.min(100, Math.round(payload.progress)))
        : 0;

      const activity = typeof payload.currentActivity === "string" && payload.currentActivity.trim()
        ? payload.currentActivity
        : nextStatus === "COMPLETED"
          ? "阶段完成"
          : "处理中";

      setActiveDetail((prev) => {
        if (!prev || prev.conversationId !== activeConversationId) return prev;
        const existing = Array.isArray(prev.agentStates) && prev.agentStates.length > 0
          ? [...prev.agentStates]
          : deriveAgentStatesFromMessages(prev.messages);

        const normalized = ["IDEATION", "PLANNING", "WRITING", "CHECKING"].map((type) => {
          return existing.find((agent) => agent.agentType === type) ?? {
            agentType: type as AgentType,
            status: "IDLE" as const,
            progress: 0,
            currentActivity: "等待任务开始",
          };
        });

        const nextStates = normalized.map((agent) => {
          if (agent.agentType !== rawType) return agent;
          const startedAt = nextStatus === "RUNNING" ? (agent.startedAt ?? timestamp) : agent.startedAt;
          const completedAt = nextStatus === "COMPLETED" ? timestamp : agent.completedAt;
          const error = nextStatus === "FAILED" ? activity : agent.error;
          return {
            ...agent,
            status: nextStatus,
            progress: nextStatus === "COMPLETED" ? 100 : nextProgress,
            currentActivity: activity,
            startedAt,
            completedAt,
            error,
          };
        });

        const order: AgentType[] = ["IDEATION", "PLANNING", "WRITING", "CHECKING"];
        const rawTypeIndex = order.indexOf(rawType as AgentType);
        if (rawTypeIndex > 0 && (nextStatus === "RUNNING" || nextStatus === "COMPLETED")) {
          for (const priorType of order.slice(0, rawTypeIndex)) {
            const priorIndex = nextStates.findIndex((agent) => agent.agentType === priorType);
            if (priorIndex < 0) continue;
            const prior = nextStates[priorIndex];
            if (prior.status === "FAILED") continue;
            nextStates[priorIndex] = {
              ...prior,
              status: "COMPLETED",
              progress: 100,
              currentActivity: "阶段完成",
              completedAt: prior.completedAt ?? timestamp,
            };
          }
        }

        return {
          ...prev,
          agentStates: nextStates,
          updatedAt: timestamp,
        };
      });
    };

    const scheduleReconnect = () => {
      if (disposed) return;
      reconnectAttemptRef.current += 1;
      if (reconnectAttemptRef.current > WS_MAX_RETRY) {
        setStreamStatus("fallback");
        return;
      }
      setStreamStatus("reconnecting");
      const delay = WS_BASE_BACKOFF_MS * reconnectAttemptRef.current;
      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        connect();
      }, delay);
    };

    const connect = () => {
      if (disposed) return;
      closeCurrentSocket();
      setStreamStatus(reconnectAttemptRef.current > 0 ? "reconnecting" : "connecting");
      const socket = connectProgressWs(taskId, {
        onMessage: (messageEvent) => {
          let parsed: ProgressEvent | null = null;
          try {
            parsed = JSON.parse(messageEvent.data) as ProgressEvent;
          } catch {
            return;
          }
          if (!parsed || !parsed.event || typeof parsed.data !== "object" || parsed.data === null) return;
          setStreamStatus("connected");
          reconnectAttemptRef.current = 0;
          setLastProgressEventAt(parsed.timestamp ?? new Date().toISOString());
          const payload = parsed.data as Record<string, unknown>;
          const phase = typeof payload.phase === "string" ? payload.phase : parsed.event;
          setCurrentPhase(phase);
          if (isProgressEventKind(parsed.event)) {
            applyRealtimeProgress(parsed.event, payload, parsed.timestamp ?? new Date().toISOString());
          }
          if (parsed.event === "AGENT_STATUS") {
            applyRealtimeAgentStatus(payload, parsed.timestamp ?? new Date().toISOString());
          }
          if (parsed.event === "TASK_COMPLETED" || parsed.event === "ERROR") {
            setPendingAssistantBubble(null);
            void refreshConversationDetail(activeConversationId, { syncDraft: false });
            void refreshConversations();
          }
        },
        onError: () => {
          setStreamStatus("reconnecting");
        },
        onClose: () => {
          if (disposed) return;
          scheduleReconnect();
        },
      });
      progressWsRef.current = socket;
    };

    connect();

    return () => {
      disposed = true;
      closeCurrentSocket();
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  }, [activeConversationId, activeDetail?.taskId, activeStatus, refreshConversationDetail, refreshConversations]);

  useEffect(() => {
    window.localStorage.setItem(LEFT_SIDEBAR_KEY, leftSidebarVisible ? "1" : "0");
  }, [leftSidebarVisible]);

  useEffect(() => {
    window.localStorage.setItem(RIGHT_SIDEBAR_KEY, rightSidebarVisible ? "1" : "0");
  }, [rightSidebarVisible]);

  useEffect(() => {
    const drawerOpen = mobileSidebarOpen || mobileEditorOpen;
    if (!drawerOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileSidebarOpen, mobileEditorOpen]);

  async function recoverDraftConversation(
    topic: string,
    previousConversationIds: Set<string>
  ): Promise<ConversationDetail | null> {
    try {
      const items = await listConversations();
      setSummaries(items);
      const recovered =
        items.find((item) => !previousConversationIds.has(item.conversationId)) ??
        items.find((item) => item.topic.trim() === topic);
      if (!recovered) return null;
      setDraftMode(false);
      setActiveConversationId(recovered.conversationId);
      const detail = await getConversation(recovered.conversationId);
      setActiveDetail(detail);
      setPlanDraft(detail.currentPlan?.markdown ?? "");
      setDraftDirtyState(false);
      return detail;
    } catch {
      return null;
    }
  }

  function onCreateDraftConversation() {
    setDraftMode(true);
    setActiveConversationId(null);
    setActiveDetail(null);
    setComposerText("");
    setPlanDraft("");
    setDraftDirtyState(false);
    setDraftMessages([]);
    setPendingAssistantBubble(null);
    setRightSidebarVisible(false);
    setMobileSidebarOpen(false);
    setMobileEditorOpen(false);
    setError("");
  }

  async function onSendInstruction() {
    const text = composerText.trim();
    if (!text) return;
    const submittingDraftTopic = !activeConversationId && draftMode;
    if (submittingDraftTopic && text.length > FIRST_MESSAGE_LIMIT) {
      setError(`首条研究主题最多 ${FIRST_MESSAGE_LIMIT} 字，请精简后再发送。`);
      return;
    }
    const previousConversationIds = submittingDraftTopic
      ? new Set(summaries.map((item) => item.conversationId))
      : undefined;

    let optimisticMessage: ConversationMessage | null = null;
    setSending(true);
    setComposerText("");
    if (submittingDraftTopic) {
      optimisticMessage = {
        messageId: `temp-user-${Date.now()}`,
        conversationId: "__draft__",
        role: "user",
        kind: "USER_TEXT",
        content: text,
        metadata: { optimistic: true, draft: true },
        collapsed: false,
        createdAt: new Date().toISOString()
      };
      setDraftMessages([optimisticMessage]);
      setPendingAssistantBubble({
        conversationId: null,
        content: "正在规划中，请等待，方案生成后会自动显示。"
      });
    } else if (activeConversationId) {
      optimisticMessage = {
        messageId: `temp-user-${Date.now()}`,
        conversationId: activeConversationId,
        role: "user",
        kind: "USER_TEXT",
        content: text,
        metadata: { optimistic: true },
        collapsed: false,
        createdAt: new Date().toISOString()
      };
      const pendingMessage = optimisticMessage;
      setActiveDetail((prev) => {
        if (!prev || prev.conversationId !== activeConversationId) return prev;
        return { ...prev, messages: [...prev.messages, pendingMessage] };
      });
      setPendingAssistantBubble({
        conversationId: activeConversationId,
        content: activeStatus === "COMPLETED" ? "正在修改中，请等待。" : "正在生成中，请等待。"
      });
    }
    setError("");
    try {
      if (submittingDraftTopic) {
        const detail = await createConversation({
          topic: text,
          config: DEFAULT_CONFIG
        });
        setSummaries((prev) => [detail, ...prev.filter((item) => item.conversationId !== detail.conversationId)]);
        setDraftMode(false);
        setActiveConversationId(detail.conversationId);
        setActiveDetail(detail);
        setPlanDraft(detail.currentPlan?.markdown ?? "");
        setDraftDirtyState(false);
        setDraftMessages([]);
        setPendingAssistantBubble(null);
        await refreshConversations();
        return;
      }

      if (!activeConversationId) return;
      await reviseConversationPlan(activeConversationId, text);
      setPendingAssistantBubble(null);
      await refreshConversationDetail(activeConversationId, { syncDraft: true, forceDraft: true });
      await refreshConversations();
    } catch (err) {
      const errorText = toErrorText(err);
      if (submittingDraftTopic && previousConversationIds && errorText.includes("请求超时")) {
        const recoveredDetail = await recoverDraftConversation(text, previousConversationIds);
        if (recoveredDetail) {
          setDraftMessages([]);
          if (recoveredDetail.status === "DRAFTING_PLAN") {
            setPendingAssistantBubble({
              conversationId: recoveredDetail.conversationId,
              content: "正在规划中，请等待，方案生成后会自动显示。"
            });
          } else {
            setPendingAssistantBubble(null);
          }
          await refreshConversations();
          return;
        }
      }
      if (submittingDraftTopic) {
        setComposerText(text);
        setDraftMessages([]);
        setPendingAssistantBubble(null);
      } else {
        setComposerText(text);
        setPendingAssistantBubble(null);
        if (optimisticMessage) {
          setActiveDetail((prev) => {
            if (!prev || prev.conversationId !== optimisticMessage.conversationId) return prev;
            return {
              ...prev,
              messages: prev.messages.filter((message) => message.messageId !== optimisticMessage?.messageId)
            };
          });
        }
      }
      setError(errorText);
    } finally {
      setSending(false);
    }
  }

  async function onSavePlan() {
    if (!activeConversationId || !planDraft.trim()) return;
    setSaving(true);
    setError("");
    try {
      await updateConversationPlan(activeConversationId, planDraft);
      setDraftDirtyState(false);
      await refreshConversationDetail(activeConversationId, { syncDraft: true });
      await refreshConversations();
    } catch (err) {
      setError(toErrorText(err));
    } finally {
      setSaving(false);
    }
  }

  async function onStartResearch() {
    if (!activeConversationId) return;
    setStarting(true);
    setError("");
    try {
      await runConversation(activeConversationId);
      await refreshConversationDetail(activeConversationId, { syncDraft: false });
      await refreshConversations();
    } catch (err) {
      setError(toErrorText(err));
    } finally {
      setStarting(false);
    }
  }

  async function onDownloadReport() {
    if (!activeConversationId) return;
    setDownloading(true);
    setError("");
    try {
      await downloadConversationReport(activeConversationId);
    } catch (err) {
      setError(toErrorText(err));
    } finally {
      setDownloading(false);
    }
  }

  function onOpenPlanDrawer() {
    setRightSidebarVisible(true);
    if (window.matchMedia("(max-width: 1120px)").matches) {
      setMobileEditorOpen(true);
    }
  }

  function onApplyPlan(markdown: string) {
    setPlanDraft(markdown);
    setDraftDirtyState(true);
    onOpenPlanDrawer();
  }

  function onFocusComposer() {
    composerRef.current?.focus();
  }

  function onRequestDeleteConversation(conversationId: string) {
    const summary = summaries.find((item) => item.conversationId === conversationId);
    setConfirmDialog({
      kind: "deleteConversation",
      conversationId,
      topic: summary?.topic ?? "未命名会话"
    });
  }

  async function onConfirmDeleteConversation(conversationId: string) {
    setDeletingConversationId(conversationId);
    setError("");
    try {
      const deletingActive = activeConversationId === conversationId;
      await deleteConversation(conversationId);
      setConfirmDialog(null);
      if (deletingActive) {
        setActiveConversationId(null);
        setActiveDetail(null);
        setPlanDraft("");
        setDraftDirtyState(false);
        setDraftMessages([]);
        setPendingAssistantBubble((prev) => (prev?.conversationId === conversationId ? null : prev));
        setRightSidebarVisible(false);
      }
      await refreshConversations({ autoSelectFirst: deletingActive });
    } catch (err) {
      setError(toErrorText(err));
    } finally {
      setDeletingConversationId(null);
    }
  }

  function onRequestRenameConversation(conversationId: string) {
    const current = summaries.find((item) => item.conversationId === conversationId);
    setRenameDialog({
      conversationId,
      value: current?.topic ?? ""
    });
  }

  async function onConfirmRenameConversation() {
    if (!renameDialog) return;
    const topic = renameDialog.value.trim();
    if (!topic) {
      setError("会话名称不能为空。");
      return;
    }
    if (topic.length > FIRST_MESSAGE_LIMIT) {
      setError(`会话名称最多 ${FIRST_MESSAGE_LIMIT} 字。`);
      return;
    }

    const { conversationId } = renameDialog;
    setRenamingConversationId(conversationId);
    setError("");
    try {
      const detail = await renameConversation(conversationId, { topic, syncCurrentPlan: true });
      setSummaries((prev) =>
        prev.map((item) =>
          item.conversationId === conversationId
            ? {
                conversationId: detail.conversationId,
                topic: detail.topic,
                status: detail.status,
                taskId: detail.taskId,
                createdAt: detail.createdAt,
                updatedAt: detail.updatedAt
              }
            : item
        )
      );
      if (activeConversationId === conversationId) {
        setActiveDetail(detail);
        setPlanDraft(detail.currentPlan?.markdown ?? "");
        setDraftDirtyState(false);
      }
      setRenameDialog(null);
      await refreshConversations();
    } catch (err) {
      setError(toErrorText(err));
    } finally {
      setRenamingConversationId(null);
    }
  }

  function onRequestDeleteAllConversations() {
    if (summaries.length === 0) return;
    setConfirmDialog({
      kind: "deleteAll",
      total: summaries.length
    });
  }

  async function onConfirmDeleteAllConversations() {
    setDeletingAll(true);
    setError("");
    try {
      await deleteAllConversations();
      setSummaries([]);
      setActiveConversationId(null);
      setActiveDetail(null);
      setDraftMode(false);
      setComposerText("");
      setPlanDraft("");
      setDraftDirtyState(false);
      setDraftMessages([]);
      setPendingAssistantBubble(null);
      setRightSidebarVisible(false);
      setMobileSidebarOpen(false);
      setMobileEditorOpen(false);
      setConfirmDialog(null);
      await refreshConversations();
    } catch (err) {
      setError(toErrorText(err));
    } finally {
      setDeletingAll(false);
    }
  }

  const composerPlaceholder =
    activeStatus === "RUNNING"
      ? "正在处理中，完成后可继续补充修改意见。"
      : activeStatus === "DRAFTING_PLAN"
        ? "正在生成研究方案，请等待当前规划完成。"
      : draftMode
        ? "先输入研究主题（最多 500 字），Agent 会先给出第一版研究方案。"
        : activeConversationId
          ? "输入需求，例如：改成演讲稿；补充最新证据并自动重跑。"
          : "请选择会话，或点击“新建研究”。";
  const sendLabel = draftMode && !activeConversationId ? "开始规划" : "发送";
  const confirmDeleteConversationPending =
    confirmDialog?.kind === "deleteConversation" && deletingConversationId === confirmDialog.conversationId;
  const confirmDeleteAllPending = confirmDialog?.kind === "deleteAll" && deletingAll;
  const renamePending = Boolean(renameDialog) && renamingConversationId === renameDialog.conversationId;

  return (
    <>
      {/* Skip Link - 可访问性：让键盘用户快速跳过导航到主内容 */}
      <a href="#main-content-start" className="skip-link">
        跳转到主内容
      </a>
      <main
        className={`shell ${mobileSidebarOpen ? "sidebar-open" : ""} ${mobileEditorOpen ? "editor-open" : ""} ${
          leftSidebarVisible ? "" : "left-hidden"
        } ${rightSidebarVisible ? "" : "right-hidden"}`}
      >
        {/* 可访问性：隐藏的标记，用于 Skip Link 跳转焦点 */}
        <div id="main-content-start" tabIndex={-1} className="sr-only" />
        <div className="edge-hotspot left">
        <button
          className="edge-toggle"
          type="button"
          onClick={() => setLeftSidebarVisible((visible) => !visible)}
          title={leftSidebarVisible ? "隐藏会话栏" : "显示会话栏"}
          aria-label={leftSidebarVisible ? "隐藏会话栏" : "显示会话栏"}
          aria-pressed={leftSidebarVisible}
        >
          {leftSidebarVisible ? "◀" : "▶"}
        </button>
      </div>
      <div className="edge-hotspot right">
        <button
          className="edge-toggle"
          type="button"
          onClick={() => setRightSidebarVisible((visible) => !visible)}
          title={rightSidebarVisible ? "隐藏草稿栏" : "显示草稿栏"}
          aria-label={rightSidebarVisible ? "隐藏草稿栏" : "显示草稿栏"}
          aria-pressed={rightSidebarVisible}
        >
          {rightSidebarVisible ? "▶" : "◀"}
        </button>
      </div>

      {(mobileSidebarOpen || mobileEditorOpen) && (
        <button
          className="mobile-backdrop"
          type="button"
          aria-label="关闭移动端抽屉"
          onClick={() => {
            setMobileSidebarOpen(false);
            setMobileEditorOpen(false);
          }}
        />
      )}

      <ConversationSidebar
        summaries={summaries}
        activeConversationId={activeConversationId}
        creatingDraft={draftMode && !activeConversationId}
        showMobileClose={mobileSidebarOpen}
        refreshing={refreshingList}
        deletingConversationId={deletingConversationId}
        renamingConversationId={renamingConversationId}
        deletingAll={deletingAll}
        onCreateDraft={onCreateDraftConversation}
        onRequestCloseMobile={() => setMobileSidebarOpen(false)}
        onSelect={(conversationId) => {
          setDraftMode(false);
          setActiveConversationId(conversationId);
          setDraftDirtyState(false);
          setDraftMessages([]);
          setPendingAssistantBubble((prev) => (prev?.conversationId === null ? null : prev));
          setMobileSidebarOpen(false);
        }}
        onDelete={onRequestDeleteConversation}
        onRename={onRequestRenameConversation}
        onDeleteAll={onRequestDeleteAllConversations}
      />

      <section className="chat-pane">
        <header className="chat-head">
          <div className="chat-head-actions">
            <button
              className="ghost mobile-only"
              type="button"
              onClick={() => {
                setMobileSidebarOpen(true);
                setMobileEditorOpen(false);
              }}
            >
              会话
            </button>
            <button
              className="ghost mobile-only"
              type="button"
              onClick={() => {
                setMobileEditorOpen(true);
                setMobileSidebarOpen(false);
              }}
            >
              草稿
            </button>
            <button
              className="ghost"
              type="button"
              onClick={() => setShowLibrary(true)}
              title="打开文献库"
            >
              文献库
            </button>
          </div>
          <div className="chat-title">
            <h1>{activeSummary?.topic ?? (draftMode ? "新研究" : "深度研究工作台")}</h1>
            <p>{statusLabel}</p>
          </div>
        </header>

        <WorkflowNavigator
          status={activeStatus}
          currentPhase={currentPhase}
          onStepClick={(stepId) => {
            // Navigate to different views based on step
            if (stepId === "planning") {
              setRightSidebarVisible(true);
            } else if (stepId === "search") {
              setShowLibrary(true);
            }
          }}
        />

        {activeStatus === "RUNNING" && effectiveAgentStates.length > 0 && (
          <AgentStatusPanel
            agents={effectiveAgentStates}
            activePhases={getActiveAgentPhases(effectiveAgentStates)}
          />
        )}

        <ChatTimeline
          messages={timelineMessages}
          currentTaskId={activeDetail?.taskId ?? null}
          draftMode={draftMode}
          activeStatus={activeStatus}
          pendingAssistantText={pendingAssistantText}
          startingResearch={starting}
          onApplyPlan={onApplyPlan}
          onOpenPlanDrawer={onOpenPlanDrawer}
          onStartResearch={onStartResearch}
          onFocusComposer={onFocusComposer}
          downloadingReport={downloading}
          onDownloadReport={onDownloadReport}
          onExportReport={() => setShowExportModal(true)}
          streamStatus={streamStatus}
          lastProgressEventAt={lastProgressEventAt}
          idleSeconds={idleSeconds}
        />

        <Composer
          value={composerText}
          status={activeStatus}
          sending={sending}
          disabled={composerDisabled}
          placeholder={composerPlaceholder}
          sendLabel={sendLabel}
          textareaRef={composerRef}
          onChange={setComposerText}
          onSend={onSendInstruction}
        />
      </section>

      <PlanEditorPane
        markdown={planDraft}
        dirty={draftDirty}
        showMobileClose={mobileEditorOpen}
        saving={saving}
        starting={starting}
        downloading={downloading}
        status={activeStatus}
        onRequestCloseMobile={() => setMobileEditorOpen(false)}
        onChange={(value) => {
          setPlanDraft(value);
          setDraftDirtyState(true);
        }}
        onReset={() => {
          setPlanDraft(activeDetail?.currentPlan?.markdown ?? "");
          setDraftDirtyState(false);
        }}
        onSave={onSavePlan}
        onStart={onStartResearch}
        onDownload={onDownloadReport}
      />

      <Dialog
        open={Boolean(confirmDialog)}
        dismissable={!confirmDeleteConversationPending && !confirmDeleteAllPending}
        title={confirmDialog?.kind === "deleteAll" ? "删除全部会话" : "删除会话"}
        description={
          confirmDialog?.kind === "deleteAll"
            ? `将删除全部 ${confirmDialog.total} 个会话（包括运行中会话），该操作不可恢复。`
            : "删除后将移除该会话的方案与消息，且不可恢复。"
        }
        onClose={() => {
          if (confirmDeleteConversationPending || confirmDeleteAllPending) return;
          setConfirmDialog(null);
        }}
        actions={
          <>
            <button
              className="ghost"
              type="button"
              onClick={() => setConfirmDialog(null)}
              disabled={confirmDeleteConversationPending || confirmDeleteAllPending}
            >
              取消
            </button>
            <button
              className="primary subtle"
              type="button"
              onClick={() => {
                if (!confirmDialog) return;
                if (confirmDialog.kind === "deleteConversation") {
                  void onConfirmDeleteConversation(confirmDialog.conversationId);
                  return;
                }
                void onConfirmDeleteAllConversations();
              }}
              disabled={confirmDeleteConversationPending || confirmDeleteAllPending}
            >
              {confirmDeleteConversationPending || confirmDeleteAllPending ? "删除中..." : "确认删除"}
            </button>
          </>
        }
      >
        {confirmDialog?.kind === "deleteConversation" && (
          <p className="dialog-helper">目标会话：{confirmDialog.topic}</p>
        )}
      </Dialog>

      <Dialog
        open={Boolean(renameDialog)}
        dismissable={!renamePending}
        title="重命名会话"
        description={`请输入新的会话名称（最多 ${FIRST_MESSAGE_LIMIT} 字）。`}
        onClose={() => {
          if (renamePending) return;
          setRenameDialog(null);
        }}
        actions={
          <>
            <button className="ghost" type="button" onClick={() => setRenameDialog(null)} disabled={renamePending}>
              取消
            </button>
            <button className="primary" type="button" onClick={() => void onConfirmRenameConversation()} disabled={renamePending}>
              {renamePending ? "保存中..." : "保存"}
            </button>
          </>
        }
      >
        <input
          className="dialog-input"
          value={renameDialog?.value ?? ""}
          maxLength={FIRST_MESSAGE_LIMIT}
          autoFocus
          onChange={(event) => {
            const nextValue = event.target.value;
            setRenameDialog((prev) => (prev ? { ...prev, value: nextValue } : prev));
          }}
          onKeyDown={(event) => {
            if (event.key !== "Enter") return;
            event.preventDefault();
            if (!renamePending) {
              void onConfirmRenameConversation();
            }
          }}
        />
      </Dialog>

      {showExportModal && activeConversationId && (
        <ExportModal
          conversationId={activeConversationId}
          onClose={() => setShowExportModal(false)}
        />
      )}

      {showLibrary && (
        <div className="library-overlay">
          <LibraryPage onClose={() => setShowLibrary(false)} />
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}
      </main>
    </>
  );
}
