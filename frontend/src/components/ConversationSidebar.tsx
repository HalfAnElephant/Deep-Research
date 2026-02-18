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
    <aside className="sidebar">
      <div className="sidebar-head">
        <div className="sidebar-head-main">
          <h2>Deep Research</h2>
          <p>多会话研究空间</p>
        </div>
        {showMobileClose && (
          <button className="ghost pane-close mobile-only" type="button" onClick={onRequestCloseMobile}>
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
            ⋯
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
              >
                {deletingAll ? "删除中..." : "全部删除"}
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="sidebar-list">
        <div className="sidebar-list-head">
          <span>会话列表</span>
          <span className="mono">{refreshing ? "刷新中" : `${summaries.length} 个`}</span>
        </div>
        <div className="sidebar-list-body">
          {summaries.length === 0 ? (
            <div className="empty-item">暂无会话，点击“新建研究”开始。</div>
          ) : (
            summaries.map((conversation) => {
              const isMenuOpen = activeItemMenuId === conversation.conversationId;
              const deleting = deletingConversationId === conversation.conversationId;
              const renaming = renamingConversationId === conversation.conversationId;

              return (
                <div
                  key={conversation.conversationId}
                  className={`conversation-item ${activeConversationId === conversation.conversationId ? "active" : ""}`}
                >
                  <button
                    className="conversation-select"
                    type="button"
                    onClick={() => {
                      setGlobalMenuOpen(false);
                      setActiveItemMenuId(null);
                      onSelect(conversation.conversationId);
                    }}
                  >
                    <div className="conversation-topic">{conversation.topic}</div>
                    <div className="conversation-meta">
                      <span className={`status-chip ${conversation.status.toLowerCase()}`}>
                        {STATUS_LABEL[conversation.status]}
                      </span>
                      <span className="mono">{formatLocalTime(conversation.updatedAt)}</span>
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
                      aria-label={`打开会话“${conversation.topic}”操作`}
                      aria-haspopup="menu"
                      aria-expanded={isMenuOpen}
                      aria-controls={`conversation-menu-${conversation.conversationId}`}
                    >
                      ⋯
                    </button>
                    {isMenuOpen && (
                      <div
                        className="menu-popover item-menu"
                        id={`conversation-menu-${conversation.conversationId}`}
                        role="menu"
                        aria-label={`会话“${conversation.topic}”操作`}
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
                        >
                          {deleting ? "删除中..." : "删除"}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </aside>
  );
}
