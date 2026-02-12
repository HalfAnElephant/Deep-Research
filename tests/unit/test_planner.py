from app.models.schemas import TaskConfig
from app.services.planner import MasterPlanner


def test_planner_generates_bounded_dag() -> None:
    planner = MasterPlanner()
    dag = planner.build_dag("root", "Root", "desc", TaskConfig(maxDepth=3, maxNodes=20, priority=3))
    assert len(dag.nodes) <= 20
    assert dag.nodes[0].taskId == "root"
    assert all(node.metadata.searchDepth <= 3 for node in dag.nodes)


def test_planner_generates_acyclic_edges() -> None:
    planner = MasterPlanner()
    dag = planner.build_dag("root", "Root", "desc", TaskConfig(maxDepth=2, maxNodes=10, priority=3))
    edges = {(edge.from_, edge.to) for edge in dag.edges}
    reverse = {(dst, src) for src, dst in edges}
    assert not edges.intersection(reverse)
