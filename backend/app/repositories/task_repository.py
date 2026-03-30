from __future__ import annotations

import json
from typing import Any

from app.core.database import get_connection
from app.core.utils import now_iso
from app.models.schemas import BranchAction, BranchRepairAttempt, BranchScore, DAGGraph, DAGEdge, NodeStatus, ResearchScoreCard, SearchBranch, TaskConfig, TaskNode, TaskResponse, TaskStatus


class TaskRepository:
    def create_task(self, task_id: str, title: str, description: str, config: TaskConfig) -> TaskResponse:
        ts = now_iso()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO tasks(task_id, title, description, status, config_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, title, description, TaskStatus.READY.value,
                 config.model_dump_json(), ts, ts),
            )
            conn.commit()
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> TaskResponse:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        return TaskResponse(
            taskId=row["task_id"],
            title=row["title"],
            description=row["description"],
            status=TaskStatus(row["status"]),
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
            config=TaskConfig.model_validate_json(row["config_json"]),
            reportPath=row["report_path"],
            researchScoreCard=ResearchScoreCard.model_validate_json(
                row["research_scorecard_json"]) if row["research_scorecard_json"] else None,
            dag=self.get_dag(task_id, allow_empty=True),
        )

    def list_tasks(self) -> list[TaskResponse]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT task_id FROM tasks ORDER BY created_at DESC").fetchall()
        return [self.get_task(row["task_id"]) for row in rows]

    def update_task(self, task_id: str, *, title: str | None, description: str | None, config: TaskConfig | None) -> TaskResponse:
        current = self.get_task(task_id)
        next_title = title if title is not None else current.title
        next_desc = description if description is not None else current.description
        next_config = config if config is not None else current.config
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET title = ?, description = ?, config_json = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (next_title, next_desc,
                 next_config.model_dump_json(), now_iso(), task_id),
            )
            conn.commit()
        return self.get_task(task_id)

    def delete_task(self, task_id: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM task_nodes WHERE task_id = ?", (task_id,))
            conn.execute(
                "DELETE FROM search_branches WHERE task_id = ?", (task_id,))
            conn.execute(
                "DELETE FROM branch_actions WHERE task_id = ?", (task_id,))
            conn.execute(
                "DELETE FROM branch_repairs WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM snapshots WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            conn.commit()

    def update_status(self, task_id: str, status: TaskStatus, *, last_error: str | None = None) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, last_error = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (status.value, last_error, now_iso(), task_id),
            )
            conn.commit()

    def set_report_path(self, task_id: str, report_path: str) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET report_path = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (report_path, now_iso(), task_id),
            )
            conn.commit()

    def set_research_scorecard(self, task_id: str, scorecard: ResearchScoreCard) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET research_scorecard_json = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (scorecard.model_dump_json(), now_iso(), task_id),
            )
            conn.commit()

    def save_dag(self, task_id: str, dag: DAGGraph) -> None:
        ts = now_iso()
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM task_nodes WHERE task_id = ?", (task_id,))
            for node in dag.nodes:
                conn.execute(
                    """
                    INSERT INTO task_nodes(
                      task_id, node_id, parent_task_id, title, description, status, priority,
                                            search_depth, info_gain_score, branch_id, branch_score, branch_depth, position_x, position_y,
                      dependencies_json, children_json, output_json,
                      created_at, updated_at
                                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        node.taskId,
                        node.parentTaskId,
                        node.title,
                        node.description,
                        node.status.value,
                        node.priority,
                        node.metadata.searchDepth,
                        node.metadata.infoGainScore,
                        node.metadata.branchId,
                        node.metadata.branchScore,
                        node.metadata.branchDepth,
                        node.metadata.positionX,
                        node.metadata.positionY,
                        json.dumps(node.dependencies),
                        json.dumps(node.children),
                        json.dumps(node.output),
                        ts,
                        ts,
                    ),
                )
            conn.commit()

    def get_dag(self, task_id: str, *, allow_empty: bool = False) -> DAGGraph:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM task_nodes WHERE task_id = ? ORDER BY search_depth ASC, created_at ASC",
                (task_id,),
            ).fetchall()
        if not rows and allow_empty:
            return DAGGraph(nodes=[], edges=[])
        if not rows:
            raise KeyError(task_id)
        nodes: list[TaskNode] = []
        edges: list[DAGEdge] = []
        for row in rows:
            node = TaskNode(
                taskId=row["node_id"],
                parentTaskId=row["parent_task_id"],
                title=row["title"],
                description=row["description"],
                status=NodeStatus(row["status"]),
                priority=row["priority"],
                dependencies=json.loads(row["dependencies_json"]),
                children=json.loads(row["children_json"]),
                metadata={
                    "estimatedTokenCost": 0,
                    "searchDepth": row["search_depth"],
                    "infoGainScore": row["info_gain_score"],
                    "branchId": row["branch_id"],
                    "branchScore": row["branch_score"] or 0.0,
                    "branchDepth": row["branch_depth"] or 0,
                    "positionX": row["position_x"],
                    "positionY": row["position_y"],
                    "createdAt": row["created_at"],
                    "updatedAt": row["updated_at"],
                },
                output=json.loads(row["output_json"]),
            )
            nodes.append(node)
            for dep in node.dependencies:
                edges.append(DAGEdge.model_validate(
                    {"from": dep, "to": node.taskId, "type": "DEPENDS_ON"}))
        return DAGGraph(nodes=nodes, edges=edges)

    def update_node_status(self, task_id: str, node_id: str, status: NodeStatus, info_gain: float) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE task_nodes
                SET status = ?, info_gain_score = ?, updated_at = ?
                WHERE task_id = ? AND node_id = ?
                """,
                (status.value, info_gain, now_iso(), task_id, node_id),
            )
            conn.commit()

    def update_node_branch_score(self, task_id: str, node_id: str, branch_score: float) -> None:
        normalized = max(0.0, min(1.0, float(branch_score)))
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE task_nodes
                SET branch_score = ?, updated_at = ?
                WHERE task_id = ? AND node_id = ?
                """,
                (normalized, now_iso(), task_id, node_id),
            )
            conn.commit()

    def prune_nodes(self, task_id: str, node_ids: list[str]) -> None:
        if not node_ids:
            return
        placeholders = ", ".join("?" for _ in node_ids)
        with get_connection() as conn:
            conn.execute(
                f"""
                UPDATE task_nodes
                SET status = ?, updated_at = ?
                WHERE task_id = ? AND node_id IN ({placeholders})
                """,
                (NodeStatus.PRUNED.value, now_iso(), task_id, *node_ids),
            )
            conn.commit()

    def save_snapshot(self, task_id: str, snapshot: dict[str, Any]) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO snapshots(task_id, snapshot_json, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                  snapshot_json = excluded.snapshot_json,
                  updated_at = excluded.updated_at
                """,
                (task_id, json.dumps(snapshot), now_iso()),
            )
            conn.commit()

    def load_snapshot(self, task_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT snapshot_json FROM snapshots WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return json.loads(row["snapshot_json"])

    def upsert_search_branch(self, task_id: str, branch: SearchBranch) -> None:
        ts = now_iso()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO search_branches(
                    task_id, branch_id, parent_branch_id, root_node_id, branch_type, branch_goal,
                    depth, status, score_info_gain, score_evidence_strength, score_feasibility, score_total,
                    prune_reason, debug_depth, worker_id, node_ids_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id, branch_id) DO UPDATE SET
                    parent_branch_id = excluded.parent_branch_id,
                    root_node_id = excluded.root_node_id,
                    branch_type = excluded.branch_type,
                    branch_goal = excluded.branch_goal,
                    depth = excluded.depth,
                    status = excluded.status,
                    score_info_gain = excluded.score_info_gain,
                    score_evidence_strength = excluded.score_evidence_strength,
                    score_feasibility = excluded.score_feasibility,
                    score_total = excluded.score_total,
                    prune_reason = excluded.prune_reason,
                    debug_depth = excluded.debug_depth,
                    worker_id = excluded.worker_id,
                    node_ids_json = excluded.node_ids_json,
                    updated_at = excluded.updated_at
                """,
                (
                    task_id,
                    branch.branchId,
                    branch.parentBranchId,
                    branch.rootNodeId,
                    branch.branchType,
                    branch.branchGoal,
                    branch.depth,
                    branch.status.value,
                    branch.score.infoGain,
                    branch.score.evidenceStrength,
                    branch.score.feasibility,
                    branch.score.total,
                    branch.pruneReason,
                    branch.debugDepth,
                    branch.workerId,
                    json.dumps(branch.nodeIds),
                    ts,
                    ts,
                ),
            )
            conn.commit()

    def list_search_branches(self, task_id: str) -> list[SearchBranch]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM search_branches WHERE task_id = ? ORDER BY depth ASC, created_at ASC",
                (task_id,),
            ).fetchall()
        branches: list[SearchBranch] = []
        for row in rows:
            branches.append(
                SearchBranch(
                    branchId=row["branch_id"],
                    parentBranchId=row["parent_branch_id"],
                    rootNodeId=row["root_node_id"],
                    branchType=row["branch_type"],
                    branchGoal=row["branch_goal"],
                    depth=row["depth"],
                    status=NodeStatus(row["status"]),
                    score=BranchScore(
                        infoGain=float(row["score_info_gain"] or 0.0),
                        evidenceStrength=float(row["score_evidence_strength"] or 0.0),
                        feasibility=float(row["score_feasibility"] or 0.0),
                        total=float(row["score_total"] or 0.0),
                    ),
                    pruneReason=row["prune_reason"],
                    debugDepth=row["debug_depth"],
                    workerId=row["worker_id"],
                    nodeIds=json.loads(row["node_ids_json"]),
                )
            )
        return branches

    def append_branch_action(self, action: BranchAction) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO branch_actions(
                  action_id, task_id, branch_id, action_type,
                  action_input_json, action_output_json,
                  score_before, score_after, status, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action.actionId,
                    action.taskId,
                    action.branchId,
                    action.actionType,
                    json.dumps(action.actionInput),
                    json.dumps(action.actionOutput),
                    action.scoreBefore,
                    action.scoreAfter,
                    action.status,
                    action.createdAt,
                ),
            )
            conn.commit()

    def append_branch_repair(self, repair: BranchRepairAttempt) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO branch_repairs(
                  repair_id, task_id, branch_id, node_id,
                  attempt, diagnosis, proposal, succeeded, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repair.repairId,
                    repair.taskId,
                    repair.branchId,
                    repair.nodeId,
                    repair.attempt,
                    repair.diagnosis,
                    repair.proposal,
                    1 if repair.succeeded else 0,
                    repair.createdAt,
                ),
            )
            conn.commit()
