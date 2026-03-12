/** Agent 状态面板组件 - 显示四个智能体的工作状态 */

import type { AgentState, AgentType } from "../types";

interface AgentStatusPanelProps {
  agents: AgentState[];
  activePhases: AgentType[];
}

interface AgentConfig {
  label: string;
  icon: React.ReactNode;
  color: string;
}

const AGENT_CONFIG: Record<AgentType, AgentConfig> = {
  IDEATION: {
    label: "构思智能体",
    color: "#8B5CF6",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <title>构思智能体图标</title>
        <path d="M9 18c-2.2 0-4-1.8-4-4V7a5 5 0 0 1 10 0v7c0 2.2-1.8 4-4 4Z" />
        <path d="M14 4v3" />
        <path d="M19 7c1.1 0 2 .9 2 2v.5c0 1.4-1.1 2.5-2.5 2.5" />
        <path d="M2 12c-1.1 0-2-.9-2-2" />
      </svg>
    )
  },
  PLANNING: {
    label: "规划智能体",
    color: "#3B82F6",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <title>规划智能体图标</title>
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
      </svg>
    )
  },
  WRITING: {
    label: "写作智能体",
    color: "#10B981",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <title>写作智能体图标</title>
        <path d="M12 19l7-7 3 3-7 7-3-3z" />
        <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z" />
        <path d="M2 2l7.586 7.586" />
        <circle cx="11" cy="11" r="2" />
      </svg>
    )
  },
  CHECKING: {
    label: "检查智能体",
    color: "#F59E0B",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <title>检查智能体图标</title>
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
        <polyline points="22 4 12 14.01 9 11.01" />
      </svg>
    )
  }
};

const STATUS_LABELS: Record<string, string> = {
  IDLE: "待机",
  RUNNING: "运行中",
  COMPLETED: "已完成",
  FAILED: "失败",
  WAITING_INPUT: "等待输入"
};

export function AgentStatusPanel(props: AgentStatusPanelProps) {
  const { agents, activePhases } = props;

  return (
    <div className="agent-status-panel">
      {(Object.keys(AGENT_CONFIG) as AgentType[]).map((type) => {
        const config = AGENT_CONFIG[type];
        const state = agents.find(a => a.agentType === type);
        const isActive = activePhases.includes(type);

        return (
          <AgentCard
            key={type}
            type={type}
            config={config}
            state={state}
            isActive={isActive}
          />
        );
      })}
    </div>
  );
}

interface AgentCardProps {
  type: AgentType;
  config: AgentConfig;
  state: AgentState | undefined;
  isActive: boolean;
}

function AgentCard(props: AgentCardProps) {
  const { config, state, isActive } = props;
  const status = state?.status || "IDLE";

  return (
    <div
      className={`agent-card ${isActive ? 'active' : ''} ${status.toLowerCase()}`}
      style={{ '--agent-color': config.color } as React.CSSProperties}
    >
      <div className="agent-icon" style={{ color: config.color }}>
        {config.icon}
      </div>
      <div className="agent-info">
        <span className="agent-label">{config.label}</span>
        <span className={`agent-status status-${status.toLowerCase()}`}>
          {STATUS_LABELS[status] || status}
        </span>
        {state?.status === "RUNNING" && (
          <>
            <div className="agent-progress">
              <div
                className="agent-progress-bar"
                style={{ width: `${state.progress}%` }}
              />
            </div>
            <span className="agent-activity">{state.currentActivity}</span>
          </>
        )}
        {state?.status === "COMPLETED" && (
          <span className="agent-completed">✓ 完成</span>
        )}
        {state?.error && (
          <span className="agent-error">{state.error}</span>
        )}
      </div>
    </div>
  );
}