/**
 * Custom hooks for Deep Research frontend application.
 * These hooks encapsulate complex state management and computation logic.
 */

export { useMenuState } from "./useMenuState";
export { useDraftPlan } from "./useDraftPlan";
export { useConversationState } from "./useConversationState";
export {
  useMessageTimeline,
  isPlanMessageKind,
  roleLabel,
  type ProgressEntry,
  type ProgressBundle,
  type UseMessageTimelineOptions,
  type UseMessageTimelineResult,
} from "./useMessageTimeline";
export {
  useDAGEditor,
  type TaskNodeStatus,
  type DAGEditorMode,
  type TaskNode,
  type DAGEdge,
  type DAGGraph,
  type DAGEditorState,
  type UseDAGEditorResult,
} from "./useDAGEditor";