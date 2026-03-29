export interface ProgressBarProps {
  progress: number;
  status: "pending" | "running" | "completed" | "failed";
  size?: "small" | "medium" | "large";
  showLabel?: boolean;
  animated?: boolean;
  phase?: string; // 可选的阶段，用于显示对应颜色
}

export function ProgressBar(props: ProgressBarProps) {
  const { progress, status, size = "medium", showLabel = true, animated = true, phase } = props;

  const getStatusColor = () => {
    // 如果有阶段信息，优先使用阶段颜色
    if (phase && status === "running") {
      const colors = getPhaseColorVars(phase);
      return colors.color;
    }

    switch (status) {
      case "completed":
        return "var(--success)";
      case "failed":
        return "var(--danger)";
      case "running":
        return "var(--primary)";
      default:
        return "var(--muted-light)";
    }
  };

  const clampedProgress = Math.min(100, Math.max(0, Math.round(progress)));

  return (
    <div className={`progress-bar progress-bar-${size}`} role="progressbar" aria-valuenow={clampedProgress} aria-valuemin={0} aria-valuemax={100} aria-label={`研究进度: ${clampedProgress}%`}>
      <div className="progress-bar-track">
        <div
          className={`progress-bar-fill ${animated && status === "running" ? "animated" : ""}`}
          style={{
            width: `${clampedProgress}%`,
            backgroundColor: getStatusColor()
          }}
        />
      </div>
      {showLabel && (
        <span className="progress-bar-label" style={{ color: getStatusColor() }}>
          {clampedProgress}%
        </span>
      )}
    </div>
  );
}

interface ProgressStep {
  id: string;
  label: string;
  status: "pending" | "running" | "completed" | "failed";
  phase?: string; // 可选的阶段标识，用于颜色显示
}

export interface ProgressStepsProps {
  steps: ProgressStep[];
  orientation?: "horizontal" | "vertical";
}

