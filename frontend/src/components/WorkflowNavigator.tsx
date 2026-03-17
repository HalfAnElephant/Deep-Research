import type { ConversationStatus } from "../types";

interface WorkflowStep {
  id: string;
  label: string;
  description: string;
  icon: string;
}

const WORKFLOW_STEPS: WorkflowStep[] = [
  {
    id: "topic",
    label: "选题",
    description: "确定研究主题",
    icon: "💡",
  },
  {
    id: "planning",
    label: "规划",
    description: "制定研究计划",
    icon: "📋",
  },
  {
    id: "search",
    label: "检索",
    description: "搜索文献资料",
    icon: "🔍",
  },
  {
    id: "analysis",
    label: "分析",
    description: "分析证据冲突",
    icon: "📊",
  },
  {
    id: "report",
    label: "报告",
    description: "生成研究报告",
    icon: "📝",
  },
];

interface WorkflowNavigatorProps {
  status: ConversationStatus | null;
  currentPhase?: string | null;
  onStepClick?: (stepId: string) => void;
}

export function WorkflowNavigator({
  status,
  currentPhase,
  onStepClick,
}: WorkflowNavigatorProps) {
  // Determine current step based on status and phase
  const getCurrentStepIndex = (): number => {
    if (!status || status === "DRAFTING_PLAN") return 1; // Planning step
    if (status === "PLAN_READY") return 1; // Planning step, ready to run
    if (status === "RUNNING") {
      // Map phase to step
      if (!currentPhase) return 2;
      if (currentPhase === "PLANNING") return 1;
      if (currentPhase === "EXECUTING") return 2;
      if (currentPhase === "REVIEWING") return 3;
      if (currentPhase === "SYNTHESIZING" || currentPhase === "FINALIZING") return 4;
      return 2;
    }
    if (status === "COMPLETED") return 4;
    if (status === "FAILED") return -1;
    return 0;
  };

  const currentStepIndex = getCurrentStepIndex();
  const isFailed = status === "FAILED";

  const getStepStatus = (index: number): "completed" | "current" | "pending" | "error" => {
    if (isFailed && index === currentStepIndex) return "error";
    if (index < currentStepIndex) return "completed";
    if (index === currentStepIndex) return "current";
    return "pending";
  };

  const getStatusIcon = (stepStatus: string, stepIcon: string) => {
    if (stepStatus === "completed") return "✓";
    if (stepStatus === "error") return "✕";
    return stepIcon;
  };

  const getStepClassName = (stepStatus: string) => {
    const baseClass = "workflow-step";
    switch (stepStatus) {
      case "completed":
        return `${baseClass} workflow-step-completed`;
      case "current":
        return `${baseClass} workflow-step-current`;
      case "error":
        return `${baseClass} workflow-step-error`;
      default:
        return `${baseClass} workflow-step-pending`;
    }
  };

  return (
    <div className="workflow-navigator">
      <div className="workflow-track">
        {WORKFLOW_STEPS.map((step, index) => {
          const stepStatus = getStepStatus(index);
          const isClickable = stepStatus !== "pending" && onStepClick;

          return (
            <div key={step.id} className="workflow-step-wrapper">
              {/* Connector line */}
              {index > 0 && (
                <div
                  className={`workflow-connector ${
                    index <= currentStepIndex ? "workflow-connector-active" : ""
                  } ${isFailed && index === currentStepIndex ? "workflow-connector-error" : ""}`}
                />
              )}

              {/* Step */}
              <button
                className={getStepClassName(stepStatus)}
                onClick={() => isClickable && onStepClick?.(step.id)}
                disabled={!isClickable}
                title={`${step.label}: ${step.description}`}
              >
                <span className="workflow-step-icon">
                  {getStatusIcon(stepStatus, step.icon)}
                </span>
                <span className="workflow-step-label">{step.label}</span>
                {stepStatus === "current" && status === "RUNNING" && (
                  <span className="workflow-step-pulse" />
                )}
              </button>

              {/* Step label below */}
              <span className="workflow-step-description">{step.description}</span>
            </div>
          );
        })}
      </div>

      {/* Status indicator */}
      {status && (
        <div className="workflow-status">
          <span className={`workflow-status-badge workflow-status-${status.toLowerCase()}`}>
            {getStatusLabel(status, currentPhase)}
          </span>
        </div>
      )}
    </div>
  );
}

function getStatusLabel(status: ConversationStatus, phase?: string | null): string {
  const statusMap: Record<string, string> = {
    DRAFTING_PLAN: "制定计划",
    PLAN_READY: "准备就绪",
    RUNNING: phase ? getPhaseLabel(phase) : "执行中",
    COMPLETED: "已完成",
    FAILED: "执行失败",
  };
  return statusMap[status] || status;
}

function getPhaseLabel(phase: string): string {
  const phaseMap: Record<string, string> = {
    PLANNING: "规划中",
    EXECUTING: "检索中",
    REVIEWING: "分析中",
    SYNTHESIZING: "撰写中",
    FINALIZING: "完成中",
  };
  return phaseMap[phase] || phase;
}
