from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
import logging
from typing import Any, Awaitable, Callable

from app.core.utils import now_iso
from app.models.schemas import NodeStatus, TaskStatus
from app.repositories.conflict_repository import ConflictRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.task_repository import TaskRepository
from app.services.agents import ReportAgent, ResearchAgent
from app.services.analyst import AnalystService
from app.services.longcat_client import longcat_client
from app.services.planner import MasterPlanner
from app.services.progress_hub import ProgressHub
from app.services.retrieval import RetrievalService
from app.services.state_machine import InvalidStateTransition, transition_or_raise
from app.services.writer import WriterService
from app.services.four_agents.checking.agent import CheckingAgent

logger = logging.getLogger(__name__)


@dataclass
class TaskControlState:
    paused: bool = False
    aborted: bool = False
    running_task: asyncio.Task | None = None
    completed_nodes: list[str] = field(default_factory=list)


@dataclass
class RuntimeProgressState:
    started_mono: float
    last_progress_mono: float
    state: str = "READY"
    phase: str = "INITIALIZING"
    progress: int = 0
    detail: str = ""
    stall_notified: bool = False


@dataclass
class DagNodeRuntimeState:
    first_started_mono: float | None = None
    last_started_mono: float | None = None
    completed_mono: float | None = None
    attempts: int = 0


