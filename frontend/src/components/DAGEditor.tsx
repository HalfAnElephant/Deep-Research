import { useEffect, useRef, useCallback } from "react";
import cytoscape, { Core, LayoutOptions } from "cytoscape";
import dagre from "cytoscape-dagre";
import type { TaskNode, DAGEdge, DAGEditorMode, TaskNodeStatus } from "../hooks/useDAGEditor";

// Register dagre layout extension
cytoscape.use(dagre);

/**
 * Dagre layout options for Cytoscape.js
 */
type DagreLayoutOptions = LayoutOptions & {
  rankDir?: "TB" | "BT" | "LR" | "RL";
  nodeSep?: number;
  rankSep?: number;
};

export interface DAGEditorProps {
  nodes: TaskNode[];
  edges: DAGEdge[];
  mode: DAGEditorMode;
  selectedNodeId: string | null;
  onNodeSelect: (nodeId: string | null) => void;
  onNodeAdd: (parentNodeId?: string) => void;
  onNodeDelete: (nodeId: string) => void;
  onNodeMove?: (nodeId: string, position: { x: number; y: number }) => void;
  onEdgeAdd?: (source: string, target: string) => void;
  onEdgeDelete?: (edgeId: string) => void;
}

/**
 * Helper function to get node color based on status
 */
function getNodeColor(status: TaskNodeStatus): string {
  const colors: Record<TaskNodeStatus, string> = {
    PENDING: "#4A90D9",
    RUNNING: "#FFB84D",
    COMPLETED: "#4CAF50",
    FAILED: "#FF6B6B",
    PRUNED: "#9E9E9E",
  };
  return colors[status] || colors.PENDING;
}

/**
 * DAGEditor Component
 *
 * A Cytoscape.js-based directed acyclic graph editor component.
 * Supports node visualization, selection, and basic graph operations.
 */
export function DAGEditor({
  nodes,
  edges,
  mode,
  selectedNodeId,
  onNodeSelect,
  onNodeAdd,
  onNodeDelete,
  onEdgeAdd,
}: DAGEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  // Stable callback refs to avoid effect re-runs
  const onNodeSelectRef = useRef(onNodeSelect);
  useEffect(() => {
    onNodeSelectRef.current = onNodeSelect;
  }, [onNodeSelect]);

  /**
   * Initialize Cytoscape instance
   */
  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            label: "data(label)",
            width: 150,
            height: 40,
            shape: "roundrectangle",
            "text-wrap": "wrap",
            "text-valign": "center",
            "text-halign": "center",
            "font-size": 12,
            color: "#fff",
            "border-width": 2,
            "border-color": "data(borderColor)",
            "text-outline-width": 1,
            "text-outline-color": "data(color)",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 3,
            "border-color": "#FF6B6B",
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "#666",
            "target-arrow-color": "#666",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
          },
        },
        {
          selector: "edge:selected",
          style: {
            width: 3,
            "line-color": "#FF6B6B",
            "target-arrow-color": "#FF6B6B",
          },
        },
      ],
      layout: {
        name: "dagre",
        rankDir: "TB",
        nodeSep: 50,
        rankSep: 100,
      } as DagreLayoutOptions,
      minZoom: 0.3,
      maxZoom: 2,
      wheelSensitivity: 0.3,
    });

    cyRef.current = cy;

    // Handle node selection
    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      onNodeSelectRef.current(node.id());
    });

    // Handle canvas click (deselect)
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        onNodeSelectRef.current(null);
      }
    });

    // Fit to view on initial render
    cy.ready(() => {
      cy.fit(undefined, 50);
    });

    return () => {
      cy.destroy();
    };
  }, []);

  /**
   * Update elements when nodes/edges change
   */
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    // Map nodes to Cytoscape format
    const cyNodes = nodes.map((node) => ({
      data: {
        id: node.nodeId,
        label: node.title,
        color: getNodeColor(node.status),
        borderColor: getNodeColor(node.status),
        ...node,
      },
    }));

    const cyEdges = edges.map((edge, index) => ({
      data: {
        id: edge.id || `edge-${index}`,
        source: edge.source,
        target: edge.target,
      },
    }));

    cy.json({ elements: { nodes: cyNodes, edges: cyEdges } });
    cy.layout({ name: "dagre", rankDir: "TB", nodeSep: 50, rankSep: 100 } as DagreLayoutOptions).run();
    cy.fit(undefined, 50);
  }, [nodes, edges]);

  /**
   * Handle selection state changes
   */
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.nodes().unselect();
    if (selectedNodeId) {
      const node = cy.getElementById(selectedNodeId);
      node.select();
    }
  }, [selectedNodeId]);

  /**
   * Handle adding child node to selected node
   */
  const handleAddChildNode = useCallback(() => {
    onNodeAdd(selectedNodeId || undefined);
  }, [onNodeAdd, selectedNodeId]);

  /**
   * Handle deleting selected node
   */
  const handleDeleteNode = useCallback(() => {
    if (selectedNodeId) {
      onNodeDelete(selectedNodeId);
    }
  }, [onNodeDelete, selectedNodeId]);

  /**
   * Handle adding edge (advanced mode)
   */
  const handleAddEdge = useCallback(() => {
    if (mode === "advanced" && onEdgeAdd) {
      // In advanced mode, could show a modal or use edgehandles extension
      // For now, this is a placeholder
      console.log("Add edge functionality available in advanced mode");
    }
  }, [mode, onEdgeAdd]);

  return (
    <div className="dag-editor-canvas" ref={containerRef}>
      {/* Toolbar for node operations */}
      <div className="dag-editor-toolbar">
        <button
          className="dag-toolbar-btn primary"
          onClick={() => onNodeAdd()}
          title="Add a new root node"
        >
          Add Root Node
        </button>
        {selectedNodeId && (
          <>
            <button
              className="dag-toolbar-btn"
              onClick={handleAddChildNode}
              title="Add a child node to the selected node"
            >
              Add Child Node
            </button>
            <button
              className="dag-toolbar-btn danger"
              onClick={handleDeleteNode}
              title="Delete the selected node and its connections"
            >
              Delete Node
            </button>
          </>
        )}
        {mode === "advanced" && (
          <button
            className="dag-toolbar-btn"
            onClick={handleAddEdge}
            title="Add an edge between two nodes (advanced mode)"
          >
            Add Edge
          </button>
        )}
      </div>
    </div>
  );
}