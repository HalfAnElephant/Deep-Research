"""DAG validation service for detecting cycles, orphans, and computing execution order."""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


class DAGValidator:
    """Validator for DAG structure with cycle detection and topological sort."""

    @staticmethod
    def validate(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
        """
        Validate DAG structure. Returns list of error messages.
        Empty list means valid.

        Args:
            nodes: List of node dictionaries with 'taskId' field
            edges: List of edge dictionaries with 'from'/'to' or 'source'/'target' fields

        Returns:
            List of error messages, empty if valid
        """
        errors: list[str] = []

        # Build node ID set
        node_ids = {n.get("taskId") for n in nodes if n.get("taskId")}

        # Check for missing node references in edges
        for i, edge in enumerate(edges):
            # Support both 'from'/'to' and 'source'/'target' formats
            source = edge.get("from") or edge.get("source")
            target = edge.get("to") or edge.get("target")

            # Check for missing required fields
            if not source:
                errors.append(f"Edge at index {i} is missing source ('from' or 'source' field)")
                continue
            if not target:
                errors.append(f"Edge at index {i} is missing target ('to' or 'target' field)")
                continue

            if source not in node_ids:
                errors.append(f"Edge references unknown source node: {source}")
            if target not in node_ids:
                errors.append(f"Edge references unknown target node: {target}")

        # Check for cycles using DFS
        if DAGValidator._has_cycle(nodes, edges):
            errors.append("DAG contains a cycle")

        # Check for orphan nodes (no incoming or outgoing edges)
        orphan_nodes = DAGValidator._find_orphans(nodes, edges)
        if orphan_nodes:
            errors.append(f"Orphan nodes found: {', '.join(orphan_nodes)}")

        return errors

    @staticmethod
    def _has_cycle(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> bool:
        """
        Detect cycle using DFS with three-color marking.

        Colors:
            WHITE (0): Not visited
            GRAY (1): Currently being processed (in recursion stack)
            BLACK (2): Completely processed

        Returns:
            True if cycle detected, False otherwise
        """
        # Build adjacency list
        adj: dict[str, list[str]] = defaultdict(list)
        for edge in edges:
            source = edge.get("from") or edge.get("source")
            target = edge.get("to") or edge.get("target")
            if source and target:
                adj[source].append(target)

        node_ids = [n.get("taskId") for n in nodes if n.get("taskId")]
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {nid: WHITE for nid in node_ids}

        def dfs(node: str) -> bool:
            """Returns True if cycle found."""
            color[node] = GRAY
            for neighbor in adj[node]:
                if color.get(neighbor) == GRAY:
                    return True  # Back edge found = cycle
                if color.get(neighbor) == WHITE and dfs(neighbor):
                    return True
            color[node] = BLACK
            return False

        for nid in node_ids:
            if color[nid] == WHITE:
                if dfs(nid):
                    return True
        return False

    @staticmethod
    def _find_orphans(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
        """
        Find nodes with no connections (only when there are multiple nodes).

        Returns:
            List of orphan node IDs
        """
        if len(nodes) <= 1:
            return []

        connected: set[str] = set()
        for edge in edges:
            source = edge.get("from") or edge.get("source")
            target = edge.get("to") or edge.get("target")
            if source:
                connected.add(source)
            if target:
                connected.add(target)

        node_ids = [n.get("taskId") for n in nodes if n.get("taskId")]
        return [nid for nid in node_ids if nid not in connected]

    @staticmethod
    def compute_execution_order(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
        """
        Topological sort using Kahn's algorithm.

        Returns:
            List of node IDs in execution order
        """
        # Build in-degree map and adjacency list
        in_degree: dict[str, int] = defaultdict(int)
        adj: dict[str, list[str]] = defaultdict(list)
        node_ids = [n.get("taskId") for n in nodes if n.get("taskId")]

        for nid in node_ids:
            in_degree[nid] = 0

        for edge in edges:
            source = edge.get("from") or edge.get("source")
            target = edge.get("to") or edge.get("target")
            if source and target:
                adj[source].append(target)
                in_degree[target] += 1

        # Start with nodes that have no dependencies
        queue: deque[str] = deque(nid for nid in node_ids if in_degree[nid] == 0)
        result: list[str] = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result