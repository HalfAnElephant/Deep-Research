from app.models.schemas import NodeStatus, TaskMetadata, TaskNode
from app.services.search_strategy import BestFirstSearchStrategy, BranchScorer


def _make_node(task_id: str, *, branch_score: float, info_gain: float, depth: int) -> TaskNode:
    return TaskNode(
        taskId=task_id,
        parentTaskId=None,
        title=f"Node {task_id}",
        description="desc",
        status=NodeStatus.PENDING,
        priority=3,
        dependencies=[],
        children=[],
        metadata=TaskMetadata(
            estimatedTokenCost=100,
            searchDepth=depth,
            infoGainScore=info_gain,
            branchId="root",
            branchScore=branch_score,
            branchDepth=depth,
            createdAt="2026-01-01T00:00:00Z",
            updatedAt="2026-01-01T00:00:00Z",
        ),
        output=[],
    )


def test_best_first_orders_by_branch_score_then_depth() -> None:
    strategy = BestFirstSearchStrategy()
    nodes = [
        _make_node("n1", branch_score=0.2, info_gain=0.8, depth=1),
        _make_node("n2", branch_score=0.9, info_gain=0.3, depth=2),
        _make_node("n3", branch_score=0.9, info_gain=0.7, depth=1),
    ]

    ordered = strategy.order(nodes)
    assert [node.taskId for node in ordered] == ["n3", "n2", "n1"]


def test_branch_scorer_reflects_evidence_gain() -> None:
    scorer = BranchScorer()
    node = _make_node("n1", branch_score=0.0, info_gain=0.5, depth=1)

    without_evidence = scorer.score(node, evidence_count=0)
    with_evidence = scorer.score(node, evidence_count=5)

    assert 0.0 <= without_evidence <= 1.0
    assert 0.0 <= with_evidence <= 1.0
    assert with_evidence > without_evidence
