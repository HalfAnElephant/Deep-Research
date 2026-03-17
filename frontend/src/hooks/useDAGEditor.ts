import { useState, useCallback, useRef } from "react";

/**
 * Task node status type
 */
export type TaskNodeStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "PRUNED";

/**
 * DAG editor mode type
 */
export type DAGEditorMode = "simple" | "advanced";

/**
 * Task node interface for DAG editor
 */
export interface TaskNode {
  nodeId: string;
  taskId: string;
  title: string;
  description?: string;
  status: TaskNodeStatus;
  priority: number;
  searchDepth: number;
  infoGainScore: number;
  elapsedMs: number;
  retryCount: number;
}

/**
 * DAG edge interface for DAG editor
 */
export interface DAGEdge {
  id: string;
  source: string;
  target: string;
}

/**
 * DAG graph structure
 */
export interface DAGGraph {
  nodes: TaskNode[];
  edges: DAGEdge[];
}

/**
 * DAG editor state interface
 */
export interface DAGEditorState {
  nodes: TaskNode[];
  edges: DAGEdge[];
  selectedNodeId: string | null;
  mode: DAGEditorMode;
  history: DAGGraph[];
  historyIndex: number;
  isDirty: boolean;
}

/**
 * Return type for useDAGEditor hook
 */
export interface UseDAGEditorResult {
  state: DAGEditorState;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  addNode: (parentNodeId?: string) => void;
  deleteNode: (nodeId: string) => void;
  updateNode: (nodeId: string, updates: Partial<TaskNode>) => void;
  selectNode: (nodeId: string | null) => void;
  addEdge: (source: string, target: string) => void;
  deleteEdge: (edgeId: string) => void;
  setMode: (mode: DAGEditorMode) => void;
  exportDag: () => DAGGraph;
  reset: (newDag: DAGGraph) => void;
}

const MAX_HISTORY_SIZE = 50;

/**
 * Custom hook for managing DAG editor state.
 * Provides undo/redo functionality, node and edge operations, and change tracking.
 */
