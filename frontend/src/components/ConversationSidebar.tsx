import { useState } from "react";

import type { ConversationStatus, ConversationSummary } from "../types";
import { formatLocalTime } from "../utils/formatTime";

const STATUS_LABEL: Record<ConversationStatus, string> = {
  DRAFTING_PLAN: "草稿中",
  PLAN_READY: "待执行",
  RUNNING: "运行中",
  COMPLETED: "已完成",
  FAILED: "失败"
};

const STATUS_DESCRIPTION: Record<ConversationStatus, string> = {
  DRAFTING_PLAN: "Agent 正在生成研究方案",
  PLAN_READY: "方案已就绪，可以开始研究",
  RUNNING: "研究任务正在执行中",
  COMPLETED: "研究已完成",
  FAILED: "执行失败，请重试"
};

interface ConversationSidebarProps {
  summaries: ConversationSummary[];
  activeConversationId: string | null;
  creatingDraft: boolean;
  showMobileClose: boolean;
  refreshing: boolean;
  deletingConversationId: string | null;
  renamingConversationId: string | null;
  deletingAll: boolean;
  onCreateDraft: () => void;
  onRequestCloseMobile: () => void;
  onSelect: (conversationId: string) => void;
  onDelete: (conversationId: string) => void;
  onRename: (conversationId: string) => void;
  onDeleteAll: () => void;
}

