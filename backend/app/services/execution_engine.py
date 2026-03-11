from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Awaitable, Callable

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
from app.services.four_agents.checking_agent import CheckingAgent

logger = logging.getLogger(__name__)


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

    def set_event_listener(self, listener: Callable[[str, str, dict], Awaitable[None]] | None) -> None:
        self.event_listener = listener

    async def _emit_event(self, task_id: str, event: str, payload: dict) -> None:
        await self.hub.emit(task_id, event, payload)
        if self.event_listener is not None:
            try:
                await self.event_listener(task_id, event, payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Event listener failed for task=%s event=%s: %s", task_id, event, exc)

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
            await self._emit_event(task_id, "ERROR", {"taskId": task_id, "error": f"Unhandled error: {exc}"})

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
