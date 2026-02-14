from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.core.utils import now_iso
from app.models.schemas import NodeStatus, TaskStatus
from app.repositories.conflict_repository import ConflictRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.task_repository import TaskRepository
from app.services.agents import ReportAgent, ResearchAgent
from app.services.analyst import AnalystService
from app.services.planner import MasterPlanner
from app.services.progress_hub import ProgressHub
from app.services.retrieval import RetrievalService
from app.services.state_machine import InvalidStateTransition, transition_or_raise
from app.services.writer import WriterService


@dataclass
class TaskControlState:
    paused: bool = False
    aborted: bool = False
    running_task: asyncio.Task | None = None
    completed_nodes: list[str] = field(default_factory=list)


class ExecutionEngine:
    def __init__(
        self,
        repository: TaskRepository,
        planner: MasterPlanner,
        hub: ProgressHub,
        evidence_repository: EvidenceRepository,
        retrieval_service: RetrievalService,
        conflict_repository: ConflictRepository,
        analyst_service: AnalystService,
        writer_service: WriterService,
        research_agent: ResearchAgent | None = None,
        report_agent: ReportAgent | None = None,
    ) -> None:
        self.repository = repository
        self.planner = planner
        self.hub = hub
        self.evidence_repository = evidence_repository
        self.retrieval_service = retrieval_service
        self.conflict_repository = conflict_repository
        self.analyst_service = analyst_service
        self.writer_service = writer_service
        self.research_agent = research_agent or ResearchAgent(retrieval_service=retrieval_service)
        self.report_agent = report_agent or ReportAgent(writer_service=writer_service)
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

    async def recover(self, task_id: str) -> None:
        snapshot = self.repository.load_snapshot(task_id)
        control = self._control.setdefault(task_id, TaskControlState())
        if snapshot:
            control.completed_nodes = snapshot.get("completed_nodes", [])
        control.paused = False
        await self.start(task_id)

    async def _run_task(self, task_id: str, current_status: TaskStatus) -> None:
        try:
            await self.hub.emit(task_id, "TASK_STARTED", {"taskId": task_id, "status": current_status.value})
            task = self.repository.get_task(task_id)
            config = task.config
            if not task.dag or not task.dag.nodes:
                self.repository.update_status(task_id, transition_or_raise(task.status, TaskStatus.PLANNING))
                dag = self.planner.build_dag(task_id, task.title, task.description, config)
                self.repository.save_dag(task_id, dag)
                await self.hub.emit(
                    task_id,
                    "TASK_PROGRESS",
                    {
                        "taskId": task_id,
                        "progress": 20,
                        "state": "PLANNING",
                        "phase": "BUILDING_PLAN",
                    },
                )

            current = self.repository.get_task(task_id)
            if current.status == TaskStatus.SUSPENDED:
                self.repository.update_status(task_id, TaskStatus.EXECUTING)
            else:
                self.repository.update_status(task_id, transition_or_raise(current.status, TaskStatus.EXECUTING))

            dag = self.repository.get_dag(task_id)
            executable_nodes = [n for n in dag.nodes if n.taskId != task_id and n.status != NodeStatus.PRUNED]
            snapshot = self.repository.load_snapshot(task_id)
            if snapshot:
                control = self._control.setdefault(task_id, TaskControlState())
                control.completed_nodes = snapshot.get("completed_nodes", control.completed_nodes)
            total = max(1, len(executable_nodes))
            for idx, node in enumerate(executable_nodes, start=1):
                control = self._control.setdefault(task_id, TaskControlState())
                if node.taskId in control.completed_nodes:
                    continue
                while control.paused and not control.aborted:
                    await asyncio.sleep(0.2)
                if control.aborted:
                    await self.hub.emit(task_id, "ERROR", {"taskId": task_id, "error": "Task aborted by user"})
                    return
                self.repository.update_node_status(task_id, node.taskId, NodeStatus.RUNNING, node.metadata.infoGainScore)
                await asyncio.sleep(0.2)
                query = f"{task.title} {node.title}"
                searching_progress = 20 + int(((idx - 1) / total) * 60)
                await self.hub.emit(
                    task_id,
                    "TASK_PROGRESS",
                    {
                        "taskId": task_id,
                        "progress": searching_progress,
                        "currentNode": node.taskId,
                        "currentNodeTitle": node.title,
                        "searchQuery": query,
                        "state": "EXECUTING",
                        "phase": "SEARCHING",
                    },
                )
                evidences = await self.research_agent.collect_evidence(
                    task_id=task_id,
                    node_id=node.taskId,
                    query=query,
                    sources=task.config.searchSources,
                )
                self.evidence_repository.save_many(evidences)
                for ev in evidences:
                    await self.hub.emit(
                        task_id,
                        "EVIDENCE_FOUND",
                        {"taskId": task_id, "nodeId": node.taskId, "evidence": ev.model_dump()},
                    )
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
                        "currentNodeTitle": node.title,
                        "searchQuery": query,
                        "evidenceCount": len(evidences),
                        "state": "EXECUTING",
                        "phase": "NODE_COMPLETED",
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
                        "evidence_cache": {ev.id: ev.url for ev in evidences},
                        "conflict_records": [],
                    },
                )

            evidences = self.evidence_repository.list(task_id=task_id, limit=1000).items
            for ev in evidences:
                ev.score = self.analyst_service.score(ev)
            conflicts = self.analyst_service.detect_conflicts(task_id=task_id, evidences=evidences, threshold=0.15)
            if conflicts:
                self.repository.update_status(task_id, transition_or_raise(TaskStatus.EXECUTING, TaskStatus.REVIEWING))
                self.conflict_repository.save_many(conflicts)
                await self.hub.emit(
                    task_id,
                    "TASK_PROGRESS",
                    {
                        "taskId": task_id,
                        "progress": 85,
                        "state": "REVIEWING",
                        "phase": "REVIEWING_CONFLICTS",
                        "conflictCount": len(conflicts),
                    },
                )
                # Single-user default: continue with unresolved conflicts recorded for later voting.
                self.repository.update_status(task_id, transition_or_raise(TaskStatus.REVIEWING, TaskStatus.SYNTHESIZING))
            else:
                self.repository.update_status(task_id, transition_or_raise(TaskStatus.EXECUTING, TaskStatus.SYNTHESIZING))
            await self.hub.emit(
                task_id,
                "TASK_PROGRESS",
                {"taskId": task_id, "progress": 90, "state": "SYNTHESIZING", "phase": "OUTLINING"},
            )
            await asyncio.sleep(0.1)
            dag = self.repository.get_dag(task_id)
            sections = [
                (node.taskId, f"{node.title}\n\n{node.description}")
                for node in dag.nodes
                if node.taskId != task_id and node.status != NodeStatus.PRUNED
            ]
            total_sections = max(1, len(sections))
            for section_idx, (_, section_text) in enumerate(sections, start=1):
                section_title = section_text.splitlines()[0].strip() if section_text else ""
                write_progress = 90 + int((section_idx / total_sections) * 6)
                await self.hub.emit(
                    task_id,
                    "TASK_PROGRESS",
                    {
                        "taskId": task_id,
                        "progress": write_progress,
                        "state": "SYNTHESIZING",
                        "phase": "WRITING_SECTION",
                        "currentSectionTitle": section_title or f"Section {section_idx}",
                    },
                )
            md_path, bib_path, _ = await asyncio.to_thread(
                self.report_agent.generate_report,
                task_id=task_id,
                task_title=task.title,
                task_description=task.description,
                sections=sections,
                evidences=evidences,
                locked_sections=set(),
            )
            self.repository.update_status(task_id, transition_or_raise(TaskStatus.SYNTHESIZING, TaskStatus.FINALIZING))
            await self.hub.emit(
                task_id,
                "TASK_PROGRESS",
                {"taskId": task_id, "progress": 98, "state": "FINALIZING", "phase": "PERSISTING_REPORT"},
            )
            self.repository.set_report_path(task_id, md_path)
            self.repository.update_status(task_id, transition_or_raise(TaskStatus.FINALIZING, TaskStatus.COMPLETED))
            await self.hub.emit(
                task_id,
                "TASK_COMPLETED",
                {"taskId": task_id, "progress": 100, "reportPath": md_path, "bibPath": bib_path},
            )
        except InvalidStateTransition as exc:
            self.repository.update_status(task_id, TaskStatus.FAILED, last_error=str(exc))
            await self.hub.emit(task_id, "ERROR", {"taskId": task_id, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self.repository.update_status(task_id, TaskStatus.FAILED, last_error=str(exc))
            await self.hub.emit(task_id, "ERROR", {"taskId": task_id, "error": f"Unhandled error: {exc}"})
