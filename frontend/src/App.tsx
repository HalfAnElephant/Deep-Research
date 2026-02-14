import { useEffect, useMemo, useState } from "react";

import {
  createConversation,
  downloadConversationReport,
  getConversation,
  listConversations,
  reviseConversationPlan,
  runConversation,
  updateConversationPlan
} from "./api";
import { ChatTimeline } from "./components/ChatTimeline";
import { Composer } from "./components/Composer";
import { ConversationSidebar } from "./components/ConversationSidebar";
import { PlanEditorPane } from "./components/PlanEditorPane";
import type { ConversationDetail, ConversationStatus, ConversationSummary } from "./types";

const DEFAULT_TOPIC = "请研究 AI Agent 在研发流程中的落地路径";
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
  RUNNING: "研究执行中",
  COMPLETED: "研究完成",
  FAILED: "执行失败"
};

function toErrorText(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export function App() {
  const [summaries, setSummaries] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [activeDetail, setActiveDetail] = useState<ConversationDetail | null>(null);

  const [topicInput, setTopicInput] = useState(DEFAULT_TOPIC);
  const [composerText, setComposerText] = useState("");
  const [planDraft, setPlanDraft] = useState("");
  const [planVersion, setPlanVersion] = useState(0);
  const [draftDirty, setDraftDirty] = useState(false);
  const [editorMode, setEditorMode] = useState<"edit" | "preview">("edit");

  const [creating, setCreating] = useState(false);
  const [sending, setSending] = useState(false);
  const [saving, setSaving] = useState(false);
  const [starting, setStarting] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [refreshingList, setRefreshingList] = useState(false);
  const [error, setError] = useState("");

  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [mobileEditorOpen, setMobileEditorOpen] = useState(false);

  const activeStatus = activeDetail?.status ?? null;
  const statusLabel = activeStatus ? STATUS_LABEL[activeStatus] : "未选择会话";
  const composerDisabled = !activeDetail || activeStatus === "RUNNING";

  const activeSummary = useMemo(
    () => summaries.find((item) => item.conversationId === activeConversationId) ?? null,
    [summaries, activeConversationId]
  );

  useEffect(() => {
    void refreshConversations({ autoSelectFirst: true });
  }, []);

  useEffect(() => {
    if (!activeConversationId) return;
    void refreshConversationDetail(activeConversationId, { syncDraft: true });
  }, [activeConversationId]);

  useEffect(() => {
    if (!activeConversationId || activeStatus !== "RUNNING") return;
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
      if (options?.autoSelectFirst && !activeConversationId && items.length > 0) {
        setActiveConversationId(items[0].conversationId);
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

  async function onCreateConversation() {
    if (!topicInput.trim()) return;
    setCreating(true);
    setError("");
    try {
      const detail = await createConversation({
        topic: topicInput.trim(),
        config: DEFAULT_CONFIG
      });
      setSummaries((prev) => [detail, ...prev.filter((item) => item.conversationId !== detail.conversationId)]);
      setActiveConversationId(detail.conversationId);
      setActiveDetail(detail);
      setPlanDraft(detail.currentPlan?.markdown ?? "");
      setPlanVersion(detail.currentPlan?.version ?? 0);
      setDraftDirty(false);
      setComposerText("");
      setMobileSidebarOpen(false);
      await refreshConversations();
    } catch (err) {
      setError(toErrorText(err));
    } finally {
      setCreating(false);
    }
  }

  async function onSendInstruction() {
    if (!activeConversationId || !composerText.trim()) return;
    setSending(true);
    setError("");
    try {
      await reviseConversationPlan(activeConversationId, composerText.trim());
      setComposerText("");
      await refreshConversationDetail(activeConversationId, { syncDraft: true, forceDraft: true });
      await refreshConversations();
    } catch (err) {
      setError(toErrorText(err));
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

  function onApplyPlan(markdown: string) {
    setPlanDraft(markdown);
    setDraftDirty(true);
    setEditorMode("edit");
    setMobileEditorOpen(true);
  }

  return (
    <main className={`shell ${mobileSidebarOpen ? "sidebar-open" : ""} ${mobileEditorOpen ? "editor-open" : ""}`}>
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
        topicInput={topicInput}
        creating={creating}
        refreshing={refreshingList}
        onTopicInputChange={setTopicInput}
        onCreate={onCreateConversation}
        onSelect={(conversationId) => {
          setActiveConversationId(conversationId);
          setDraftDirty(false);
          setMobileSidebarOpen(false);
        }}
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
            <h1>{activeSummary?.topic ?? "Chat-Driven Deep Research"}</h1>
            <p>{statusLabel}</p>
          </div>
        </header>

        <ChatTimeline
          messages={activeDetail?.messages ?? []}
          onApplyPlan={onApplyPlan}
          downloadingReport={downloading}
          onDownloadReport={onDownloadReport}
        />

        <Composer
          value={composerText}
          status={activeStatus}
          sending={sending}
          disabled={composerDisabled}
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
