import { useState } from "react";

interface EmptyStateProps {
  scenario: "welcome" | "no-conversation" | "no-messages" | "loading";
  onCreateDraft?: () => void;
  onSelectConversation?: () => void;
  onExampleClick?: (topic: string) => void;
}

const EXAMPLE_TOPICS = [
  {
    topic: "人工智能在医疗诊断中的应用与挑战",
    category: "AI 应用",
    icon: "AI"
  },
  {
    topic: "可持续能源技术的发展趋势与投资机会",
    category: "能源科技",
    icon: "energy"
  },
  {
    topic: "远程办公对员工心理健康的影响研究",
    category: "工作模式",
    icon: "work"
  },
  {
    topic: "区块链技术在供应链管理中的应用案例分析",
    category: "区块链",
    icon: "blockchain"
  }
];

export function EmptyState(props: EmptyStateProps) {
  const { scenario, onCreateDraft, onSelectConversation, onExampleClick } = props;
  const [hoveredExample, setHoveredExample] = useState<string | null>(null);

  // Welcome state - first time user, no conversations
  if (scenario === "welcome") {
    return (
      <div className="empty-state welcome">
        <div className="empty-state-illustration">
          <div className="illustration-icon">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <div className="illustration-pulse" aria-hidden="true" />
        </div>

        <div className="empty-state-content">
          <h2 className="empty-state-title">欢迎使用 Research Flow</h2>
          <p className="empty-state-description">
            输入研究主题，AI 将为您生成详细的研究方案，并进行深度分析和报告生成。
          </p>

          <div className="empty-state-cta">
            <button
              className="primary large"
              type="button"
              onClick={onCreateDraft}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              开始新研究
            </button>
          </div>

          <div className="empty-state-examples">
            <p className="examples-label">或选择一个示例主题开始</p>
            <div className="examples-grid">
              {EXAMPLE_TOPICS.map((example) => (
                <button
                  key={example.topic}
                  className={`example-card ${hoveredExample === example.topic ? "hovered" : ""}`}
                  type="button"
                  onClick={() => onExampleClick?.(example.topic)}
                  onMouseEnter={() => setHoveredExample(example.topic)}
                  onMouseLeave={() => setHoveredExample(null)}
                >
                  <span className="example-category">{example.category}</span>
                  <span className="example-topic">{example.topic}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="empty-state-features">
          <div className="feature-item">
            <div className="feature-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
            </div>
            <span>智能方案生成</span>
          </div>
          <div className="feature-item">
            <div className="feature-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
            </div>
            <span>实时进度追踪</span>
          </div>
          <div className="feature-item">
            <div className="feature-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
            </div>
            <span>报告下载导出</span>
          </div>
        </div>
      </div>
    );
  }

  // No conversation selected
  if (scenario === "no-conversation") {
    return (
      <div className="empty-state centered">
        <div className="empty-state-illustration small">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </div>
        <h3 className="empty-state-title small">选择或创建会话</h3>
        <p className="empty-state-description">
          从左侧列表选择已有会话，或创建新的研究会话。
        </p>
        <div className="empty-state-actions">
          <button className="ghost" type="button" onClick={onSelectConversation}>
            查看会话列表
          </button>
          <button className="primary" type="button" onClick={onCreateDraft}>
            新建研究
          </button>
        </div>
      </div>
    );
  }

  // No messages in current conversation
  if (scenario === "no-messages") {
    return (
      <div className="empty-state centered">
        <div className="empty-state-illustration small">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <h3 className="empty-state-title small">暂无消息记录</h3>
        <p className="empty-state-description">
          当前会话还没有消息记录，请在下方输入框输入研究需求。
        </p>
      </div>
    );
  }

  // Loading state
  return (
    <div className="empty-state centered">
      <div className="loading-indicator">
        <div className="loading-spinner" aria-hidden="true" />
        <span className="loading-text">加载中...</span>
      </div>
    </div>
  );
}