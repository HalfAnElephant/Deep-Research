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
import { Dialog } from "./components/Dialog";
import { PlanEditorPane } from "./components/PlanEditorPane";
import type { ConversationDetail, ConversationMessage, ConversationStatus, ConversationSummary } from "./types";

const FIRST_MESSAGE_LIMIT = 500;
const REFRESH_INTERVAL_MS = Number(import.meta.env.VITE_CONVERSATION_REFRESH_MS ?? "2500");
const LEFT_SIDEBAR_KEY = "dr:left-sidebar-visible";
const RIGHT_SIDEBAR_KEY = "dr:right-sidebar-visible";

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

function readStoredFlag(key: string, fallback: boolean): boolean {
  if (typeof window === "undefined") return fallback;
  const raw = window.localStorage.getItem(key);
  if (raw === "1") return true;
  if (raw === "0") return false;
  return fallback;
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
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState | null>(null);
  const [renameDialog, setRenameDialog] = useState<RenameDialogState | null>(null);

  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [mobileEditorOpen, setMobileEditorOpen] = useState(false);
  const [leftSidebarVisible, setLeftSidebarVisible] = useState(() => readStoredFlag(LEFT_SIDEBAR_KEY, true));
  const [rightSidebarVisible, setRightSidebarVisible] = useState(() => readStoredFlag(RIGHT_SIDEBAR_KEY, false));

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
        setPlanVersion(detail.currentPlan?.version ?? 0);
        setDraftDirty(false);
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
      setPlanVersion(0);
      setDraftDirty(false);
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
    <main
      className={`shell ${mobileSidebarOpen ? "sidebar-open" : ""} ${mobileEditorOpen ? "editor-open" : ""} ${
        leftSidebarVisible ? "" : "left-hidden"
      } ${rightSidebarVisible ? "" : "right-hidden"}`}
    >
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
          setDraftDirty(false);
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
          </div>
          <div className="chat-title">
            <h1>{activeSummary?.topic ?? (draftMode ? "新研究" : "深度研究工作台")}</h1>
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
        showMobileClose={mobileEditorOpen}
        saving={saving}
        starting={starting}
        downloading={downloading}
        status={activeStatus}
        onModeChange={setEditorMode}
        onRequestCloseMobile={() => setMobileEditorOpen(false)}
        onChange={(value) => {
          setPlanDraft(value);
          setDraftDirty(true);
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

      {error && <div className="error-banner">{error}</div>}
    </main>
  );
}
