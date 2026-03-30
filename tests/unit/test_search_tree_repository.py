from app.core.database import init_db
from app.core.utils import new_id, now_iso
from app.models.schemas import BranchAction, BranchRepairAttempt, BranchScore, NodeStatus, SearchBranch, TaskConfig
from app.repositories.task_repository import TaskRepository


def test_search_branch_persistence_roundtrip() -> None:
    init_db()
    repo = TaskRepository()
    task_id = new_id()
    repo.create_task(
        task_id=task_id,
        title="search tree test",
        description="verify branch persistence",
        config=TaskConfig(),
    )

    branch = SearchBranch(
        branchId="branch-root",
        rootNodeId="node-1",
        depth=0,
        status=NodeStatus.RUNNING,
        score=BranchScore(infoGain=0.5, evidenceStrength=0.4, feasibility=0.7, total=0.56),
        nodeIds=["node-1", "node-2"],
    )
    repo.upsert_search_branch(task_id, branch)

    action = BranchAction(
        actionId=new_id(),
        taskId=task_id,
        branchId="branch-root",
        actionType="NODE_EXECUTED",
        actionInput={"nodeId": "node-1"},
        actionOutput={"evidenceCount": 3},
        scoreBefore=0.2,
        scoreAfter=0.56,
        status="COMPLETED",
        createdAt=now_iso(),
    )
    repo.append_branch_action(action)

    repair = BranchRepairAttempt(
        repairId=new_id(),
        taskId=task_id,
        branchId="branch-root",
        nodeId="node-1",
        attempt=1,
        diagnosis="network timeout",
        proposal="retry",
        succeeded=True,
        createdAt=now_iso(),
    )
    repo.append_branch_repair(repair)

    loaded = repo.list_search_branches(task_id)
    assert len(loaded) == 1
    assert loaded[0].branchId == "branch-root"
    assert loaded[0].score.total == 0.56
    assert loaded[0].status == NodeStatus.RUNNING