export function ProgressSteps(props: ProgressStepsProps) {
  const { steps, orientation = "horizontal" } = props;

  const getStepIcon = (status: ProgressStep["status"]) => {
    switch (status) {
      case "completed":
        return (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        );
      case "failed":
        return (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        );
      case "running":
        return (
          <div className="step-spinner" aria-hidden="true" />
        );
      default:
        return null;
    }
  };

  return (
    <div className={`progress-steps progress-steps-${orientation}`} role="list" aria-label="研究步骤">
      {steps.map((step, index) => {
        // 根据步骤 ID 或 phase 获取颜色
        const phaseKey = step.phase || step.id;
        const colors = getPhaseColorVars(phaseKey);
        const isActive = step.status === "running" || step.status === "completed";

        return (
          <div key={step.id} className={`progress-step progress-step-${step.status}`} role="listitem">
            <div className="step-indicator">
              <div
                className={`step-circle step-circle-${step.status}`}
                style={isActive ? {
                  backgroundColor: step.status === "completed" ? colors.color : undefined,
                  borderColor: colors.color,
                  color: step.status === "completed" ? "white" : colors.color,
                  boxShadow: step.status === "running" ? `0 0 0 4px ${colors.glow}` : undefined
                } : {}}
              >
                {getStepIcon(step.status)}
                {step.status === "pending" && <span className="step-number">{index + 1}</span>}
              </div>
              {index < steps.length - 1 && (
                <div
                  className={`step-connector step-connector-${steps[index + 1].status === "completed" || step.status === "completed" ? "active" : ""}`}
                  style={step.status === "completed" ? { backgroundColor: colors.color } : {}}
                />
              )}
            </div>
            <div className="step-content">
              <span className="step-label" style={step.status === "running" ? { color: colors.color } : {}}>
                {step.label}
              </span>
              <span className="step-status">{getStatusLabel(step.status)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function getStatusLabel(status: ProgressStep["status"]): string {
  switch (status) {
    case "completed":
      return "已完成";
    case "running":
      return "进行中";
    case "failed":
      return "失败";
    default:
      return "等待中";
  }
}

export interface ProgressCardProps {
  summary: string;
  progress: number;
  status: "pending" | "running" | "completed" | "failed";
  phase?: string;
  detail?: string;
  entries?: Array<{
    summary: string;
    phase: string;
    state: string;
    progress: number | null;
    detail?: string;
  }>;
  expanded?: boolean;
  onToggle?: () => void;
}

export function ProgressCard(props: ProgressCardProps) {
  const { summary, progress, status, phase, detail, entries = [], expanded = false, onToggle } = props;

  const getStepsFromEntries = (): ProgressStep[] => {
    if (entries.length === 0) {
      return [
        { id: "planning", label: "规划研究", status: status === "completed" ? "completed" : status === "failed" ? "failed" : "pending" },
        { id: "searching", label: "搜索资料", status: "pending" },
        { id: "analyzing", label: "分析数据", status: "pending" },
        { id: "synthesizing", label: "整合报告", status: "pending" }
      ];
    }

    const phases = [...new Set(entries.map(e => e.phase))];
    return phases.map((p, index) => {
      const phaseEntries = entries.filter(e => e.phase === p);
      const hasRunning = phaseEntries.some(e => e.state === "RUNNING");
      const hasCompleted = phaseEntries.every(e => e.state === "COMPLETED");
      const hasFailed = phaseEntries.some(e => e.state === "FAILED");

      let stepStatus: ProgressStep["status"] = "pending";
      if (hasFailed) stepStatus = "failed";
      else if (hasCompleted) stepStatus = "completed";
      else if (hasRunning) stepStatus = "running";

      return {
        id: p,
        label: getPhaseLabel(p),
        status: stepStatus,
        phase: p // 传递 phase 用于颜色显示
      };
    });
  };

  // 获取当前阶段的颜色
  const currentPhaseColors = phase ? getPhaseColorVars(phase) : null;

  return (
    <div className={`progress-card progress-card-${status}`}>
      <button className="progress-card-header" type="button" onClick={onToggle} aria-expanded={expanded}>
        <div className="progress-card-main">
          <ProgressBar progress={progress} status={status} size="medium" phase={phase} />
          <p className="progress-card-summary">{summary}</p>
          {phase && (
            <span
              className="progress-card-phase"
              style={currentPhaseColors ? {
                backgroundColor: currentPhaseColors.light,
                color: currentPhaseColors.text,
                border: `1px solid ${currentPhaseColors.border}`,
                boxShadow: `0 0 0 2px ${currentPhaseColors.glow}`
              } : {}}
            >
              {getPhaseLabel(phase)}
            </span>
          )}
          {detail && <span className="progress-card-detail">{detail}</span>}
        </div>
        <div className="progress-card-toggle">
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            style={{ transform: expanded ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </button>

      {expanded && (
        <div className="progress-card-details">
          <ProgressSteps steps={getStepsFromEntries()} orientation="vertical" />

          {entries.length > 0 && (
            <div className="progress-entries-list">
              <h4 className="entries-title">详细记录</h4>
              {entries.map((entry, index) => {
                const colors = getPhaseColorVars(entry.phase);
                return (
                  <div
                    key={index}
                    className={`entry-item entry-state-${entry.state.toLowerCase()}`}
                    style={{
                      borderLeft: `3px solid ${colors.color}`
                    }}
                  >
                    <div className="entry-summary">{entry.summary}</div>
                    <div className="entry-meta">
                      <span
                        className="entry-phase"
                        style={{
                          backgroundColor: colors.light,
                          color: colors.text,
                          border: `1px solid ${colors.border}`
                        }}
                      >
                        {getPhaseLabel(entry.phase)}
                      </span>
                      {entry.progress !== null && (
                        <span className="entry-progress">{entry.progress}%</span>
                      )}
                    </div>
                    {entry.detail && <div className="entry-detail">{entry.detail}</div>}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function getPhaseLabel(phase: string): string {
  const labels: Record<string, string> = {
    PLANNING: "规划阶段",
    BUILDING_PLAN: "构建研究计划",
    SEARCHING: "搜索阶段",
    EXECUTING: "执行搜索",
    NODE_COMPLETED: "节点完成",
    REVIEWING: "分析阶段",
    REVIEWING_CONFLICTS: "分析冲突",
    SYNTHESIZING: "整合阶段",
    OUTLINING: "生成大纲",
    WRITING_SECTION: "写作章节",
    PREPARING_MATERIALS: "准备写作材料",
    CALLING_LLM: "等待 AI 响应",
    REVIEW_PASSED: "审核通过",
    REVIEW_ISSUES: "审核发现问题",
    SAVING_REPORT: "保存报告",
    FINALIZING: "完成阶段",
    PERSISTING_REPORT: "持久化报告"
  };
  return labels[phase] || phase;
}

// 阶段到颜色的映射
function getPhaseColorVars(phase: string): {
  color: string;
  light: string;
  border: string;
  glow: string;
  text: string;
} {
  // 根据阶段前缀判断所属阶段
  const upperPhase = phase.toUpperCase();

  // Phase 1: PLANNING - 紫色
  if (upperPhase.includes("PLAN") || upperPhase.includes("BUILDING")) {
    return {
      color: "var(--phase-planning)",
      light: "var(--phase-planning-light)",
      border: "var(--phase-planning-border)",
      glow: "var(--phase-planning-glow)",
      text: "var(--phase-planning-text)"
    };
  }

  // Phase 3: REVIEWING - 琥珀色
  if (upperPhase.includes("REVIEW") || upperPhase.includes("CALLING_LLM")) {
    return {
      color: "var(--phase-reviewing)",
      light: "var(--phase-reviewing-light)",
      border: "var(--phase-reviewing-border)",
      glow: "var(--phase-reviewing-glow)",
      text: "var(--phase-reviewing-text)"
    };
  }

  // Phase 4: SYNTHESIZING - 青色
  if (upperPhase.includes("SYNTHESIZING") || upperPhase.includes("OUTLINING") ||
      upperPhase.includes("WRITING") || upperPhase.includes("PREPARING")) {
    return {
      color: "var(--phase-synthesizing)",
      light: "var(--phase-synthesizing-light)",
      border: "var(--phase-synthesizing-border)",
      glow: "var(--phase-synthesizing-glow)",
      text: "var(--phase-synthesizing-text)"
    };
  }

  // Phase 5: FINALIZING - 翠绿色
  if (upperPhase.includes("FINALIZING") || upperPhase.includes("PERSISTING") ||
      upperPhase.includes("SAVING") || upperPhase.includes("COMPLETED")) {
    return {
      color: "var(--phase-finalizing)",
      light: "var(--phase-finalizing-light)",
      border: "var(--phase-finalizing-border)",
      glow: "var(--phase-finalizing-glow)",
      text: "var(--phase-finalizing-text)"
    };
  }

  // Phase 2: EXECUTING - 蓝色 (默认)
  return {
    color: "var(--phase-executing)",
    light: "var(--phase-executing-light)",
    border: "var(--phase-executing-border)",
    glow: "var(--phase-executing-glow)",
    text: "var(--phase-executing-text)"
  };
}
