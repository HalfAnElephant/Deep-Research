interface ProgressBarProps {
  progress: number;
  status: "pending" | "running" | "completed" | "failed";
  size?: "small" | "medium" | "large";
  showLabel?: boolean;
  animated?: boolean;
}

export function ProgressBar(props: ProgressBarProps) {
  const { progress, status, size = "medium", showLabel = true, animated = true } = props;

  const getStatusColor = () => {
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
}

interface ProgressStepsProps {
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
      {steps.map((step, index) => (
        <div key={step.id} className={`progress-step progress-step-${step.status}`} role="listitem">
          <div className="step-indicator">
            <div className={`step-circle step-circle-${step.status}`}>
              {getStepIcon(step.status)}
              {step.status === "pending" && <span className="step-number">{index + 1}</span>}
            </div>
            {index < steps.length - 1 && (
              <div className={`step-connector step-connector-${steps[index + 1].status === "completed" || step.status === "completed" ? "active" : ""}`} />
            )}
          </div>
          <div className="step-content">
            <span className="step-label">{step.label}</span>
            <span className="step-status">{getStatusLabel(step.status)}</span>
          </div>
        </div>
      ))}
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

interface ProgressCardProps {
  summary: string;
  progress: number;
  status: "pending" | "running" | "completed" | "failed";
  phase?: string;
  entries?: Array<{
    summary: string;
    phase: string;
    state: string;
    progress: number | null;
  }>;
  expanded?: boolean;
  onToggle?: () => void;
}

export function ProgressCard(props: ProgressCardProps) {
  const { summary, progress, status, phase, entries = [], expanded = false, onToggle } = props;

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
        status: stepStatus
      };
    });
  };

  return (
    <div className={`progress-card progress-card-${status}`}>
      <button className="progress-card-header" type="button" onClick={onToggle} aria-expanded={expanded}>
        <div className="progress-card-main">
          <ProgressBar progress={progress} status={status} size="medium" />
          <p className="progress-card-summary">{summary}</p>
          {phase && <span className="progress-card-phase">{phase}</span>}
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
              {entries.map((entry, index) => (
                <div key={index} className={`entry-item entry-state-${entry.state.toLowerCase()}`}>
                  <div className="entry-summary">{entry.summary}</div>
                  <div className="entry-meta">
                    <span className="entry-phase">{entry.phase}</span>
                    {entry.progress !== null && (
                      <span className="entry-progress">{entry.progress}%</span>
                    )}
                  </div>
                </div>
              ))}
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
    SEARCHING: "搜索阶段",
    ANALYZING: "分析阶段",
    SYNTHESIZING: "整合阶段",
    FINALIZING: "完成阶段"
  };
  return labels[phase] || phase;
}