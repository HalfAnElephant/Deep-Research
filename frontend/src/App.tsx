import { useEffect, useMemo, useRef, useState } from "react";

import {
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
import { ChatTimeline } from "./components/ChatTimeline";
import { Composer } from "./components/Composer";
import { ConversationSidebar } from "./components/ConversationSidebar";
import { PlanEditorPane } from "./components/PlanEditorPane";
import type { ConversationDetail, ConversationMessage, ConversationStatus, ConversationSummary } from "./types";

const FIRST_MESSAGE_LIMIT = 500;
const REFRESH_INTERVAL_MS = Number(import.meta.env.VITE_CONVERSATION_REFRESH_MS ?? "2500");

const DEFAULT_CONFIG = {
  maxDepth: 2,
  maxNodes: 8,
  searchSources: ["arXiv", "Semantic Scholar"],
  priority: 4
};

const STATUS_LABEL: Record<ConversationStatus, string> = {
  DRAFTING_PLAN: "草稿生成中",
  PLAN_READY: "方案可执行",
  RUNNING: "处理中",
  COMPLETED: "研究完成",
  FAILED: "执行失败"
};

function toErrorText(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

interface PendingAssistantBubble {
  conversationId: string | null;
  content: string;
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
  const [planVersion, setPlanVersion] = useState(0);
  const [draftDirty, setDraftDirty] = useState(false);
  const [editorMode, setEditorMode] = useState<"edit" | "preview">("edit");

  const [sending, setSending] = useState(false);
  const [saving, setSaving] = useState(false);
  const [starting, setStarting] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [deletingConversationId, setDeletingConversationId] = useState<string | null>(null);
  const [renamingConversationId, setRenamingConversationId] = useState<string | null>(null);
  const [deletingAll, setDeletingAll] = useState(false);
  const [refreshingList, setRefreshingList] = useState(false);
  const [error, setError] = useState("");

  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [mobileEditorOpen, setMobileEditorOpen] = useState(false);
  const [leftSidebarVisible, setLeftSidebarVisible] = useState(true);
  const [rightSidebarVisible, setRightSidebarVisible] = useState(false);

  const composerRef = useRef<HTMLTextAreaElement | null>(null);

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

  useEffect(() => {
    void refreshConversations({ autoSelectFirst: true });
  }, []);

  useEffect(() => {
    if (!activeConversationId) return;
    void refreshConversationDetail(activeConversationId, { syncDraft: true });
  }, [activeConversationId]);

  useEffect(() => {
    if (!activeConversationId || (activeStatus !== "RUNNING" && activeStatus !== "DRAFTING_PLAN")) return;
    const timer = window.setInterval(() => {
      void refreshConversationDetail(activeConversationId, { syncDraft: false });
      void refreshConversations();
    }, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [activeConversationId, activeStatus]);

  async function refreshConversations(options?: { autoSelectFirst?: boolean }) {
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
  }

  async function refreshConversationDetail(
    conversationId: string,
    options?: { syncDraft?: boolean; forceDraft?: boolean }
  ) {
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
        !draftDirty ||
        currentPlan.version !== planVersion;
      if (shouldSync) {
        setPlanDraft(currentPlan.markdown);
        setPlanVersion(currentPlan.version);
        setDraftDirty(false);
      }
    } catch (err) {
      setError(toErrorText(err));
    }
  }

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
      setPlanVersion(detail.currentPlan?.version ?? 0);
      setDraftDirty(false);
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
    setPlanVersion(0);
    setDraftDirty(false);
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
        setPlanVersion(detail.currentPlan?.version ?? 0);
        setDraftDirty(false);
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
      setDraftDirty(false);
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
    setDraftDirty(true);
    setEditorMode("edit");
    onOpenPlanDrawer();
  }

  function onFocusComposer() {
    composerRef.current?.focus();
  }

  async function onDeleteConversation(conversationId: string) {
    if (!window.confirm("删除后将移除该会话的方案与消息，是否继续？")) return;
    setDeletingConversationId(conversationId);
    setError("");
    try {
      const deletingActive = activeConversationId === conversationId;
      await deleteConversation(conversationId);
      if (deletingActive) {
        setActiveConversationId(null);
        setActiveDetail(null);
        setPlanDraft("");
        setPlanVersion(0);
        setDraftDirty(false);
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

  async function onRenameConversation(conversationId: string) {
    const current = summaries.find((item) => item.conversationId === conversationId);
    const input = window.prompt("请输入新的会话名称", current?.topic ?? "");
    if (input === null) return;
    const topic = input.trim();
    if (!topic) {
      setError("会话名称不能为空。");
      return;
    }
    if (topic.length > FIRST_MESSAGE_LIMIT) {
      setError(`会话名称最多 ${FIRST_MESSAGE_LIMIT} 字。`);
      return;
    }

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
        setPlanVersion(detail.currentPlan?.version ?? 0);
        setDraftDirty(false);
      }
      await refreshConversations();
    } catch (err) {
      setError(toErrorText(err));
    } finally {
      setRenamingConversationId(null);
    }
  }

  async function onDeleteAllConversations() {
    if (summaries.length === 0) return;
    if (!window.confirm("将删除全部会话（包括运行中会话），且不可恢复。是否继续？")) return;
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
      setPlanVersion(0);
      setDraftDirty(false);
      setDraftMessages([]);
      setPendingAssistantBubble(null);
      setRightSidebarVisible(false);
      setMobileSidebarOpen(false);
      setMobileEditorOpen(false);
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

  return (
    <main
      className={`shell ${mobileSidebarOpen ? "sidebar-open" : ""} ${mobileEditorOpen ? "editor-open" : ""} ${
        leftSidebarVisible ? "" : "left-hidden"
      } ${rightSidebarVisible ? "" : "right-hidden"}`}
    >
      <div className="edge-hotspot left">
        <button
          className="edge-toggle"
          onClick={() => setLeftSidebarVisible((visible) => !visible)}
          title={leftSidebarVisible ? "隐藏会话栏" : "显示会话栏"}
        >
          {leftSidebarVisible ? "◀" : "▶"}
        </button>
      </div>
      <div className="edge-hotspot right">
        <button
          className="edge-toggle"
          onClick={() => setRightSidebarVisible((visible) => !visible)}
          title={rightSidebarVisible ? "隐藏草稿栏" : "显示草稿栏"}
        >
          {rightSidebarVisible ? "▶" : "◀"}
        </button>
      </div>

      {(mobileSidebarOpen || mobileEditorOpen) && (
        <button
          className="mobile-backdrop"
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
        refreshing={refreshingList}
        deletingConversationId={deletingConversationId}
        renamingConversationId={renamingConversationId}
        deletingAll={deletingAll}
        onCreateDraft={onCreateDraftConversation}
        onSelect={(conversationId) => {
          setDraftMode(false);
          setActiveConversationId(conversationId);
          setDraftDirty(false);
          setDraftMessages([]);
          setPendingAssistantBubble((prev) => (prev?.conversationId === null ? null : prev));
          setMobileSidebarOpen(false);
        }}
        onDelete={onDeleteConversation}
        onRename={onRenameConversation}
        onDeleteAll={onDeleteAllConversations}
      />

      <section className="chat-pane">
        <header className="chat-head">
          <div className="chat-head-actions">
            <button className="ghost mobile-only" onClick={() => setMobileSidebarOpen(true)}>
              会话
            </button>
            <button className="ghost mobile-only" onClick={() => setMobileEditorOpen(true)}>
              草稿
            </button>
          </div>
          <div className="chat-title">
            <h1>{activeSummary?.topic ?? (draftMode ? "新研究" : "Chat-Driven Deep Research")}</h1>
            <p>{statusLabel}</p>
          </div>
        </header>

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
        mode={editorMode}
        dirty={draftDirty}
        saving={saving}
        starting={starting}
        downloading={downloading}
        status={activeStatus}
        onModeChange={setEditorMode}
        onChange={(value) => {
          setPlanDraft(value);
          setDraftDirty(true);
        }}
        onSave={onSavePlan}
        onStart={onStartResearch}
        onDownload={onDownloadReport}
      />

      {error && <div className="error-banner">{error}</div>}
    </main>
  );
}
