import type { ConversationStatus, ConversationSummary } from "../types";

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
  topicInput: string;
  creating: boolean;
  refreshing: boolean;
  onTopicInputChange: (value: string) => void;
  onCreate: () => void;
  onSelect: (conversationId: string) => void;
}

export function ConversationSidebar(props: ConversationSidebarProps) {
  const {
    summaries,
    activeConversationId,
    topicInput,
    creating,
    refreshing,
    onTopicInputChange,
    onCreate,
    onSelect
  } = props;

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <h2>Deep Research</h2>
        <p>多会话研究空间</p>
      </div>

      <div className="new-chat-card">
        <label className="field-label">新研究主题</label>
        <textarea
          value={topicInput}
          onChange={(event) => onTopicInputChange(event.target.value)}
          placeholder="输入一个研究主题，例如：AI Coding Agent 在中型团队的落地策略"
        />
        <button className="primary" onClick={onCreate} disabled={creating || !topicInput.trim()}>
          {creating ? "创建中..." : "新建研究"}
        </button>
      </div>

      <div className="sidebar-list">
        <div className="sidebar-list-head">
          <span>会话列表</span>
          <span className="mono">{refreshing ? "刷新中" : `${summaries.length} 个`}</span>
        </div>
        {summaries.length === 0 ? (
          <div className="empty-item">暂无会话</div>
        ) : (
          summaries.map((conversation) => (
            <button
              key={conversation.conversationId}
              className={`conversation-item ${activeConversationId === conversation.conversationId ? "active" : ""}`}
              onClick={() => onSelect(conversation.conversationId)}
            >
              <div className="conversation-topic">{conversation.topic}</div>
              <div className="conversation-meta">
                <span className={`status-chip ${conversation.status.toLowerCase()}`}>
                  {STATUS_LABEL[conversation.status]}
                </span>
                <span className="mono">{conversation.updatedAt.slice(11, 19)}</span>
              </div>
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
