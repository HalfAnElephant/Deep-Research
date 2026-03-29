"""Unit tests for DAGValidator service."""
from __future__ import annotations

from app.services.dag_validator import DAGValidator


class TestDAGValidatorValidate:
    """Tests for DAGValidator.validate()"""

    def test_valid_simple_dag(self):
        """A simple DAG with no cycles should pass validation."""
        nodes = [{"taskId": "a"}, {"taskId": "b"}, {"taskId": "c"}]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "c"},
        ]
        errors = DAGValidator.validate(nodes, edges)
        assert errors == []

    def test_detects_cycle(self):
        """Should detect cycles in the graph."""
        nodes = [{"taskId": "a"}, {"taskId": "b"}, {"taskId": "c"}]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "c"},
            {"source": "c", "target": "a"},  # Creates cycle
        ]
        errors = DAGValidator.validate(nodes, edges)
        assert "DAG contains a cycle" in errors

    def test_detects_unknown_source(self):
        """Should detect edges referencing unknown source nodes."""
        nodes = [{"taskId": "a"}]
        edges = [{"source": "unknown", "target": "a"}]
        errors = DAGValidator.validate(nodes, edges)
        assert any("unknown source node" in e for e in errors)

    def test_detects_unknown_target(self):
        """Should detect edges referencing unknown target nodes."""
        nodes = [{"taskId": "a"}]
        edges = [{"source": "a", "target": "unknown"}]
        errors = DAGValidator.validate(nodes, edges)
        assert any("unknown target node" in e for e in errors)

    def test_detects_orphan_nodes(self):
        """Should detect nodes with no connections when multiple nodes exist."""
        nodes = [{"taskId": "a"}, {"taskId": "b"}, {"taskId": "orphan"}]
        edges = [{"source": "a", "target": "b"}]
        errors = DAGValidator.validate(nodes, edges)
        assert any("Orphan nodes" in e for e in errors)

    def test_single_node_no_orphan(self):
        """A single node should not be flagged as orphan."""
        nodes = [{"taskId": "a"}]
        edges = []
        errors = DAGValidator.validate(nodes, edges)
        assert not any("Orphan" in e for e in errors)

    def test_detects_missing_edge_source(self):
        """Should detect edges with missing source field."""
        nodes = [{"taskId": "a"}]
        edges = [{"target": "a"}]  # Missing source
        errors = DAGValidator.validate(nodes, edges)
        assert any("missing source" in e for e in errors)

    def test_detects_missing_edge_target(self):
        """Should detect edges with missing target field."""
        nodes = [{"taskId": "a"}]
        edges = [{"source": "a"}]  # Missing target
        errors = DAGValidator.validate(nodes, edges)
        assert any("missing target" in e for e in errors)

    def test_supports_from_to_format(self):
        """Should support both source/target and from/to edge formats."""
        nodes = [{"taskId": "a"}, {"taskId": "b"}]
        edges = [{"from": "a", "to": "b"}]
        errors = DAGValidator.validate(nodes, edges)
        assert errors == []


class TestDAGValidatorHasCycle:
    """Tests for DAGValidator._has_cycle()"""

    def test_no_cycle_linear(self):
        """Linear chain should have no cycle."""
        nodes = [{"taskId": "a"}, {"taskId": "b"}, {"taskId": "c"}]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "c"},
        ]
        assert DAGValidator._has_cycle(nodes, edges) is False

    def test_no_cycle_branching(self):
        """Branching DAG should have no cycle."""
        nodes = [{"taskId": "a"}, {"taskId": "b"}, {"taskId": "c"}, {"taskId": "d"}]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "a", "target": "c"},
            {"source": "b", "target": "d"},
            {"source": "c", "target": "d"},
        ]
        assert DAGValidator._has_cycle(nodes, edges) is False

    def test_detects_simple_cycle(self):
        """Simple cycle a -> b -> a should be detected."""
        nodes = [{"taskId": "a"}, {"taskId": "b"}]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "a"},
        ]
        assert DAGValidator._has_cycle(nodes, edges) is True

    def test_detects_self_loop(self):
        """Self-loop should be detected as cycle."""
        nodes = [{"taskId": "a"}]
        edges = [{"source": "a", "target": "a"}]
        assert DAGValidator._has_cycle(nodes, edges) is True

    def test_detects_longer_cycle(self):
        """Longer cycle should be detected."""
        nodes = [{"taskId": "a"}, {"taskId": "b"}, {"taskId": "c"}, {"taskId": "d"}]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "c"},
            {"source": "c", "target": "d"},
            {"source": "d", "target": "a"},
        ]
        assert DAGValidator._has_cycle(nodes, edges) is True


class TestDAGValidatorFindOrphans:
    """Tests for DAGValidator._find_orphans()"""

    def test_no_orphans_when_connected(self):
        """Fully connected graph should have no orphans."""
        nodes = [{"taskId": "a"}, {"taskId": "b"}, {"taskId": "c"}]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "c"},
        ]
        assert DAGValidator._find_orphans(nodes, edges) == []

    def test_finds_single_orphan(self):
        """Should find a single orphan node."""
        nodes = [{"taskId": "a"}, {"taskId": "b"}, {"taskId": "orphan"}]
        edges = [{"source": "a", "target": "b"}]
        orphans = DAGValidator._find_orphans(nodes, edges)
        assert "orphan" in orphans

    def test_finds_multiple_orphans(self):
        """Should find multiple orphan nodes."""
        nodes = [{"taskId": "a"}, {"taskId": "orphan1"}, {"taskId": "orphan2"}]
        edges = []
        orphans = DAGValidator._find_orphans(nodes, edges)
        assert len(orphans) == 3  # All nodes are orphans when no edges

    def test_single_node_not_orphan(self):
        """Single node should not be considered orphan."""
        nodes = [{"taskId": "a"}]
        edges = []
        orphans = DAGValidator._find_orphans(nodes, edges)
        assert orphans == []


class TestDAGValidatorExecutionOrder:
    """Tests for DAGValidator.compute_execution_order()"""

    def test_linear_order(self):
        """Linear chain should return nodes in order."""
        nodes = [{"taskId": "a"}, {"taskId": "b"}, {"taskId": "c"}]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "c"},
        ]
        order = DAGValidator.compute_execution_order(nodes, edges)
        assert order == ["a", "b", "c"]

    def test_independent_nodes_order(self):
        """Independent nodes can be in any order."""
        nodes = [{"taskId": "a"}, {"taskId": "b"}, {"taskId": "c"}]
        edges = []
        order = DAGValidator.compute_execution_order(nodes, edges)
        assert set(order) == {"a", "b", "c"}

    def test_diamond_dependency(self):
        """Diamond dependency pattern."""
        nodes = [{"taskId": "a"}, {"taskId": "b"}, {"taskId": "c"}, {"taskId": "d"}]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "a", "target": "c"},
            {"source": "b", "target": "d"},
            {"source": "c", "target": "d"},
        ]
        order = DAGValidator.compute_execution_order(nodes, edges)
        # a must be first, d must be last
        assert order[0] == "a"
        assert order[-1] == "d"
        # b and c must come between a and d
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_empty_nodes(self):
        """Empty nodes list should return empty order."""
        nodes = []
        edges = []
        order = DAGValidator.compute_execution_order(nodes, edges)
        assert order == []

    def test_single_node(self):
        """Single node should return that node."""
        nodes = [{"taskId": "a"}]
        edges = []
        order = DAGValidator.compute_execution_order(nodes, edges)
        assert order == ["a"]
