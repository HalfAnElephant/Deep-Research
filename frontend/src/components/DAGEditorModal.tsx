import {
  useDAGEditor,
  type DAGGraph,
  type TaskNode,
  type DAGEditorMode,
  type TaskNodeStatus,
} from "../hooks/useDAGEditor";
import { DAGEditor } from "./DAGEditor";

export interface DAGEditorModalProps {
  taskId: string;
  dag: DAGGraph;
  isOpen: boolean;
  onClose: () => void;
  onSave: (dag: DAGGraph) => void;
}

/**
 * NodeDetailPanel Component
 *
 * Side panel for editing properties of a selected node.
 */
interface NodeDetailPanelProps {
  node: TaskNode | null;
  onUpdate: (updates: Partial<TaskNode>) => void;
  onDelete: () => void;
}

function NodeDetailPanel({ node, onUpdate, onDelete }: NodeDetailPanelProps) {
  if (!node) {
    return (
      <div className="dag-node-detail-panel">
        <div className="dag-node-detail-empty">
          <div className="dag-node-detail-empty-icon">?</div>
          <div className="dag-node-detail-empty-text">
            Select a node to view and edit its details
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="dag-node-detail-panel">
      <h3 className="dag-node-detail-panel-header">Node Details</h3>

      <div className="dag-node-detail-field">
        <label htmlFor="node-title">Title</label>
        <input
          id="node-title"
          type="text"
          value={node.title}
          onChange={(e) => onUpdate({ title: e.target.value })}
          placeholder="Enter node title..."
        />
      </div>

      <div className="dag-node-detail-field">
        <label htmlFor="node-description">Description</label>
        <textarea
          id="node-description"
          value={node.description || ""}
          onChange={(e) => onUpdate({ description: e.target.value })}
          placeholder="Enter node description..."
        />
      </div>

      <div className="dag-node-detail-field">
        <label htmlFor="node-status">Status</label>
        <select
          id="node-status"
          value={node.status}
          onChange={(e) => onUpdate({ status: e.target.value as TaskNodeStatus })}
        >
          <option value="PENDING">Pending</option>
          <option value="RUNNING">Running</option>
          <option value="COMPLETED">Completed</option>
          <option value="FAILED">Failed</option>
          <option value="PRUNED">Pruned</option>
        </select>
      </div>

      <div className="dag-node-detail-field">
        <label htmlFor="node-priority">Priority</label>
        <input
          id="node-priority"
          type="number"
          value={node.priority}
          onChange={(e) => onUpdate({ priority: parseInt(e.target.value, 10) || 0 })}
          min="0"
        />
      </div>

      <div className="dag-node-detail-field">
        <label htmlFor="node-depth">Search Depth</label>
        <input
          id="node-depth"
          type="number"
          value={node.searchDepth}
          onChange={(e) => onUpdate({ searchDepth: parseInt(e.target.value, 10) || 0 })}
          min="0"
        />
      </div>

      <div className="dag-node-detail-actions">
        <button
          className="dag-toolbar-btn danger"
          onClick={onDelete}
        >
          Delete Node
        </button>
      </div>
    </div>
  );
}

/**
 * DAGEditorModal Component
 *
 * Full-screen modal for editing DAG (Directed Acyclic Graph) structures.
 * Provides a graph visualization with undo/redo support and node editing.
 */
export function DAGEditorModal({
  taskId,
  dag,
  isOpen,
  onClose,
  onSave,
}: DAGEditorModalProps) {
  // Ensure dag has valid structure
  const safeDag: DAGGraph = {
    nodes: Array.isArray(dag?.nodes) ? dag.nodes : [],
    edges: Array.isArray(dag?.edges) ? dag.edges : [],
  };

  const {
    state,
    undo,
    redo,
    canUndo,
    canRedo,
    addNode,
    deleteNode,
    updateNode,
    selectNode,
    addEdge,
    deleteEdge,
    reorderNodes,
    setMode,
    exportDag,
  } = useDAGEditor(safeDag);

  // Use hook's mode state instead of local state
  const mode = state.mode;

  if (!isOpen) return null;

  const handleSave = () => {
    onSave(exportDag());
  };

  const handleClose = () => {
    if (state.isDirty) {
      const confirmed = window.confirm(
        "You have unsaved changes. Are you sure you want to close?"
      );
      if (!confirmed) return;
    }
    onClose();
  };

  const selectedNode = state.nodes.find((n) => n.nodeId === state.selectedNodeId) ?? null;

  return (
    <div className="dag-editor-modal" role="dialog" aria-labelledby="dag-editor-title">
      <header className="dag-editor-modal-header">
        <h1 id="dag-editor-title" className="dag-editor-modal-title">
          Edit DAG - Task {taskId.slice(0, 8)}...
        </h1>
        <div className="dag-editor-modal-toolbar">
          {/* Mode toggle */}
          <div className="dag-mode-toggle">
            <button
              className={`dag-mode-toggle-btn ${mode === "simple" ? "active" : ""}`}
              onClick={() => setMode("simple")}
              aria-pressed={mode === "simple"}
            >
              Simple
            </button>
            <button
              className={`dag-mode-toggle-btn ${mode === "advanced" ? "active" : ""}`}
              onClick={() => setMode("advanced")}
              aria-pressed={mode === "advanced"}
            >
              Advanced
            </button>
          </div>

          <span className="dag-toolbar-separator" />

          {/* Undo/Redo */}
          <button
            className="dag-toolbar-btn"
            onClick={undo}
            disabled={!canUndo}
            title="Undo last change"
          >
            Undo
          </button>
          <button
            className="dag-toolbar-btn"
            onClick={redo}
            disabled={!canRedo}
            title="Redo last undone change"
          >
            Redo
          </button>

          <span className="dag-toolbar-separator" />

          {/* Dirty indicator */}
          {state.isDirty && (
            <span style={{ color: "var(--warning)", fontSize: "var(--text-sm)" }}>
              Unsaved changes
            </span>
          )}

          {/* Actions */}
          <button
            className="dag-toolbar-btn ghost"
            onClick={handleClose}
          >
            Cancel
          </button>
          <button
            className="dag-toolbar-btn primary"
            onClick={handleSave}
            disabled={!state.isDirty}
          >
            Save
          </button>
        </div>
      </header>

      <div className="dag-editor-modal-body">
        <DAGEditor
          nodes={state.nodes}
          edges={state.edges}
          mode={mode}
          selectedNodeId={state.selectedNodeId}
          onNodeSelect={selectNode}
          onNodeAdd={addNode}
          onNodeDelete={deleteNode}
          onNodeReorder={reorderNodes}
          onEdgeAdd={addEdge}
          onEdgeDelete={deleteEdge}
        />

        <NodeDetailPanel
          node={selectedNode}
          onUpdate={(updates) => {
            if (state.selectedNodeId) {
              updateNode(state.selectedNodeId, updates);
            }
          }}
          onDelete={() => {
            if (state.selectedNodeId) {
              deleteNode(state.selectedNodeId);
            }
          }}
        />
      </div>
    </div>
  );
}