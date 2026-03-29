import { useEffect, useRef, useCallback, useState } from "react";
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

const NODE_MIN_WIDTH = 220;
const NODE_MAX_WIDTH = 300;
const NODE_MIN_HEIGHT = 72;
const NODE_HORIZONTAL_PADDING = 36;
const NODE_VERTICAL_PADDING = 28;
const NODE_FONT_SIZE = 14;
const NODE_LINE_HEIGHT = 18;
const NODE_CHARACTERS_PER_LINE = 14;
const FIT_PADDING = 36;
const MIN_FIT_ZOOM = 0.62;
const MAX_FIT_ZOOM = 1.05;

const DAGRE_LAYOUT_OPTIONS: DagreLayoutOptions = {
  name: "dagre",
  rankDir: "TB",
  nodeSep: 72,
  rankSep: 112,
  fit: false,
  animate: false,
};

/**
 * Edge creation step state for two-step edge creation flow
 */
type EdgeCreationStep = "idle" | "source" | "target";

export interface DAGEditorProps {
  nodes: TaskNode[];
  edges: DAGEdge[];
  mode: DAGEditorMode;
  selectedNodeId: string | null;
  onNodeSelect: (nodeId: string | null) => void;
  onNodeAdd: (parentNodeId?: string) => void;
  onNodeDelete: (nodeId: string) => void;
  onNodeMove?: (nodeId: string, position: { x: number; y: number }) => void;
  onNodeReorder?: (orderedNodeIds: string[]) => void;
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

function hexToRgba(hexColor: string, alpha: number): string {
  const normalized = hexColor.replace("#", "");
  if (normalized.length !== 6) return `rgba(74, 144, 217, ${alpha})`;

  const red = Number.parseInt(normalized.slice(0, 2), 16);
  const green = Number.parseInt(normalized.slice(2, 4), 16);
  const blue = Number.parseInt(normalized.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function measureNode(title: string) {
  const trimmedTitle = title.trim() || "Untitled";
  const textLength = Array.from(trimmedTitle).length;
  const lineCount = Math.max(1, Math.ceil(textLength / NODE_CHARACTERS_PER_LINE));
  const widestLineChars = Math.min(
    NODE_CHARACTERS_PER_LINE + 4,
    Math.max(NODE_CHARACTERS_PER_LINE, textLength)
  );
  const width = Math.min(
    NODE_MAX_WIDTH,
    Math.max(NODE_MIN_WIDTH, widestLineChars * NODE_FONT_SIZE + NODE_HORIZONTAL_PADDING)
  );
  const height = Math.max(
    NODE_MIN_HEIGHT,
    lineCount * NODE_LINE_HEIGHT + NODE_VERTICAL_PADDING
  );

  return {
    width,
    height,
    labelMaxWidth: width - NODE_HORIZONTAL_PADDING,
  };
}

function fitGraph(cy: Core) {
  const elements = cy.elements();
  if (elements.length === 0) return;

  cy.resize();
  cy.fit(elements, FIT_PADDING);
  const nextZoom = Math.min(MAX_FIT_ZOOM, Math.max(cy.zoom(), MIN_FIT_ZOOM));
  cy.zoom(nextZoom);
  cy.center(elements);
}

function getEdgeStyle(mode: DAGEditorMode) {
  return {
    width: mode === "advanced" ? 3 : 2,
    "line-color": mode === "advanced" ? "#888" : "#666",
    "target-arrow-color": mode === "advanced" ? "#888" : "#666",
    opacity: mode === "advanced" ? 1 : 0.8,
  };
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
  onNodeMove,
  onNodeReorder,
  onEdgeAdd,
  onEdgeDelete,
}: DAGEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  // Edge creation state for two-step flow
  const [edgeCreationStep, setEdgeCreationStep] = useState<EdgeCreationStep>("idle");
  const [edgeSource, setEdgeSource] = useState<string | null>(null);

  // Refs for edge creation state to avoid effect re-runs
  const edgeCreationStepRef = useRef(edgeCreationStep);
  const edgeSourceRef = useRef(edgeSource);

  useEffect(() => {
    edgeCreationStepRef.current = edgeCreationStep;
  }, [edgeCreationStep]);

  useEffect(() => {
    edgeSourceRef.current = edgeSource;
  }, [edgeSource]);

  // Stable callback refs to avoid effect re-runs
  const onNodeSelectRef = useRef(onNodeSelect);
  const onNodeDeleteRef = useRef(onNodeDelete);
  const onNodeMoveRef = useRef(onNodeMove);
  const onNodeReorderRef = useRef(onNodeReorder);
  const onEdgeAddRef = useRef(onEdgeAdd);
  const onEdgeDeleteRef = useRef(onEdgeDelete);
  const modeRef = useRef(mode);
  const resizeFrameRef = useRef<number | null>(null);
  const selectedNodeIdRef = useRef<string | null>(selectedNodeId);
  const manualLayoutRef = useRef(false);
  const manualPositionsRef = useRef<Record<string, { x: number; y: number }>>({});

  useEffect(() => {
    onNodeSelectRef.current = onNodeSelect;
  }, [onNodeSelect]);

  useEffect(() => {
    onNodeDeleteRef.current = onNodeDelete;
  }, [onNodeDelete]);

  useEffect(() => {
    onNodeMoveRef.current = onNodeMove;
  }, [onNodeMove]);

  useEffect(() => {
    onNodeReorderRef.current = onNodeReorder;
  }, [onNodeReorder]);

  useEffect(() => {
    onEdgeAddRef.current = onEdgeAdd;
  }, [onEdgeAdd]);

  useEffect(() => {
    onEdgeDeleteRef.current = onEdgeDelete;
  }, [onEdgeDelete]);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    selectedNodeIdRef.current = selectedNodeId;
  }, [selectedNodeId]);

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
            "background-color": "data(backgroundColor)",
            label: "data(label)",
            width: "data(width)",
            height: "data(height)",
            shape: "roundrectangle",
            "corner-radius": 24,
            padding: 14,
            "text-wrap": "wrap",
            "text-max-width": "data(labelMaxWidth)",
            "text-valign": "center",
            "text-halign": "center",
            "font-size": NODE_FONT_SIZE,
            "line-height": 1.3,
            color: "#0f172a",
            "border-width": 1.75,
            "border-color": "data(borderColor)",
            "text-outline-width": 0,
            "shadow-color": "data(shadowColor)",
            "shadow-blur": 18,
            "shadow-opacity": 0.4,
            "shadow-offset-y": 6,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 3,
            "border-color": "#111827",
            "shadow-blur": 24,
            "shadow-opacity": 0.58,
          },
        },
        {
          selector: "edge",
          style: {
            ...getEdgeStyle(mode),
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
        {
          selector: "edge.highlighted",
          style: {
            width: 4,
            "line-color": "#4CAF50",
            "target-arrow-color": "#4CAF50",
          },
        },
      ],
      layout: DAGRE_LAYOUT_OPTIONS,
      minZoom: 0.45,
      maxZoom: 2.4,
      wheelSensitivity: 0.3,
      autoungrabify: false,
    });

    cyRef.current = cy;

    // Handle edge deletion in advanced mode
    cy.on("tap", "edge", (evt) => {
      if (modeRef.current === "advanced") {
        const edge = evt.target;
        // Delete edge on click in advanced mode
        onEdgeDeleteRef.current?.(edge.id());
      }
    });

    // Handle node selection
    cy.on("tap", "node", (evt) => {
      const node = evt.target;

      // Handle edge creation flow - use refs to get current state
      const currentStep = edgeCreationStepRef.current;
      const currentSource = edgeSourceRef.current;

      if (currentStep === "source") {
        setEdgeSource(node.id());
        setEdgeCreationStep("target");
        return;
      }

      if (currentStep === "target" && currentSource) {
        // Prevent self-loops
        if (currentSource !== node.id()) {
          onEdgeAddRef.current?.(currentSource, node.id());
        }
        setEdgeCreationStep("idle");
        setEdgeSource(null);
        return;
      }

      // Normal node selection
      onNodeSelectRef.current(node.id());
    });

    // Handle keyboard deletion for selected node
    const handleKeyDown = (event: KeyboardEvent) => {
      const isDelete = event.key === "Delete" || event.key === "Backspace";
      if (!isDelete) return;

      const target = event.target as HTMLElement | null;
      const isTypingTarget =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        Boolean(target?.closest("[contenteditable='true']"));

      if (isTypingTarget || !selectedNodeIdRef.current) return;

      event.preventDefault();
      onNodeDeleteRef.current(selectedNodeIdRef.current);
    };

    window.addEventListener("keydown", handleKeyDown);

    // Enable drag-to-reorder in canvas
    cy.on("dragfree", "node", (evt) => {
      const node = evt.target;
      if (!manualLayoutRef.current) {
        const captured: Record<string, { x: number; y: number }> = {};
        cy.nodes().forEach((n) => {
          const p = n.position();
          captured[n.id()] = { x: p.x, y: p.y };
        });
        manualPositionsRef.current = captured;
      }

      manualLayoutRef.current = true;
      const position = node.position();
      manualPositionsRef.current[node.id()] = { x: position.x, y: position.y };
      onNodeMoveRef.current?.(node.id(), { x: position.x, y: position.y });

      const orderedIds = cy
        .nodes()
        .toArray()
        .sort((a, b) => {
          const ay = a.position("y");
          const by = b.position("y");
          if (ay === by) {
            return a.position("x") - b.position("x");
          }
          return ay - by;
        })
        .map((n) => n.id());

      onNodeReorderRef.current?.(orderedIds);
    });

    // Handle canvas click (deselect)
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        // Cancel edge creation if clicking on canvas - use ref
        if (edgeCreationStepRef.current !== "idle") {
          setEdgeCreationStep("idle");
          setEdgeSource(null);
        }
        onNodeSelectRef.current(null);
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      if (resizeFrameRef.current !== null) {
        window.cancelAnimationFrame(resizeFrameRef.current);
      }

      resizeFrameRef.current = window.requestAnimationFrame(() => {
        fitGraph(cy);
      });
    });

    resizeObserver.observe(containerRef.current);

    // Fit to view on initial render
    cy.ready(() => {
      window.requestAnimationFrame(() => {
        fitGraph(cy);
      });
    });

    return () => {
      if (resizeFrameRef.current !== null) {
        window.cancelAnimationFrame(resizeFrameRef.current);
      }
      window.removeEventListener("keydown", handleKeyDown);
      resizeObserver.disconnect();
      cy.destroy();
    };
  }, []);

  /**
   * Update elements when nodes/edges change
   */
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    const validNodeIds = new Set(nodes.map((node) => node.nodeId));
    for (const nodeId of Object.keys(manualPositionsRef.current)) {
      if (!validNodeIds.has(nodeId)) {
        delete manualPositionsRef.current[nodeId];
      }
    }

    const currentPositions = manualPositionsRef.current;
    const currentPositionEntries = Object.values(currentPositions);
    const averageX =
      currentPositionEntries.length > 0
        ? currentPositionEntries.reduce((sum, p) => sum + p.x, 0) / currentPositionEntries.length
        : 220;
    const averageY =
      currentPositionEntries.length > 0
        ? currentPositionEntries.reduce((sum, p) => sum + p.y, 0) / currentPositionEntries.length
        : 140;

    // Map nodes to Cytoscape format
    const cyNodes = nodes.map((node) => {
      const baseColor = getNodeColor(node.status);
      const nodeSize = measureNode(node.title);
      const fallbackPosition = {
        x: averageX + ((nodes.findIndex((n) => n.nodeId === node.nodeId) % 4) - 1.5) * 92,
        y: averageY + Math.floor(nodes.findIndex((n) => n.nodeId === node.nodeId) / 4) * 88,
      };

      return {
        data: {
          id: node.nodeId,
          label: node.title,
          color: baseColor,
          backgroundColor: hexToRgba(baseColor, 0.3),
          borderColor: hexToRgba(baseColor, 0.85),
          shadowColor: hexToRgba(baseColor, 0.42),
          width: nodeSize.width,
          height: nodeSize.height,
          labelMaxWidth: nodeSize.labelMaxWidth,
          ...node,
        },
        position: manualLayoutRef.current
          ? currentPositions[node.nodeId] ?? fallbackPosition
          : undefined,
      };
    });

    const cyEdges = edges.map((edge, index) => ({
      data: {
        id: edge.id || `edge-${index}`,
        source: edge.source,
        target: edge.target,
      },
    }));

    cy.json({ elements: { nodes: cyNodes, edges: cyEdges } });

    if (manualLayoutRef.current) {
      const layout = cy.layout({
        name: "preset",
        fit: false,
        animate: false,
      });
      layout.run();
      fitGraph(cy);
      return;
    }

    const layout = cy.layout(DAGRE_LAYOUT_OPTIONS);
    layout.one("layoutstop", () => {
      fitGraph(cy);
    });
    layout.run();
  }, [nodes, edges]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.style()
      .selector("edge")
      .style(getEdgeStyle(mode))
      .update();

    if (mode !== "advanced" && edgeCreationStepRef.current !== "idle") {
      setEdgeCreationStep("idle");
      setEdgeSource(null);
    }
  }, [mode]);

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
   * Start edge creation flow
   */
  const handleStartEdgeCreation = useCallback(() => {
    setEdgeCreationStep("source");
    setEdgeSource(null);
  }, []);

  /**
   * Cancel edge creation flow
   */
  const handleCancelEdgeCreation = useCallback(() => {
    setEdgeCreationStep("idle");
    setEdgeSource(null);
  }, []);

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
        {mode === "advanced" && edgeCreationStep === "idle" && (
          <button
            className="dag-toolbar-btn"
            onClick={handleStartEdgeCreation}
            title="Start creating an edge between two nodes"
          >
            Add Edge
          </button>
        )}
        {mode === "advanced" && edgeCreationStep === "source" && (
          <div className="dag-toolbar-hint">
            <span>Click on the source node</span>
            <button
              className="dag-toolbar-btn ghost"
              onClick={handleCancelEdgeCreation}
              title="Cancel edge creation"
            >
              Cancel
            </button>
          </div>
        )}
        {mode === "advanced" && edgeCreationStep === "target" && (
          <div className="dag-toolbar-hint">
            <span>Click on the target node</span>
            <button
              className="dag-toolbar-btn ghost"
              onClick={handleCancelEdgeCreation}
              title="Cancel edge creation"
            >
              Cancel
            </button>
          </div>
        )}
        {mode === "advanced" && (
          <span className="dag-toolbar-hint-inline">
            Drag nodes to reorder · Click edges to delete
          </span>
        )}
      </div>
    </div>
  );
}