export function ConversationSidebar(props: ConversationSidebarProps) {
  const {
    summaries,
    activeConversationId,
    creatingDraft,
    showMobileClose,
    refreshing,
    deletingConversationId,
    renamingConversationId,
    deletingAll,
    onCreateDraft,
    onRequestCloseMobile,
    onSelect,
    onDelete,
    onRename,
    onDeleteAll
  } = props;

  const [globalMenuOpen, setGlobalMenuOpen] = useState(false);
  const [activeItemMenuId, setActiveItemMenuId] = useState<string | null>(null);

  return (
    <aside className="sidebar" aria-label="会话列表">
      <div className="sidebar-head">
        <div className="sidebar-head-main">
          <h2>Deep Research</h2>
          <p>多会话研究空间</p>
        </div>
        {showMobileClose && (
          <button
            className="ghost pane-close mobile-only"
            type="button"
            onClick={onRequestCloseMobile}
            aria-label="关闭会话列表"
          >
            关闭
          </button>
        )}
      </div>

      <div className="sidebar-toolbar">
        <button
          className="primary"
          type="button"
          onClick={() => {
            setGlobalMenuOpen(false);
            setActiveItemMenuId(null);
            onCreateDraft();
          }}
          aria-label={creatingDraft ? "等待首条输入" : "新建研究"}
        >
          {creatingDraft ? "等待首条输入" : "新建研究"}
        </button>
        <div className="menu-wrap">
          <button
            className={`icon-button ${globalMenuOpen ? "active" : ""}`}
            type="button"
            onClick={() => {
              setActiveItemMenuId(null);
              setGlobalMenuOpen((open) => !open);
            }}
            title="更多操作"
            aria-label="打开更多会话操作"
            aria-haspopup="menu"
            aria-expanded={globalMenuOpen}
            aria-controls="sidebar-global-menu"
          >
            <svg width="4" height="16" viewBox="0 0 4 16" fill="currentColor" aria-hidden="true">
              <circle cx="2" cy="3" r="1.5" />
              <circle cx="2" cy="8" r="1.5" />
              <circle cx="2" cy="13" r="1.5" />
            </svg>
          </button>
          {globalMenuOpen && (
            <div className="menu-popover" id="sidebar-global-menu" role="menu" aria-label="更多会话操作">
              <button
                className="menu-item danger"
                type="button"
                role="menuitem"
                onClick={() => {
                  setGlobalMenuOpen(false);
                  onDeleteAll();
                }}
                disabled={deletingAll || summaries.length === 0}
                aria-label={deletingAll ? "删除中..." : summaries.length === 0 ? "没有会话可删除" : `删除全部 ${summaries.length} 个会话`}
              >
                {deletingAll ? "删除中..." : "全部删除"}
              </button>
            </div>
          )}
        </div>
      </div>

      <nav className="sidebar-list" aria-label="会话列表">
        <div className="sidebar-list-head">
          <span>会话列表</span>
          <span className="mono" aria-live="polite" aria-atomic="true">
            {refreshing ? "刷新中" : `${summaries.length} 个`}
          </span>
        </div>
        <ul className="sidebar-list-body" role="list">
          {summaries.length === 0 ? (
            <li className="empty-item" role="status">
              暂无会话，点击"新建研究"开始。
            </li>
          ) : (
            summaries.map((conversation) => {
              const isMenuOpen = activeItemMenuId === conversation.conversationId;
              const deleting = deletingConversationId === conversation.conversationId;
              const renaming = renamingConversationId === conversation.conversationId;
              const isActive = activeConversationId === conversation.conversationId;

              return (
                <li
                  key={conversation.conversationId}
                  className={`conversation-item ${isActive ? "active" : ""}`}
                >
                  <button
                    className="conversation-select"
                    type="button"
                    onClick={() => {
                      setGlobalMenuOpen(false);
                      setActiveItemMenuId(null);
                      onSelect(conversation.conversationId);
                    }}
                    aria-current={isActive ? "true" : undefined}
                    aria-describedby={`status-${conversation.conversationId}`}
                  >
                    <div className="conversation-topic">{conversation.topic}</div>
                    <div className="conversation-meta">
                      <span
                        id={`status-${conversation.conversationId}`}
                        className={`status-chip ${conversation.status.toLowerCase()}`}
                        aria-label={STATUS_DESCRIPTION[conversation.status]}
                      >
                        {STATUS_LABEL[conversation.status]}
                      </span>
                      <time className="mono" dateTime={conversation.updatedAt}>
                        {formatLocalTime(conversation.updatedAt)}
                      </time>
                    </div>
                  </button>

                  <div className="menu-wrap item-menu-wrap">
                    <button
                      className={`icon-button small ${isMenuOpen ? "active" : ""}`}
                      type="button"
                      onClick={() => {
                        setGlobalMenuOpen(false);
                        setActiveItemMenuId((current) =>
                          current === conversation.conversationId ? null : conversation.conversationId
                        );
                      }}
                      title="会话操作"
                      aria-label={`打开会话"${conversation.topic}"操作`}
                      aria-haspopup="menu"
                      aria-expanded={isMenuOpen}
                      aria-controls={`conversation-menu-${conversation.conversationId}`}
                    >
                      <svg width="4" height="16" viewBox="0 0 4 16" fill="currentColor" aria-hidden="true">
                        <circle cx="2" cy="3" r="1.5" />
                        <circle cx="2" cy="8" r="1.5" />
                        <circle cx="2" cy="13" r="1.5" />
                      </svg>
                    </button>
                    {isMenuOpen && (
                      <div
                        className="menu-popover item-menu"
                        id={`conversation-menu-${conversation.conversationId}`}
                        role="menu"
                        aria-label={`会话"${conversation.topic}"操作`}
                      >
                        <button
                          className="menu-item"
                          type="button"
                          role="menuitem"
                          onClick={() => {
                            setActiveItemMenuId(null);
                            onRename(conversation.conversationId);
                          }}
                          disabled={renaming || deleting}
                          aria-busy={renaming}
                        >
                          {renaming ? "重命名中..." : "重命名"}
                        </button>
                        <button
                          className="menu-item danger"
                          type="button"
                          role="menuitem"
                          onClick={() => {
                            setActiveItemMenuId(null);
                            onDelete(conversation.conversationId);
                          }}
                          disabled={deleting || renaming}
                          aria-busy={deleting}
                        >
                          {deleting ? "删除中..." : "删除"}
                        </button>
                      </div>
                    )}
                  </div>
                </li>
              );
            })
          )}
        </ul>
      </nav>
    </aside>
  );
}