class ExecutionEngine:
    HEARTBEAT_INTERVAL_SECONDS = 6
    STALL_WARNING_SECONDS = 25

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
        checking_agent: CheckingAgent | None = None,
        event_listener: Callable[[str, str, dict],
                                 Awaitable[None]] | None = None,
    ) -> None:
        self.repository = repository
        self.planner = planner
        self.hub = hub
        self.evidence_repository = evidence_repository
        self.retrieval_service = retrieval_service
        self.conflict_repository = conflict_repository
        self.analyst_service = analyst_service
        self.writer_service = writer_service
        self.research_agent = research_agent or ResearchAgent(
            retrieval_service=retrieval_service)
        # 如果未提供 report_agent，创建时传入 checking_agent
        if report_agent is None:
            self.report_agent = ReportAgent(
                writer_service=writer_service,
                checking_agent=checking_agent
            )
        else:
            self.report_agent = report_agent
        self.checking_agent = checking_agent
        self.event_listener = event_listener
        self._control: dict[str, TaskControlState] = {}
        self._runtime_progress: dict[str, RuntimeProgressState] = {}
        self._node_runtime: dict[str, dict[str, DagNodeRuntimeState]] = {}
        self._last_agent_state: dict[str, dict[str, tuple[str, int, str]]] = {}

    def _phase_to_agent_type(self, phase: str) -> str:
        phase_upper = (phase or "").upper()
        if "CHECK" in phase_upper or "REVIEW" in phase_upper:
            return "CHECKING"
        if any(token in phase_upper for token in ("WRIT", "SYNTH", "FINAL", "PERSIST", "MATERIAL")):
            return "WRITING"
        if "PLAN" in phase_upper or "BUILD" in phase_upper:
            return "PLANNING"
        return "IDEATION"

    def _normalize_agent_status(self, raw_status: str) -> str:
        value = (raw_status or "").upper().strip()
        if "FAIL" in value or "ERROR" in value or "ABORT" in value:
            return "FAILED"
        if value in {"COMPLETED", "DONE", "SUCCESS", "PASSED", "REVIEW_PASSED"}:
            return "COMPLETED"
        if value in {
            "RUNNING",
            "EXECUTING",
            "PLANNING",
            "REVIEWING",
            "SYNTHESIZING",
            "FINALIZING",
            "REPORT_REVISING",
        }:
            return "RUNNING"
        return "IDLE"

    def _build_writing_preview(self, section_text: str) -> str:
        lines = [line.strip()
                 for line in section_text.splitlines() if line.strip()]
        if not lines:
            return ""
        content_lines = lines[1:] if len(lines) > 1 else lines
        preview = " ".join(content_lines)
        if len(preview) > 180:
            preview = f"{preview[:180]}..."
        return preview

    async def _emit_agent_status(self, task_id: str, payload: dict[str, Any]) -> None:
        agent_type = str(payload.get("agentType") or "").strip()
        if not agent_type:
            return
        status = str(payload.get("status") or "IDLE").strip().upper()
        progress_raw = payload.get("progress")
        progress = int(progress_raw) if isinstance(
            progress_raw, (int, float)) else 0
        progress = max(0, min(100, progress))
        activity = str(payload.get("currentActivity") or "").strip()

        task_cache = self._last_agent_state.setdefault(task_id, {})
        previous = task_cache.get(agent_type)
        current_signature = (status, progress, activity)
        if previous == current_signature:
            return
        task_cache[agent_type] = current_signature

        await self.hub.emit(task_id, "AGENT_STATUS", payload)
        if self.event_listener is not None:
            try:
                await self.event_listener(task_id, "AGENT_STATUS", payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Event listener failed for task=%s event=%s: %s", task_id, "AGENT_STATUS", exc)

    async def _emit_agent_status_from_task_event(self, task_id: str, event: str, payload: dict[str, Any]) -> None:
        if event not in {"TASK_PROGRESS", "TASK_HEARTBEAT", "STALL_WARNING", "TASK_COMPLETED", "TASK_FAILED", "TASK_ABORTED", "ERROR"}:
            return

        if event == "TASK_COMPLETED":
            for agent_type in ("IDEATION", "PLANNING", "WRITING", "CHECKING"):
                await self._emit_agent_status(
                    task_id,
                    {
                        "taskId": task_id,
                        "agentType": agent_type,
                        "status": "COMPLETED",
                        "progress": 100,
                        "currentActivity": "阶段完成",
                        "phase": "TASK_COMPLETED",
                        "updatedAt": now_iso(),
                    },
                )
            return

        runtime = self._runtime_progress.get(task_id)
        phase = str(payload.get("phase") or "").strip()
        if not phase and runtime is not None:
            phase = runtime.phase
        if phase.upper() in {"HEARTBEAT", "STALL_WARNING"}:
            phase = str(payload.get("currentPhase") or payload.get(
                "phase") or (runtime.phase if runtime else "")).strip()
        if not phase:
            phase = "UNKNOWN"

        raw_state = str(payload.get("state") or (
            runtime.state if runtime else "RUNNING")).strip() or "RUNNING"
        status = self._normalize_agent_status(raw_state)
        if event == "STALL_WARNING" and status == "IDLE":
            status = "RUNNING"
        if event in {"TASK_FAILED", "TASK_ABORTED", "ERROR"}:
            status = "FAILED"

        progress_raw = payload.get("progress")
        progress = int(progress_raw) if isinstance(progress_raw, (int, float)) else (
            runtime.progress if runtime is not None else 0)
        progress = max(0, min(100, int(progress)))
        detail = str(
            payload.get("currentWritingContent")
            or payload.get("detail")
            or payload.get("currentSectionTitle")
            or payload.get("currentNodeTitle")
            or ""
        ).strip()

        await self._emit_agent_status(
            task_id,
            {
                "taskId": task_id,
                "agentType": self._phase_to_agent_type(phase),
                "status": status,
                "progress": progress,
                "currentActivity": detail or f"处理中 ({phase})",
                "phase": phase,
                "updatedAt": now_iso(),
            },
        )

    def _ensure_dag_node_runtime(self, task_id: str) -> None:
        runtime = self._node_runtime.setdefault(task_id, {})
        try:
            dag = self.repository.get_dag(task_id)
        except Exception:
            return
        for node in dag.nodes:
            if node.taskId == task_id:
                continue
            runtime.setdefault(node.taskId, DagNodeRuntimeState())

    def _record_node_start(self, task_id: str, node_id: str, now_mono: float) -> None:
        self._ensure_dag_node_runtime(task_id)
        node_runtime = self._node_runtime.setdefault(
            task_id, {}).setdefault(node_id, DagNodeRuntimeState())
        if node_runtime.first_started_mono is None:
            node_runtime.first_started_mono = now_mono
        node_runtime.last_started_mono = now_mono
        node_runtime.completed_mono = None
        node_runtime.attempts += 1

    def _record_node_completed(self, task_id: str, node_id: str, now_mono: float) -> None:
        self._ensure_dag_node_runtime(task_id)
        node_runtime = self._node_runtime.setdefault(
            task_id, {}).setdefault(node_id, DagNodeRuntimeState())
        if node_runtime.first_started_mono is None:
            node_runtime.first_started_mono = now_mono
            node_runtime.attempts = max(1, node_runtime.attempts)
        node_runtime.completed_mono = now_mono

    def _attach_dag_snapshot(self, task_id: str, payload: dict[str, Any]) -> None:
        self._ensure_dag_node_runtime(task_id)
        runtime = self._runtime_progress.get(task_id)
        try:
            dag = self.repository.get_dag(task_id)
        except Exception:
            payload.setdefault("dagNodes", [])
            payload.setdefault("dagSummary", {
                               "total": 0, "pending": 0, "running": 0, "completed": 0, "failed": 0})
            return

        now_mono = asyncio.get_running_loop().time()
        dag_nodes: list[dict[str, Any]] = []
        summary = {"total": 0, "pending": 0,
                   "running": 0, "completed": 0, "failed": 0}

        for node in dag.nodes:
            if node.taskId == task_id:
                continue
            summary["total"] += 1
            status_value = node.status.value
            status_key = status_value.lower()
            if status_key in summary:
                summary[status_key] += 1

            node_runtime = self._node_runtime.get(task_id, {}).get(node.taskId)
            elapsed_ms = 0
            retry_count = 0
            if node_runtime is not None:
                retry_count = max(0, node_runtime.attempts - 1)
                if node_runtime.first_started_mono is not None:
                    end_mono = node_runtime.completed_mono
                    if end_mono is None and status_value == "RUNNING":
                        end_mono = now_mono
                    if end_mono is None and runtime is not None:
                        end_mono = now_mono
                    if end_mono is not None:
                        elapsed_ms = max(
                            0, int((end_mono - node_runtime.first_started_mono) * 1000))

            dag_nodes.append(
                {
                    "nodeId": node.taskId,
                    "title": node.title,
                    "status": status_value,
                    "searchDepth": node.metadata.searchDepth,
                    "dependencies": node.dependencies,
                    "elapsedMs": elapsed_ms,
                    "retryCount": retry_count,
                }
            )

        payload.setdefault("dagNodes", dag_nodes)
        payload.setdefault("dagSummary", summary)

    def set_event_listener(self, listener: Callable[[str, str, dict], Awaitable[None]] | None) -> None:
        self.event_listener = listener

    async def _emit_event(self, task_id: str, event: str, payload: dict) -> None:
        if event in {"TASK_PROGRESS", "TASK_HEARTBEAT", "STALL_WARNING"}:
            self._attach_dag_snapshot(task_id, payload)
        if event == "TASK_PROGRESS":
            runtime = self._runtime_progress.get(task_id)
            if runtime is not None:
                now_mono = asyncio.get_running_loop().time()
                raw_progress = payload.get("progress")
                if isinstance(raw_progress, (int, float)):
                    runtime.progress = max(0, min(100, int(raw_progress)))
                raw_state = payload.get("state")
                if isinstance(raw_state, str) and raw_state.strip():
                    runtime.state = raw_state.strip()
                raw_phase = payload.get("phase")
                if isinstance(raw_phase, str) and raw_phase.strip():
                    runtime.phase = raw_phase.strip()
                detail = payload.get("detail")
                if isinstance(detail, str) and detail.strip():
                    runtime.detail = detail.strip()
                else:
                    node_title = payload.get("currentNodeTitle")
                    section_title = payload.get("currentSectionTitle")
                    if isinstance(section_title, str) and section_title.strip():
                        runtime.detail = f"正在写作：{section_title.strip()}"
                    elif isinstance(node_title, str) and node_title.strip():
                        runtime.detail = f"正在处理：{node_title.strip()}"
                runtime.last_progress_mono = now_mono
                runtime.stall_notified = False
                payload.setdefault("elapsedMs", int(
                    (now_mono - runtime.started_mono) * 1000))
                payload.setdefault("idleMs", 0)
                payload.setdefault("heartbeat", False)

        await self.hub.emit(task_id, event, payload)
        if self.event_listener is not None:
            try:
                await self.event_listener(task_id, event, payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Event listener failed for task=%s event=%s: %s", task_id, event, exc)

        await self._emit_agent_status_from_task_event(task_id, event, payload)

    async def _heartbeat_loop(self, task_id: str) -> None:
        while True:
            await asyncio.sleep(self.HEARTBEAT_INTERVAL_SECONDS)
            runtime = self._runtime_progress.get(task_id)
            if runtime is None:
                return
            now_mono = asyncio.get_running_loop().time()
            idle_seconds = now_mono - runtime.last_progress_mono
            elapsed_ms = int((now_mono - runtime.started_mono) * 1000)
            idle_ms = int(idle_seconds * 1000)

            await self._emit_event(
                task_id,
                "TASK_HEARTBEAT",
                {
                    "taskId": task_id,
                    "progress": runtime.progress,
                    "state": runtime.state,
                    "phase": "HEARTBEAT",
                    "detail": runtime.detail or "任务执行中，正在等待阶段更新。",
                    "currentPhase": runtime.phase,
                    "elapsedMs": elapsed_ms,
                    "idleMs": idle_ms,
                    "heartbeat": True,
                },
            )

            if idle_seconds >= self.STALL_WARNING_SECONDS and not runtime.stall_notified:
                runtime.stall_notified = True
                await self._emit_event(
                    task_id,
                    "STALL_WARNING",
                    {
                        "taskId": task_id,
                        "progress": runtime.progress,
                        "state": runtime.state,
                        "phase": "STALL_WARNING",
                        "detail": (
                            f"当前阶段持续 {int(idle_seconds)} 秒未出现新进展，"
                            "系统仍在运行，建议继续等待或稍后重试。"
                        ),
                        "currentPhase": runtime.phase,
                        "elapsedMs": elapsed_ms,
                        "idleMs": idle_ms,
                        "stall": True,
                    },
                )

    async def start(self, task_id: str) -> None:
        task = self.repository.get_task(task_id)
        control = self._control.setdefault(task_id, TaskControlState())
        control.paused = False
        control.aborted = False
        if control.running_task and not control.running_task.done():
            return
        loop = asyncio.get_running_loop()
        control.running_task = loop.create_task(
            self._run_task(task_id, task.status))

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
        now_mono = asyncio.get_running_loop().time()
        self._runtime_progress[task_id] = RuntimeProgressState(
            started_mono=now_mono,
            last_progress_mono=now_mono,
            state=current_status.value,
            phase="INITIALIZING",
            progress=0,
            detail="正在初始化任务执行上下文。",
        )
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(task_id))
        try:
            await self._emit_event(task_id, "TASK_STARTED", {"taskId": task_id, "status": current_status.value})
            task = self.repository.get_task(task_id)
            config = task.config
            if not task.dag or not task.dag.nodes:
                self.repository.update_status(
                    task_id, transition_or_raise(task.status, TaskStatus.PLANNING))
                dag = self.planner.build_dag(
                    task_id, task.title, task.description, config)
                self.repository.save_dag(task_id, dag)
                await self._emit_event(
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
                self.repository.update_status(task_id, transition_or_raise(
                    current.status, TaskStatus.EXECUTING))

            dag = self.repository.get_dag(task_id)
            executable_nodes = [n for n in dag.nodes if n.taskId !=
                                task_id and n.status != NodeStatus.PRUNED]
            self._ensure_dag_node_runtime(task_id)
            snapshot = self.repository.load_snapshot(task_id)
            if snapshot:
                control = self._control.setdefault(task_id, TaskControlState())
                control.completed_nodes = snapshot.get(
                    "completed_nodes", control.completed_nodes)
            total = max(1, len(executable_nodes))
            for idx, node in enumerate(executable_nodes, start=1):
                control = self._control.setdefault(task_id, TaskControlState())
                if node.taskId in control.completed_nodes:
                    continue
                while control.paused and not control.aborted:
                    await asyncio.sleep(0.2)
                if control.aborted:
                    await self._emit_event(task_id, "ERROR", {"taskId": task_id, "error": "Task aborted by user"})
                    return
                now_mono = asyncio.get_running_loop().time()
                self._record_node_start(task_id, node.taskId, now_mono)
                self.repository.update_node_status(
                    task_id, node.taskId, NodeStatus.RUNNING, node.metadata.infoGainScore)
                await asyncio.sleep(0.2)
                query = f"{task.title} {node.title}"
                searching_progress = 20 + int(((idx - 1) / total) * 60)
                await self._emit_event(
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
                    await self._emit_event(
                        task_id,
                        "EVIDENCE_FOUND",
                        {"taskId": task_id, "nodeId": node.taskId,
                            "evidence": ev.model_dump()},
                    )
                self.repository.update_node_status(
                    task_id, node.taskId, NodeStatus.COMPLETED, node.metadata.infoGainScore)
                self._record_node_completed(
                    task_id, node.taskId, asyncio.get_running_loop().time())
                control.completed_nodes.append(node.taskId)
                progress = 20 + int((idx / total) * 60)
                await self._emit_event(
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

            evidences = self.evidence_repository.list(
                task_id=task_id, limit=1000).items
            for ev in evidences:
                ev.score = self.analyst_service.score(ev)
            conflicts = self.analyst_service.detect_conflicts(
                task_id=task_id, evidences=evidences, threshold=0.15)
            if conflicts:
                self.repository.update_status(task_id, transition_or_raise(
                    TaskStatus.EXECUTING, TaskStatus.REVIEWING))
                self.conflict_repository.save_many(conflicts)
                await self._emit_event(
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
                self.repository.update_status(task_id, transition_or_raise(
                    TaskStatus.REVIEWING, TaskStatus.SYNTHESIZING))
            else:
                self.repository.update_status(task_id, transition_or_raise(
                    TaskStatus.EXECUTING, TaskStatus.SYNTHESIZING))
            await self._emit_event(
                task_id,
                "TASK_PROGRESS",
                {"taskId": task_id, "progress": 90,
                    "state": "SYNTHESIZING", "phase": "OUTLINING"},
            )
            await asyncio.sleep(0.1)
            dag = self.repository.get_dag(task_id)
            research_sections = [
                (node.taskId, f"{node.title}\n\n{node.description}")
                for node in dag.nodes
                if node.taskId != task_id and node.status != NodeStatus.PRUNED
            ]
            writing_plan = self.planner.build_writing_plan(
                title=task.title,
                description=task.description,
                research_sections=research_sections,
            )
            sections = self.planner.build_report_sections(
                title=task.title,
                description=task.description,
                research_sections=research_sections,
            )
            total_sections = max(1, len(sections))
            for section_idx, (_, section_text) in enumerate(sections, start=1):
                section_title = section_text.splitlines(
                )[0].strip() if section_text else ""
                writing_preview = self._build_writing_preview(section_text)
                write_progress = 90 + int((section_idx / total_sections) * 6)
                await self._emit_event(
                    task_id,
                    "TASK_PROGRESS",
                    {
                        "taskId": task_id,
                        "progress": write_progress,
                        "state": "SYNTHESIZING",
                        "phase": "WRITING_SECTION",
                        "currentSectionTitle": section_title or f"Section {section_idx}",
                        "currentWritingContent": writing_preview,
                    },
                )

            # 准备写作材料
            await self._emit_event(
                task_id,
                "TASK_PROGRESS",
                {
                    "taskId": task_id,
                    "progress": 91,
                    "state": "SYNTHESIZING",
                    "phase": "PREPARING_MATERIALS",
                    "detail": "正在准备写作材料...",
                },
            )

            # 调用 LLM 生成报告 - 这是阻塞点
            await self._emit_event(
                task_id,
                "TASK_PROGRESS",
                {
                    "taskId": task_id,
                    "progress": 94,
                    "state": "SYNTHESIZING",
                    "phase": "CALLING_LLM",
                    "detail": "正在调用 AI 生成内容，这可能需要 1-2 分钟，请耐心等待...",
                },
            )
            logger.info(f"Task {task_id}: 开始调用 LLM 生成报告")
            suppressed_segments: list[str] = []

            try:
                md_path, bib_path, _ = await asyncio.to_thread(
                    self.report_agent.generate_report,
                    task_id=task_id,
                    task_title=task.title,
                    task_description=task.description,
                    sections=sections,
                    evidences=evidences,
                    locked_sections=set(),
                    writing_plan=writing_plan,
                    suppressed_content_callback=suppressed_segments.append,
                )
            except Exception as first_exc:  # noqa: BLE001
                logger.warning(
                    f"Task {task_id}: 首次报告生成失败，准备自动重写恢复: {first_exc}")
                await self._emit_event(
                    task_id,
                    "TASK_PROGRESS",
                    {
                        "taskId": task_id,
                        "progress": 94,
                        "state": "SYNTHESIZING",
                        "phase": "AUTO_REWRITE_RECOVERY",
                        "detail": "首次成文失败，正在自动重写关键章节并重试...",
                    },
                )
                recovered_description = (
                    f"{task.description}\n\n"
                    "系统检测到首次成文失败。请保留已有结构，优先修复失败章节，确保最终输出至少包含三个二级章节、"
                    "每章有自然段落，并维持证据引用可追溯。"
                )
                writing_plan = self.planner.build_writing_plan(
                    title=task.title,
                    description=recovered_description,
                    research_sections=research_sections,
                )
                md_path, bib_path, _ = await asyncio.to_thread(
                    self.report_agent.generate_report,
                    task_id=task_id,
                    task_title=task.title,
                    task_description=recovered_description,
                    sections=sections,
                    evidences=evidences,
                    locked_sections=set(),
                    writing_plan=writing_plan,
                    suppressed_content_callback=suppressed_segments.append,
                )

            await self._emit_suppressed_writer_note(
                task_id=task_id,
                topic=task.title,
                suppressed_segments=suppressed_segments,
            )

            logger.info(f"Task {task_id}: LLM 报告生成完成")

            # 审核阶段
            if self.checking_agent:
                await self._emit_event(
                    task_id,
                    "TASK_PROGRESS",
                    {
                        "taskId": task_id,
                        "progress": 95,
                        "state": "SYNTHESIZING",
                        "phase": "REVIEWING",
                        "detail": "正在审核文章质量...",
                    },
                )
                logger.info(f"Task {task_id}: 开始审核报告")

                from app.services.four_agents.base import AgentContext
                from pathlib import Path

                # 读取生成的文章
                article_content = Path(md_path).read_text(encoding="utf-8")

                context = AgentContext(
                    task_id=task_id,
                    conversation_id=task_id,
                    topic=task.title,
                    config={"article_content": article_content,
                            "article_path": md_path}
                )

                check_result = await self.checking_agent.run(context)

                if check_result.success:
                    logger.info(f"Task {task_id}: 审核通过")
                    await self._emit_event(
                        task_id,
                        "TASK_PROGRESS",
                        {
                            "taskId": task_id,
                            "progress": 96,
                            "state": "SYNTHESIZING",
                            "phase": "REVIEW_PASSED",
                            "detail": "审核通过，文章质量符合要求",
                        },
                    )
                else:
                    logger.warning(
                        f"Task {task_id}: 审核发现问题: {check_result.output.get('summary', {})}")
                    await self._emit_event(
                        task_id,
                        "TASK_PROGRESS",
                        {
                            "taskId": task_id,
                            "progress": 96,
                            "state": "SYNTHESIZING",
                            "phase": "REVIEW_ISSUES",
                            "detail": f"审核发现问题: {check_result.output.get('summary', {}).get('total_issues', 0)} 处",
                            "issues": check_result.output.get('issues', []),
                        },
                    )

            # 保存报告
            await self._emit_event(
                task_id,
                "TASK_PROGRESS",
                {
                    "taskId": task_id,
                    "progress": 97,
                    "state": "SYNTHESIZING",
                    "phase": "SAVING_REPORT",
                    "detail": "正在保存报告...",
                },
            )
            self.repository.update_status(task_id, transition_or_raise(
                TaskStatus.SYNTHESIZING, TaskStatus.FINALIZING))
            await self._emit_event(
                task_id,
                "TASK_PROGRESS",
                {"taskId": task_id, "progress": 98,
                    "state": "FINALIZING", "phase": "PERSISTING_REPORT"},
            )
            self.repository.set_report_path(task_id, md_path)
            self.repository.update_status(task_id, transition_or_raise(
                TaskStatus.FINALIZING, TaskStatus.COMPLETED))
            await self._emit_event(
                task_id,
                "TASK_COMPLETED",
                {"taskId": task_id, "progress": 100,
                    "reportPath": md_path, "bibPath": bib_path},
            )
        except InvalidStateTransition as exc:
            self.repository.update_status(
                task_id, TaskStatus.FAILED, last_error=str(exc))
            await self._emit_event(task_id, "ERROR", {"taskId": task_id, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self.repository.update_status(
                task_id, TaskStatus.FAILED, last_error=str(exc))
            error_detail = str(exc)
            if "'sqlite3.Row' object has no attribute 'get'" in error_detail:
                error_detail = "数据库查询格式错误，请联系开发者修复"
            await self._emit_event(task_id, "ERROR", {"taskId": task_id, "error": error_detail})
        finally:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task
            self._runtime_progress.pop(task_id, None)
            self._node_runtime.pop(task_id, None)
            self._last_agent_state.pop(task_id, None)

    async def _emit_suppressed_writer_note(self, *, task_id: str, topic: str, suppressed_segments: list[str]) -> None:
        unique_segments = _dedupe_nonempty_strings(suppressed_segments)
        if not unique_segments:
            return
        content = await longcat_client.summarize_suppressed_writer_note(
            topic=topic,
            segments=unique_segments,
        )
        if not content:
            return
        await self._emit_event(
            task_id,
            "TASK_NOTE",
            {
                "taskId": task_id,
                "content": content,
                "segments": unique_segments[:3],
                "source": "writer-suppressed-meta",
            },
        )


def _dedupe_nonempty_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        candidate = value.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered
