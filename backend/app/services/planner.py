from __future__ import annotations

from collections import deque

from app.core.utils import new_id, now_iso
from app.models.schemas import DAGGraph, DAGEdge, NodeStatus, TaskConfig, TaskMetadata, TaskNode


class MasterPlanner:
    """Builds a bounded DAG with BFS + DFS expansion and simple pruning."""

    def build_dag(self, root_task_id: str, title: str, description: str, config: TaskConfig) -> DAGGraph:
        ts = now_iso()
        root = TaskNode(
            taskId=root_task_id,
            parentTaskId=None,
            title=title,
            description=description,
            status=NodeStatus.PENDING,
            priority=config.priority,
            dependencies=[],
            children=[],
            metadata=TaskMetadata(
                estimatedTokenCost=0,
                searchDepth=0,
                infoGainScore=1.0,
                createdAt=ts,
                updatedAt=ts,
            ),
            output=[],
        )
        first_topics = ["背景研究", "现状分析", "挑战识别"]
        nodes = [root]
        edges: list[DAGEdge] = []
        q: deque[tuple[TaskNode, int]] = deque([(root, 0)])
        total_nodes = 1
        low_gain_streak = 0

        while q and total_nodes < config.maxNodes:
            parent, depth = q.popleft()
            if depth >= config.maxDepth:
                continue
            candidates = first_topics if depth == 0 else [f"{parent.title} - 深入方向"]
            for ctitle in candidates:
                if total_nodes >= config.maxNodes:
                    break
                node_id = new_id()
                info_gain = self._estimate_info_gain(node_id, depth + 1)
                status = NodeStatus.PRUNED if low_gain_streak >= 1 and info_gain < 0.2 else NodeStatus.PENDING
                if info_gain < 0.2:
                    low_gain_streak += 1
                else:
                    low_gain_streak = 0
                node = TaskNode(
                    taskId=node_id,
                    parentTaskId=parent.taskId,
                    title=ctitle,
                    description=f"{ctitle}: {description}",
                    status=status,
                    priority=max(1, config.priority - depth),
                    dependencies=[parent.taskId],
                    children=[],
                    metadata=TaskMetadata(
                        estimatedTokenCost=800 + depth * 200,
                        searchDepth=depth + 1,
                        infoGainScore=info_gain,
                        createdAt=ts,
                        updatedAt=ts,
                    ),
                    output=[],
                )
                nodes.append(node)
                parent.children.append(node_id)
                edges.append(DAGEdge.model_validate({"from": parent.taskId, "to": node_id}))
                total_nodes += 1
                q.append((node, depth + 1))

        return DAGGraph(nodes=nodes, edges=edges)

    @staticmethod
    def _estimate_info_gain(seed: str, depth: int) -> float:
        value = (sum(ord(ch) for ch in seed) % 100) / 100.0
        return max(0.05, round(value * (1.0 / (depth + 0.5)), 2))