export function useDAGEditor(initialDag: DAGGraph): UseDAGEditorResult {
  // Initial state
  const initialState: DAGEditorState = {
    nodes: initialDag.nodes,
    edges: initialDag.edges,
    selectedNodeId: null,
    mode: "simple",
    history: [initialDag],
    historyIndex: 0,
    isDirty: false,
  };

  const [state, setState] = useState<DAGEditorState>(initialState);
  const initialDagRef = useRef<DAGGraph>(initialDag);
  const nextNodeIdRef = useRef(0);

  /**
   * Generate a unique node ID
   */
  const generateNodeId = useCallback((): string => {
    return `node_${nextNodeIdRef.current++}_${Date.now()}`;
  }, []);

  /**
   * Generate a unique edge ID
   */
  const generateEdgeId = useCallback((): string => {
    return `edge_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }, []);

  /**
   * Check if current state is dirty (changed from initial)
   */
  const checkDirty = useCallback(
    (nodes: TaskNode[], edges: DAGEdge[]): boolean => {
      const currentDag: DAGGraph = { nodes, edges };
      return JSON.stringify(currentDag) !== JSON.stringify(initialDagRef.current);
    },
    []
  );

  /**
   * Push a new state to history
   */
  const pushToHistory = useCallback(
    (nodes: TaskNode[], edges: DAGEdge[]) => {
      setState((prev) => {
        const newHistory = prev.history.slice(0, prev.historyIndex + 1);
        newHistory.push({ nodes, edges });

        // Keep max 50 history entries
        if (newHistory.length > MAX_HISTORY_SIZE) {
          newHistory.shift();
        }

        const newHistoryIndex = newHistory.length - 1;
        const isDirty = checkDirty(nodes, edges);

        return {
          ...prev,
          nodes,
          edges,
          history: newHistory,
          historyIndex: newHistoryIndex,
          isDirty,
        };
      });
    },
    [checkDirty]
  );

  /**
   * Undo last operation
   */
  const undo = useCallback(() => {
    setState((prev) => {
      if (prev.historyIndex <= 0) return prev;
      const newIndex = prev.historyIndex - 1;
      const newDag = prev.history[newIndex];
      const isDirty = checkDirty(newDag.nodes, newDag.edges);

      return {
        ...prev,
        nodes: newDag.nodes,
        edges: newDag.edges,
        historyIndex: newIndex,
        isDirty,
      };
    });
  }, [checkDirty]);

  /**
   * Redo next operation
   */
  const redo = useCallback(() => {
    setState((prev) => {
      if (prev.historyIndex >= prev.history.length - 1) return prev;
      const newIndex = prev.historyIndex + 1;
      const newDag = prev.history[newIndex];
      const isDirty = checkDirty(newDag.nodes, newDag.edges);

      return {
        ...prev,
        nodes: newDag.nodes,
        edges: newDag.edges,
        historyIndex: newIndex,
        isDirty,
      };
    });
  }, [checkDirty]);

  /**
   * Check if undo is available
   */
  const canUndo = state.historyIndex > 0;

  /**
   * Check if redo is available
   */
  const canRedo = state.historyIndex < state.history.length - 1;

  /**
   * Add a new node (optionally as a child of parent node in simple mode)
   */
  const addNode = useCallback(
    (parentNodeId?: string) => {
      setState((prev) => {
        const newNode: TaskNode = {
          nodeId: generateNodeId(),
          taskId: `task_${Date.now()}`,
          title: "New Task",
          description: "",
          status: "PENDING",
          priority: 0,
          searchDepth: 0,
          infoGainScore: 0,
          elapsedMs: 0,
          retryCount: 0,
        };

        const newNodes = [...prev.nodes, newNode];
        let newEdges = [...prev.edges];

        // In simple mode, automatically create edge from parent
        if (prev.mode === "simple" && parentNodeId) {
          const parentNode = prev.nodes.find((n) => n.nodeId === parentNodeId);
          if (parentNode) {
            newEdges = [
              ...newEdges,
              {
                id: generateEdgeId(),
                source: parentNodeId,
                target: newNode.nodeId,
              },
            ];
          }
        }

        const newHistory = prev.history.slice(0, prev.historyIndex + 1);
        newHistory.push({ nodes: newNodes, edges: newEdges });
        if (newHistory.length > MAX_HISTORY_SIZE) {
          newHistory.shift();
        }

        const newHistoryIndex = newHistory.length - 1;
        const isDirty = checkDirty(newNodes, newEdges);

        return {
          ...prev,
          nodes: newNodes,
          edges: newEdges,
          history: newHistory,
          historyIndex: newHistoryIndex,
          isDirty,
          selectedNodeId: newNode.nodeId,
        };
      });
    },
    [generateNodeId, generateEdgeId, checkDirty]
  );

  /**
   * Delete a node and all connected edges
   */
  const deleteNode = useCallback(
    (nodeId: string) => {
      setState((prev) => {
        const newNodes = prev.nodes.filter((n) => n.nodeId !== nodeId);
        const newEdges = prev.edges.filter(
          (e) => e.source !== nodeId && e.target !== nodeId
        );

        const newHistory = prev.history.slice(0, prev.historyIndex + 1);
        newHistory.push({ nodes: newNodes, edges: newEdges });
        if (newHistory.length > MAX_HISTORY_SIZE) {
          newHistory.shift();
        }

        const newHistoryIndex = newHistory.length - 1;
        const isDirty = checkDirty(newNodes, newEdges);

        return {
          ...prev,
          nodes: newNodes,
          edges: newEdges,
          history: newHistory,
          historyIndex: newHistoryIndex,
          isDirty,
          selectedNodeId: prev.selectedNodeId === nodeId ? null : prev.selectedNodeId,
        };
      });
    },
    [checkDirty]
  );

  /**
   * Update a node's properties
   */
  const updateNode = useCallback(
    (nodeId: string, updates: Partial<TaskNode>) => {
      setState((prev) => {
        const nodeIndex = prev.nodes.findIndex((n) => n.nodeId === nodeId);
        if (nodeIndex === -1) return prev;

        const newNodes = [...prev.nodes];
        newNodes[nodeIndex] = { ...newNodes[nodeIndex], ...updates };

        const newHistory = prev.history.slice(0, prev.historyIndex + 1);
        newHistory.push({ nodes: newNodes, edges: prev.edges });
        if (newHistory.length > MAX_HISTORY_SIZE) {
          newHistory.shift();
        }

        const newHistoryIndex = newHistory.length - 1;
        const isDirty = checkDirty(newNodes, prev.edges);

        return {
          ...prev,
          nodes: newNodes,
          history: newHistory,
          historyIndex: newHistoryIndex,
          isDirty,
        };
      });
    },
    [checkDirty]
  );

  /**
   * Select a node
   */
  const selectNode = useCallback((nodeId: string | null) => {
    setState((prev) => ({
      ...prev,
      selectedNodeId: nodeId,
    }));
  }, []);

  /**
   * Add an edge between two nodes (advanced mode only)
   */
  const addEdge = useCallback(
    (source: string, target: string) => {
      // Prevent self-referential edges
      if (source === target) return;

      setState((prev) => {
        // Prevent duplicate edges - check inside setState to avoid stale closure
        const edgeExists = prev.edges.some(
          (e) => e.source === source && e.target === target
        );
        if (edgeExists) return prev;

        const newEdge: DAGEdge = {
          id: generateEdgeId(),
          source,
          target,
        };

        const newEdges = [...prev.edges, newEdge];

        const newHistory = prev.history.slice(0, prev.historyIndex + 1);
        newHistory.push({ nodes: prev.nodes, edges: newEdges });
        if (newHistory.length > MAX_HISTORY_SIZE) {
          newHistory.shift();
        }

        const newHistoryIndex = newHistory.length - 1;
        const isDirty = checkDirty(prev.nodes, newEdges);

        return {
          ...prev,
          edges: newEdges,
          history: newHistory,
          historyIndex: newHistoryIndex,
          isDirty,
        };
      });
    },
    [generateEdgeId, checkDirty]
  );

  /**
   * Delete an edge (advanced mode only)
   */
  const deleteEdge = useCallback(
    (edgeId: string) => {
      setState((prev) => {
        const newEdges = prev.edges.filter((e) => e.id !== edgeId);

        const newHistory = prev.history.slice(0, prev.historyIndex + 1);
        newHistory.push({ nodes: prev.nodes, edges: newEdges });
        if (newHistory.length > MAX_HISTORY_SIZE) {
          newHistory.shift();
        }

        const newHistoryIndex = newHistory.length - 1;
        const isDirty = checkDirty(prev.nodes, newEdges);

        return {
          ...prev,
          edges: newEdges,
          history: newHistory,
          historyIndex: newHistoryIndex,
          isDirty,
        };
      });
    },
    [checkDirty]
  );

  /**
   * Set editor mode
   */
  const setMode = useCallback((mode: DAGEditorMode) => {
    setState((prev) => ({
      ...prev,
      mode,
    }));
  }, []);

  /**
   * Export current DAG state
   */
  const exportDag = useCallback((): DAGGraph => {
    return {
      nodes: [...state.nodes],
      edges: [...state.edges],
    };
  }, [state.nodes, state.edges]);

  /**
   * Reset editor with new DAG data
   */
  const reset = useCallback((newDag: DAGGraph) => {
    initialDagRef.current = newDag;
    nextNodeIdRef.current = 0;

    setState({
      nodes: newDag.nodes,
      edges: newDag.edges,
      selectedNodeId: null,
      mode: "simple",
      history: [newDag],
      historyIndex: 0,
      isDirty: false,
    });
  }, []);

  return {
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
    setMode,
    exportDag,
    reset,
  };
}