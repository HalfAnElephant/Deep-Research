from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.core.utils import now_iso
from app.models.schemas import NodeStatus, TaskStatus
from app.repositories.task_repository import TaskRepository
from app.services.planner import MasterPlanner
from app.services.progress_hub import ProgressHub
from app.services.state_machine import InvalidStateTransition, transition_or_raise


@dataclass
class TaskControlState:
    paused: bool = False
    aborted: bool = False
    running_task: asyncio.Task | None = None
    completed_nodes: list[str] = field(default_factory=list)


class ExecutionEngine:
    def __init__(self, repository: TaskRepository, planner: MasterPlanner, hub: ProgressHub) -> None:
        self.repository = repository
        self.planner = planner
        self.hub = hub
        self._control: dict[str, TaskControlState] = {}

    async def start(self, task_id: str) -> None:
        task = self.repository.get_task(task_id)
        control = self._control.setdefault(task_id, TaskControlState())
        control.paused = False
        control.aborted = False
        if control.running_task and not control.running_task.done():
            return
        loop = asyncio.get_running_loop()
        control.running_task = loop.create_task(self._run_task(task_id, task.status))

    def pause(self, task_id: str) -> None:
        control = self._control.setdefault(task_id, TaskControlState())
        control.paused = True
        self.repository.update_status(task_id, TaskStatus.SUSPENDED)

    async def resume(self, task_id: str) -> None:
        control = self._control.setdefault(task_id, TaskControlState())
        control.paused = False
        await self.start(task_id)

    def abort(self, task_id: str) -> None:
        control = self._control.setdefault(task_id, TaskControlState())
        control.aborted = True
        self.repository.update_status(task_id, TaskStatus.ABORTED)

    async def _run_task(self, task_id: str, current_status: TaskStatus) -> None:
        try:
            await self.hub.emit(task_id, "TASK_STARTED", {"taskId": task_id, "status": current_status.value})
            task = self.repository.get_task(task_id)
            config = task.config
            if not task.dag or not task.dag.nodes:
                self.repository.update_status(task_id, transition_or_raise(task.status, TaskStatus.PLANNING))
                dag = self.planner.build_dag(task_id, task.title, task.description, config)
                self.repository.save_dag(task_id, dag)
                await self.hub.emit(task_id, "TASK_PROGRESS", {"taskId": task_id, "progress": 20, "state": "PLANNING"})

            current = self.repository.get_task(task_id)
            if current.status == TaskStatus.SUSPENDED:
                self.repository.update_status(task_id, TaskStatus.EXECUTING)
            else:
                self.repository.update_status(task_id, transition_or_raise(current.status, TaskStatus.EXECUTING))

            dag = self.repository.get_dag(task_id)
            executable_nodes = [n for n in dag.nodes if n.taskId != task_id and n.status != NodeStatus.PRUNED]
            total = max(1, len(executable_nodes))
            for idx, node in enumerate(executable_nodes, start=1):
                control = self._control.setdefault(task_id, TaskControlState())
                while control.paused and not control.aborted:
                    await asyncio.sleep(0.2)
                if control.aborted:
                    await self.hub.emit(task_id, "ERROR", {"taskId": task_id, "error": "Task aborted by user"})
                    return
                self.repository.update_node_status(task_id, node.taskId, NodeStatus.RUNNING, node.metadata.infoGainScore)
                await asyncio.sleep(0.2)
                self.repository.update_node_status(task_id, node.taskId, NodeStatus.COMPLETED, node.metadata.infoGainScore)
                control.completed_nodes.append(node.taskId)
                progress = 20 + int((idx / total) * 60)
                await self.hub.emit(
                    task_id,
                    "TASK_PROGRESS",
                    {
                        "taskId": task_id,
                        "progress": progress,
                        "currentNode": node.taskId,
                        "state": "EXECUTING",
                    },
                )
                self.repository.save_snapshot(
                    task_id,
                    {
                        "task_id": task_id,
                        "timestamp": now_iso(),
                        "fsm_state": TaskStatus.EXECUTING.value,
                        "completed_nodes": control.completed_nodes,
                        "pending_nodes": [n.taskId for n in executable_nodes if n.taskId not in control.completed_nodes],
                        "evidence_cache": {},
                        "conflict_records": [],
                    },
                )

            self.repository.update_status(task_id, transition_or_raise(TaskStatus.EXECUTING, TaskStatus.SYNTHESIZING))
            await self.hub.emit(task_id, "TASK_PROGRESS", {"taskId": task_id, "progress": 90, "state": "SYNTHESIZING"})
            await asyncio.sleep(0.1)
            self.repository.update_status(task_id, transition_or_raise(TaskStatus.SYNTHESIZING, TaskStatus.FINALIZING))
            self.repository.update_status(task_id, transition_or_raise(TaskStatus.FINALIZING, TaskStatus.COMPLETED))
            await self.hub.emit(task_id, "TASK_COMPLETED", {"taskId": task_id, "progress": 100})
        except InvalidStateTransition as exc:
            self.repository.update_status(task_id, TaskStatus.FAILED, last_error=str(exc))
            await self.hub.emit(task_id, "ERROR", {"taskId": task_id, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self.repository.update_status(task_id, TaskStatus.FAILED, last_error=str(exc))
            await self.hub.emit(task_id, "ERROR", {"taskId": task_id, "error": f"Unhandled error: {exc}"})
