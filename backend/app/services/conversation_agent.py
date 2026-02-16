from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable

import httpx

from app.core.config import settings
from app.core.utils import new_id
from app.models.schemas import (
    ConversationDetail,
    ConversationMessage,
    ConversationStatus,
    MessageKind,
    MessageRole,
    NodeStatus,
    PlanRevision,
    RunConversationResponse,
    TaskConfig,
    TaskStatus,
)
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.task_repository import TaskRepository
from app.services.agents import ReportAgent
from app.services.execution_engine import ExecutionEngine


@dataclass(frozen=True)
class ParsedPlan:
    title: str
    config: TaskConfig
    warnings: list[str]


class ConversationAgent:
    _FRONT_MATTER_PATTERN = re.compile(r"\A---\s*\n(?P<header>.*?)\n---\s*\n?", re.DOTALL)
    _KV_PATTERN = re.compile(r"^\s*([a-zA-Z_]+)\s*:\s*(.*?)\s*$")
    _PLAN_INTENT_MARKERS = (
        "研究方案",
        "研究计划",
        "front matter",
        "max_depth",
        "max_nodes",
        "priority",
        "search_sources",
        "任务树",
        "执行步骤",
        "改方案",
    )
    _RESEARCH_INTENT_MARKERS = (
        "重新研究",
        "重新执行",
        "再执行",
        "再跑",
        "重跑",
        "补充检索",
        "补充资料",
        "补充证据",
        "再检索",
        "再搜索",
        "补充文献",
        "查询最新",
        "更新最新",
        "追加调研",
    )
    _REPORT_REBUILD_MARKERS = (
        "从证据重写",
        "依据证据重写",
        "基于证据重写",
        "重新生成报告",
        "全量重写",
    )
    _REPORT_INTENT_MARKERS = (
        "改写报告",
        "修改报告",
        "重写报告",
        "润色",
        "演讲稿",
        "口播",
        "摘要版",
        "精简版",
        "扩写",
        "改语气",
        "改风格",
        "rewrite",
        "speech",
        "tone",
        "style",
    )

    def __init__(
        self,
        *,
        repository: ConversationRepository,
        task_repository: TaskRepository,
        execution_engine: ExecutionEngine,
        evidence_repository: EvidenceRepository | None = None,
        report_agent: ReportAgent | None = None,
    ) -> None:
        self.repository = repository
        self.task_repository = task_repository
        self.execution_engine = execution_engine
        self.evidence_repository = evidence_repository
        self.report_agent = report_agent

    async def create_conversation(self, *, topic: str, config: TaskConfig | None = None) -> ConversationDetail:
        selected_config = config or TaskConfig()
        conversation_id = new_id()
        self.repository.create_conversation(
            conversation_id=conversation_id,
            topic=topic,
            status=ConversationStatus.DRAFTING_PLAN,
            config=selected_config,
        )
        self.repository.add_message(
            conversation_id,
            message_id=new_id(),
            role=MessageRole.USER,
            kind=MessageKind.USER_TEXT,
            content=topic,
            metadata={"stage": "CREATED"},
        )
        markdown = await asyncio.to_thread(self._generate_initial_plan, topic=topic, config=selected_config)
        revision = self.repository.add_plan_revision(
            conversation_id,
            author=MessageRole.ASSISTANT,
            markdown=markdown,
        )
        self.repository.add_message(
            conversation_id,
            message_id=new_id(),
            role=MessageRole.ASSISTANT,
            kind=MessageKind.PLAN_DRAFT,
            content=revision.markdown,
            metadata={"version": revision.version},
        )
        self.repository.set_status(conversation_id, ConversationStatus.PLAN_READY)
        return self.repository.get_detail(conversation_id)

    async def revise_plan(self, *, conversation_id: str, instruction: str) -> tuple[PlanRevision, ConversationMessage]:
        summary = self.repository.get_summary(conversation_id)
        if summary.status == ConversationStatus.RUNNING:
            raise ValueError("当前会话正在处理中，请等待完成后再发送新需求。")
        current_plan = self.repository.get_current_plan(conversation_id)
        if current_plan is None:
            raise ValueError("当前会话没有可修订方案。")

        has_report = self._has_persisted_report(summary.taskId)
        mode = self._infer_instruction_mode(has_report=has_report, instruction=instruction)
        if mode == "RESEARCH":
            revision, _ = await self._apply_plan_revision(
                conversation_id=conversation_id,
                topic=summary.topic,
                current_plan=current_plan.markdown,
                instruction=instruction,
            )
            await self.start_research(conversation_id=conversation_id)
            return revision, self._latest_message(conversation_id)

        if mode == "REPORT":
            message = await self._start_report_revision(
                conversation_id=conversation_id,
                task_id=summary.taskId or "",
                instruction=instruction,
            )
            return current_plan, message

        return await self._apply_plan_revision(
            conversation_id=conversation_id,
            topic=summary.topic,
            current_plan=current_plan.markdown,
            instruction=instruction,
        )

    def _infer_instruction_mode(self, *, has_report: bool, instruction: str) -> str:
        if not has_report:
            return "PLAN"
        if self._matches_any_marker(instruction, self._RESEARCH_INTENT_MARKERS):
            return "RESEARCH"
        if self._matches_any_marker(instruction, self._PLAN_INTENT_MARKERS):
            return "PLAN"
        if self._matches_any_marker(instruction, self._REPORT_INTENT_MARKERS):
            return "REPORT"
        return "REPORT"

    async def _start_report_revision(
        self,
        *,
        conversation_id: str,
        task_id: str,
        instruction: str,
    ) -> ConversationMessage:
        self.repository.add_message(
            conversation_id,
            message_id=new_id(),
            role=MessageRole.USER,
            kind=MessageKind.USER_TEXT,
            content=instruction,
        )
        self.repository.set_status(conversation_id, ConversationStatus.RUNNING)
        ack_message = self.repository.add_message(
            conversation_id,
            message_id=new_id(),
            role=MessageRole.SYSTEM,
            kind=MessageKind.USER_TEXT,
            content="正在修改中，Agent 会基于当前报告完成改写并自动更新结果。",
            metadata={"taskId": task_id, "stage": "REPORT_REVISING"},
        )
        asyncio.create_task(
            self._run_report_revision_job(
                conversation_id=conversation_id,
                task_id=task_id,
                instruction=instruction,
            )
        )
        return ack_message

    async def _run_report_revision_job(self, *, conversation_id: str, task_id: str, instruction: str) -> None:
        def progress_callback(
            progress: int,
            phase: str,
            state: str,
            summary: str,
            payload: dict | None = None,
        ) -> None:
            self._emit_report_revision_progress(
                conversation_id=conversation_id,
                task_id=task_id,
                progress=progress,
                phase=phase,
                state=state,
                summary=summary,
                payload=payload,
            )

        progress_callback(
            5,
            "ANALYZING_REQUIREMENT",
            "REPORT_REVISING",
            "已接收改稿任务，正在分析修改意图。",
            {"taskId": task_id, "instruction": instruction[:120]},
        )
        try:
            await asyncio.to_thread(
                self._revise_report_and_record,
                conversation_id=conversation_id,
                task_id=task_id,
                instruction=instruction,
                progress_callback=progress_callback,
            )
            progress_callback(
                100,
                "REPORT_COMPLETED",
                "COMPLETED",
                "报告改写完成，已更新到会话中。",
                {"taskId": task_id},
            )
            self.repository.set_status(conversation_id, ConversationStatus.COMPLETED)
        except KeyError:
            return
        except Exception as exc:  # noqa: BLE001
            try:
                progress_callback(
                    100,
                    "REPORT_FAILED",
                    "FAILED",
                    f"报告改写失败：{exc}",
                    {"taskId": task_id, "error": str(exc)},
                )
                self.repository.set_status(conversation_id, ConversationStatus.FAILED)
                self.repository.add_message(
                    conversation_id,
                    message_id=new_id(),
                    role=MessageRole.SYSTEM,
                    kind=MessageKind.ERROR,
                    content=f"报告改写失败：{exc}",
                    metadata={"taskId": task_id, "stage": "REPORT_REVISION"},
                )
            except KeyError:
                return

    def _emit_report_revision_progress(
        self,
        *,
        conversation_id: str,
        task_id: str,
        progress: int,
        phase: str,
        state: str,
        summary: str,
        payload: dict | None = None,
    ) -> None:
        normalized_task_id = task_id.strip() if task_id.strip() else f"report-revision:{conversation_id}"
        progress_value = max(0, min(100, int(progress)))
        event_payload = {"taskId": normalized_task_id, "phase": phase, "state": state, "progress": progress_value}
        if payload:
            event_payload.update(payload)
        event_payload["taskId"] = normalized_task_id
        try:
            self.repository.append_progress_entry(
                conversation_id,
                task_id=normalized_task_id,
                message_id=new_id(),
                phase=phase,
                state=state,
                summary=summary,
                progress=progress_value,
                payload=event_payload,
            )
        except KeyError:
            return

    async def _apply_plan_revision(
        self,
        *,
        conversation_id: str,
        topic: str,
        current_plan: str,
        instruction: str,
    ) -> tuple[PlanRevision, ConversationMessage]:
        self.repository.add_message(
            conversation_id,
            message_id=new_id(),
            role=MessageRole.USER,
            kind=MessageKind.USER_TEXT,
            content=instruction,
        )
        config = self.repository.get_config(conversation_id)
        revised = await asyncio.to_thread(
            self._generate_revised_plan,
            topic=topic,
            config=config,
            current_plan=current_plan,
            instruction=instruction,
        )
        revision = self.repository.add_plan_revision(
            conversation_id,
            author=MessageRole.ASSISTANT,
            markdown=revised,
        )
        message = self.repository.add_message(
            conversation_id,
            message_id=new_id(),
            role=MessageRole.ASSISTANT,
            kind=MessageKind.PLAN_REVISION,
            content=revision.markdown,
            metadata={"version": revision.version},
        )
        self.repository.set_status(conversation_id, ConversationStatus.PLAN_READY)
        return revision, message

    def update_plan(self, *, conversation_id: str, markdown: str) -> PlanRevision:
        summary = self.repository.get_summary(conversation_id)
        if summary.status == ConversationStatus.RUNNING:
            raise ValueError("研究执行中，暂不支持直接编辑方案。")
        revision = self.repository.add_plan_revision(
            conversation_id,
            author=MessageRole.USER,
            markdown=markdown,
        )
        self.repository.add_message(
            conversation_id,
            message_id=new_id(),
            role=MessageRole.USER,
            kind=MessageKind.PLAN_EDITED,
            content=revision.markdown,
            metadata={"version": revision.version},
        )
        self.repository.set_status(conversation_id, ConversationStatus.PLAN_READY)
        return revision

    def rename_conversation(
        self,
        *,
        conversation_id: str,
        topic: str,
        sync_current_plan: bool = True,
    ) -> ConversationDetail:
        topic_text = topic.strip()
        if len(topic_text) < 2:
            raise ValueError("会话标题至少需要 2 个字符。")
        summary = self.repository.update_topic(conversation_id, topic_text)

        current_plan = self.repository.get_current_plan(conversation_id) if sync_current_plan else None
        if current_plan is not None:
            base_config = self.repository.get_config(conversation_id)
            rewritten = self._rewrite_plan_topic(
                current_plan.markdown,
                topic=topic_text,
                config=base_config,
            )
            if rewritten.strip() != current_plan.markdown.strip():
                revision = self.repository.add_plan_revision(
                    conversation_id,
                    author=MessageRole.SYSTEM,
                    markdown=rewritten,
                )
                self.repository.add_message(
                    conversation_id,
                    message_id=new_id(),
                    role=MessageRole.SYSTEM,
                    kind=MessageKind.USER_TEXT,
                    content=f"会话已重命名为：{topic_text}（方案已同步到 v{revision.version}）",
                    metadata={
                        "stage": "RENAMED",
                        "planVersion": revision.version,
                        "topic": topic_text,
                    },
                )
            else:
                self.repository.add_message(
                    conversation_id,
                    message_id=new_id(),
                    role=MessageRole.SYSTEM,
                    kind=MessageKind.USER_TEXT,
                    content=f"会话已重命名为：{topic_text}",
                    metadata={"stage": "RENAMED", "topic": topic_text},
                )
        else:
            self.repository.add_message(
                conversation_id,
                message_id=new_id(),
                role=MessageRole.SYSTEM,
                kind=MessageKind.USER_TEXT,
                content=f"会话已重命名为：{topic_text}",
                metadata={"stage": "RENAMED", "topic": topic_text},
            )

        if summary.status == ConversationStatus.DRAFTING_PLAN:
            self.repository.set_status(conversation_id, ConversationStatus.PLAN_READY)
        return self.repository.get_detail(conversation_id)

    def delete_conversation(self, *, conversation_id: str) -> None:
        summary = self.repository.get_summary(conversation_id)
        self._abort_task_if_active(summary.taskId)
        self.repository.delete_conversation(conversation_id)

    def delete_all_conversations(self) -> int:
        for summary in self.repository.list_summaries():
            self._abort_task_if_active(summary.taskId)
        return self.repository.delete_all_conversations()

    async def start_research(self, *, conversation_id: str) -> RunConversationResponse:
        summary = self.repository.get_summary(conversation_id)
        if summary.status == ConversationStatus.RUNNING:
            if summary.taskId:
                return RunConversationResponse(
                    conversationId=conversation_id,
                    taskId=summary.taskId,
                    status=ConversationStatus.RUNNING,
                )
            raise ValueError("会话状态异常：RUNNING 但 taskId 缺失。")

        current_plan = self.repository.get_current_plan(conversation_id)
        if current_plan is None:
            raise ValueError("没有可执行方案，请先生成或编辑研究方案。")
        base_config = self.repository.get_config(conversation_id)
        parsed = self._parse_plan(current_plan.markdown, topic=summary.topic, base_config=base_config)
        for warning in parsed.warnings:
            self.repository.add_message(
                conversation_id,
                message_id=new_id(),
                role=MessageRole.SYSTEM,
                kind=MessageKind.ERROR,
                content=warning,
            )
        task_description = self._extract_plan_body(current_plan.markdown)[:5000]
        if len(task_description.strip()) < 3:
            task_description = f"围绕主题“{summary.topic}”执行系统化研究。"
        task = self.task_repository.create_task(
            task_id=new_id(),
            title=parsed.title[:200],
            description=task_description,
            config=parsed.config,
        )
        self.repository.set_task_id(conversation_id, task.taskId)
        self.repository.set_status(conversation_id, ConversationStatus.RUNNING)
        self.repository.add_message(
            conversation_id,
            message_id=new_id(),
            role=MessageRole.SYSTEM,
            kind=MessageKind.USER_TEXT,
            content="研究任务已启动，Agent 正在按方案执行。",
            metadata={"taskId": task.taskId},
        )
        await self.execution_engine.start(task.taskId)
        return RunConversationResponse(
            conversationId=conversation_id,
            taskId=task.taskId,
            status=ConversationStatus.RUNNING,
        )

    async def on_task_event(self, task_id: str, event: str, data: dict) -> None:
        summary = self.repository.find_by_task_id(task_id)
        if summary is None:
            return
        conversation_id = summary.conversationId

        if event == "TASK_PROGRESS":
            phase = str(data.get("phase") or data.get("state") or "UNKNOWN").strip() or "UNKNOWN"
            state = str(data.get("state") or "UNKNOWN").strip() or "UNKNOWN"
            progress = data.get("progress")
            if isinstance(progress, float):
                progress = int(progress)
            if not isinstance(progress, int):
                progress = None
            summary_line = self._progress_summary(data)
            self.repository.append_progress_entry(
                conversation_id,
                task_id=task_id,
                message_id=new_id(),
                phase=phase,
                state=state,
                summary=summary_line,
                progress=progress,
                payload=data,
            )
            return

        if event == "TASK_COMPLETED":
            self.repository.set_status(conversation_id, ConversationStatus.COMPLETED)
            report_content = self._load_report(task_id)
            self.repository.add_message(
                conversation_id,
                message_id=new_id(),
                role=MessageRole.ASSISTANT,
                kind=MessageKind.FINAL_REPORT,
                content=report_content or "研究已完成，但报告正文暂不可用。",
                metadata={"taskId": task_id},
            )
            return

        if event in {"TASK_FAILED", "TASK_ABORTED", "ERROR"}:
            self.repository.set_status(conversation_id, ConversationStatus.FAILED)
            error_text = str(data.get("error") or "研究执行失败，请检查日志。").strip()
            self.repository.add_message(
                conversation_id,
                message_id=new_id(),
                role=MessageRole.SYSTEM,
                kind=MessageKind.ERROR,
                content=error_text,
                metadata={"taskId": task_id, "event": event},
            )

    def _load_report(self, task_id: str) -> str:
        try:
            task = self.task_repository.get_task(task_id)
        except KeyError:
            return ""
        if not task.reportPath:
            return ""
        path = Path(task.reportPath)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _revise_report_and_record(
        self,
        *,
        conversation_id: str,
        task_id: str,
        instruction: str,
        progress_callback: Callable[[int, str, str, str, dict | None], None] | None = None,
    ) -> ConversationMessage:
        def emit(progress: int, phase: str, summary: str, payload: dict | None = None) -> None:
            if progress_callback is None:
                return
            progress_callback(progress, phase, "REPORT_REVISING", summary, payload)

        current_report = self._load_report(task_id)
        if not current_report:
            latest_report = self._latest_report_message(conversation_id)
            current_report = latest_report.content if latest_report else ""
        emit(
            20,
            "PREPARING_DRAFT",
            "已读取现有报告，正在整理可保留内容。",
            {"taskId": task_id, "currentReportLength": len(current_report)},
        )

        report_text = ""
        if current_report.strip():
            emit(
                45,
                "WRITING_DRAFT",
                "正在按你的要求改写报告结构与语气。",
                {"taskId": task_id},
            )
            llm_revised = self._rewrite_report_with_llm(current_report=current_report, instruction=instruction)
            report_text = llm_revised or self._fallback_revised_report(
                current_report=current_report,
                instruction=instruction,
            )
            emit(
                72,
                "WRITING_DRAFT",
                "主体改写完成，正在保存新版本。",
                {"taskId": task_id},
            )
            self._persist_report(task_id=task_id, content=report_text)

        should_rebuild = self._matches_any_marker(instruction, self._REPORT_REBUILD_MARKERS)
        if should_rebuild or not report_text:
            emit(
                78,
                "EVIDENCE_REBUILD",
                "正在基于已有证据重建报告内容。",
                {"taskId": task_id},
            )
            report_text = self._regenerate_report_from_existing_artifacts(task_id=task_id, instruction=instruction)
            if report_text:
                emit(
                    90,
                    "EVIDENCE_REBUILD",
                    "证据重建完成，正在合并输出。",
                    {"taskId": task_id},
                )
        if not report_text:
            report_text = self._fallback_revised_report(current_report=current_report, instruction=instruction)
            self._persist_report(task_id=task_id, content=report_text)
        emit(
            96,
            "PERSISTING_REPORT",
            "正在写入会话并刷新报告预览。",
            {"taskId": task_id},
        )

        return self.repository.add_message(
            conversation_id,
            message_id=new_id(),
            role=MessageRole.ASSISTANT,
            kind=MessageKind.FINAL_REPORT,
            content=report_text,
            metadata={"taskId": task_id, "mode": "REPORT_REVISION"},
        )

    def _regenerate_report_from_existing_artifacts(self, *, task_id: str, instruction: str) -> str:
        if not self.report_agent or not self.evidence_repository:
            return ""
        try:
            task = self.task_repository.get_task(task_id)
        except KeyError:
            return ""

        try:
            dag = self.task_repository.get_dag(task_id, allow_empty=True)
        except Exception:
            return ""
        sections = [
            (node.taskId, f"{node.title}\n\n{node.description}")
            for node in dag.nodes
            if node.taskId != task_id and node.status != NodeStatus.PRUNED
        ]
        evidences = self.evidence_repository.list(task_id=task_id, limit=1000).items
        revised_description = (
            f"{task.description}\n\n"
            f"用户补充要求：{instruction}\n"
            "请在保持证据可追溯的前提下重写完整报告。"
        )
        try:
            md_path, _, _ = self.report_agent.generate_report(
                task_id=task_id,
                task_title=task.title,
                task_description=revised_description,
                sections=sections,
                evidences=evidences,
                locked_sections=set(),
            )
            self.task_repository.set_report_path(task_id, md_path)
            return Path(md_path).read_text(encoding="utf-8")
        except Exception:
            return ""

    def _rewrite_report_with_llm(self, *, current_report: str, instruction: str) -> str:
        if not current_report.strip():
            return ""
        prompt = (
            "你是报告改写 Agent。请基于用户提供的“当前报告”完成改写。\n"
            "要求：\n"
            "1. 仅输出最终 Markdown，不要解释过程；\n"
            "2. 保留事实准确性，尽量保留证据 ID（例如 [evidence:xxxx]）；\n"
            "3. 如果用户要求体裁变化（如演讲稿），需完整重排结构与语气；\n"
            "4. 未被用户要求删除的信息请尽量保留。"
        )
        user_input = (
            f"用户要求：{instruction}\n\n"
            f"当前报告：\n{current_report[:45000]}"
        )
        return self._chat_complete(system_prompt=prompt, user_prompt=user_input).strip()

    @staticmethod
    def _fallback_revised_report(*, current_report: str, instruction: str) -> str:
        base = current_report.strip() or "# 修订报告"
        return (
            f"{base}\n\n"
            "## 修订说明\n"
            f"- 用户要求：{instruction}\n"
            "- 已触发自动修订流程；若需补充外部资料，请在指令中明确“补充检索/重新研究”。\n"
        )

    def _persist_report(self, *, task_id: str, content: str) -> None:
        try:
            task = self.task_repository.get_task(task_id)
        except KeyError:
            return
        if task.reportPath:
            report_path = Path(task.reportPath)
        else:
            report_path = Path("backend/.data/reports") / f"{task_id}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(content, encoding="utf-8")
        self.task_repository.set_report_path(task_id, str(report_path))

    def _latest_report_message(self, conversation_id: str) -> ConversationMessage | None:
        messages = self.repository.get_detail(conversation_id).messages
        for message in reversed(messages):
            if message.kind == MessageKind.FINAL_REPORT:
                return message
        return None

    def _latest_message(self, conversation_id: str) -> ConversationMessage:
        messages = self.repository.get_detail(conversation_id).messages
        if not messages:
            raise ValueError("会话中没有消息记录。")
        return messages[-1]

    def _has_persisted_report(self, task_id: str | None) -> bool:
        if not task_id:
            return False
        return bool(self._load_report(task_id).strip())

    @staticmethod
    def _matches_any_marker(text: str, markers: tuple[str, ...]) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in markers)

    @staticmethod
    def _extract_plan_body(markdown: str) -> str:
        match = ConversationAgent._FRONT_MATTER_PATTERN.match(markdown.strip())
        if not match:
            return markdown.strip()
        return markdown[match.end() :].strip()

    def _parse_plan(self, markdown: str, *, topic: str, base_config: TaskConfig) -> ParsedPlan:
        warnings: list[str] = []
        config_data = base_config.model_dump()
        parsed_title = topic
        match = self._FRONT_MATTER_PATTERN.match(markdown.strip())
        if not match:
            warnings.append("未检测到方案 front matter，已回退为默认执行配置。")
            return ParsedPlan(title=parsed_title, config=TaskConfig(**config_data), warnings=warnings)

        header = match.group("header")
        for raw_line in header.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            kv = self._KV_PATTERN.match(line)
            if not kv:
                warnings.append(f"忽略无法解析的 front matter 行：{line}")
                continue
            key = kv.group(1).strip().lower()
            value = kv.group(2).strip()
            if key == "title" and value:
                parsed_title = value.strip().strip('"').strip("'")
                continue
            if key == "topic":
                continue
            if key == "max_depth":
                config_data["maxDepth"] = self._int_or_default(value, base_config.maxDepth, min_value=1, max_value=8)
                continue
            if key == "max_nodes":
                config_data["maxNodes"] = self._int_or_default(value, base_config.maxNodes, min_value=1, max_value=500)
                continue
            if key == "priority":
                config_data["priority"] = self._int_or_default(value, base_config.priority, min_value=1, max_value=5)
                continue
            if key == "search_sources":
                parsed_sources = self._parse_sources(value)
                if parsed_sources:
                    config_data["searchSources"] = parsed_sources
                else:
                    warnings.append("search_sources 为空，已回退默认数据源配置。")

        return ParsedPlan(title=parsed_title[:200], config=TaskConfig(**config_data), warnings=warnings)

    @staticmethod
    def _int_or_default(raw: str, default: int, *, min_value: int, max_value: int) -> int:
        try:
            value = int(raw.strip())
        except Exception:
            return default
        return max(min_value, min(max_value, value))

    @staticmethod
    def _parse_sources(raw: str) -> list[str]:
        text = raw.strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        parts = [part.strip().strip('"').strip("'") for part in text.split(",")]
        return [part for part in parts if part]

    def _generate_initial_plan(self, *, topic: str, config: TaskConfig) -> str:
        prompt = (
            "请为用户生成一个可执行的深度研究方案，输出必须是 Markdown，并且必须包含 front matter。\n"
            "front matter 字段固定为：title, topic, max_depth, max_nodes, priority, search_sources。\n"
            "正文至少包含：研究目标、研究问题拆解、方法与来源、执行步骤、风险与边界、交付标准。\n"
            "严禁输出解释性前言，直接返回完整 Markdown。"
        )
        user_input = (
            f"主题：{topic}\n"
            f"配置建议：max_depth={config.maxDepth}, max_nodes={config.maxNodes}, "
            f"priority={config.priority}, search_sources={config.searchSources}\n"
            "输出语言：中文。"
        )
        generated = self._chat_complete(system_prompt=prompt, user_prompt=user_input)
        if generated:
            normalized = self._ensure_front_matter(generated, topic=topic, config=config)
            if normalized:
                return normalized
        return self._fallback_plan(topic=topic, config=config)

    def _generate_revised_plan(
        self,
        *,
        topic: str,
        config: TaskConfig,
        current_plan: str,
        instruction: str,
    ) -> str:
        prompt = (
            "你是研究计划修订 Agent。请根据用户指令修订“当前研究方案”。\n"
            "输出必须是完整 Markdown，且必须包含完整 front matter。\n"
            "不要解释你做了什么，不要输出多余文本，只返回最终方案。"
        )
        user_input = (
            f"主题：{topic}\n"
            f"用户指令：{instruction}\n\n"
            f"当前方案如下：\n{current_plan}\n\n"
            f"保底配置：max_depth={config.maxDepth}, max_nodes={config.maxNodes}, "
            f"priority={config.priority}, search_sources={config.searchSources}"
        )
        generated = self._chat_complete(system_prompt=prompt, user_prompt=user_input)
        if generated:
            normalized = self._ensure_front_matter(generated, topic=topic, config=config)
            if normalized:
                return normalized
        return self._fallback_revision(current_plan=current_plan, instruction=instruction, topic=topic, config=config)

    def _chat_complete(self, *, system_prompt: str, user_prompt: str) -> str:
        if settings.use_mock_sources:
            return ""
        base_url, api_key, model = self._resolve_provider()
        if not base_url or not api_key:
            return ""
        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "temperature": 0.2,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
                response.raise_for_status()
                payload = response.json()
            return (
                payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
        except Exception:
            return ""

    @staticmethod
    def _resolve_provider() -> tuple[str, str, str]:
        provider = settings.default_llm_provider.lower().strip()
        if provider == "openrouter":
            return settings.openrouter_base_url, settings.openrouter_api_key, settings.openrouter_model
        if provider == "deepseek":
            return settings.deepseek_base_url, settings.deepseek_api_key, settings.deepseek_model
        if provider == "openai":
            return settings.openai_base_url, settings.openai_api_key, settings.openai_model
        return "", "", ""

    def _abort_task_if_active(self, task_id: str | None) -> None:
        if not task_id:
            return
        try:
            task = self.task_repository.get_task(task_id)
        except KeyError:
            return
        if task.status in {
            TaskStatus.READY,
            TaskStatus.PLANNING,
            TaskStatus.EXECUTING,
            TaskStatus.REVIEWING,
            TaskStatus.SYNTHESIZING,
            TaskStatus.FINALIZING,
            TaskStatus.SUSPENDED,
        }:
            self.execution_engine.abort(task_id)

    def _rewrite_plan_topic(self, markdown: str, *, topic: str, config: TaskConfig) -> str:
        text = markdown.strip()
        if not text:
            return self._ensure_front_matter(markdown, topic=topic, config=config)

        match = self._FRONT_MATTER_PATTERN.match(text)
        if not match:
            return self._ensure_front_matter(text, topic=topic, config=config)

        header = match.group("header")
        body = text[match.end() :].strip()
        header_lines = header.splitlines()
        rewritten_lines: list[str] = []
        has_title = False
        has_topic = False
        for raw_line in header_lines:
            kv = self._KV_PATTERN.match(raw_line)
            if not kv:
                rewritten_lines.append(raw_line)
                continue
            key = kv.group(1).strip()
            key_l = key.lower()
            if key_l == "title":
                rewritten_lines.append(f"{key}: {self._yaml_value(topic)}")
                has_title = True
                continue
            if key_l == "topic":
                rewritten_lines.append(f"{key}: {self._yaml_value(topic)}")
                has_topic = True
                continue
            rewritten_lines.append(raw_line)

        if not has_title:
            rewritten_lines.append(f"title: {self._yaml_value(topic)}")
        if not has_topic:
            rewritten_lines.append(f"topic: {self._yaml_value(topic)}")

        rebuilt_header = "\n".join(rewritten_lines)
        rebuilt = f"---\n{rebuilt_header}\n---"
        if body:
            return f"{rebuilt}\n\n{body}"
        return rebuilt

    @staticmethod
    def _yaml_value(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _ensure_front_matter(self, markdown: str, *, topic: str, config: TaskConfig) -> str:
        text = markdown.strip()
        if not text:
            return ""
        if self._FRONT_MATTER_PATTERN.match(text):
            return text
        return (
            "---\n"
            f"title: {topic}\n"
            f"topic: {topic}\n"
            f"max_depth: {config.maxDepth}\n"
            f"max_nodes: {config.maxNodes}\n"
            f"priority: {config.priority}\n"
            f"search_sources: [{', '.join(config.searchSources)}]\n"
            "---\n\n"
            f"{text}"
        )

    @staticmethod
    def _fallback_plan(*, topic: str, config: TaskConfig) -> str:
        return (
            "---\n"
            f"title: {topic} 深度研究方案\n"
            f"topic: {topic}\n"
            f"max_depth: {config.maxDepth}\n"
            f"max_nodes: {config.maxNodes}\n"
            f"priority: {config.priority}\n"
            f"search_sources: [{', '.join(config.searchSources)}]\n"
            "---\n\n"
            "## 研究目标\n"
            "围绕主题建立可验证的结论链路，输出可执行决策建议。\n\n"
            "## 研究问题拆解\n"
            "1. 核心概念与边界是什么。\n"
            "2. 当前主流方法与证据来源有哪些。\n"
            "3. 风险、局限与落地障碍分别是什么。\n\n"
            "## 方法与来源\n"
            "- 使用学术论文与高可信 Web 来源交叉验证。\n"
            "- 对关键结论保留可追溯证据 ID。\n\n"
            "## 执行步骤\n"
            "1. 规划任务树并确定检索查询。\n"
            "2. 检索、清洗并打分证据。\n"
            "3. 处理冲突并形成综合分析。\n"
            "4. 生成最终 Markdown 报告。\n\n"
            "## 风险与边界\n"
            "- 时效性偏差：关注近三年数据，必要时补充最新动态。\n"
            "- 来源偏差：至少两类来源交叉验证。\n\n"
            "## 交付标准\n"
            "- 报告含摘要、方法、发现、分析、建议。\n"
            "- 关键结论标注证据引用并给出行动建议。\n"
        )

    def _fallback_revision(self, *, current_plan: str, instruction: str, topic: str, config: TaskConfig) -> str:
        normalized = self._ensure_front_matter(current_plan, topic=topic, config=config)
        return (
            f"{normalized}\n\n"
            "## 修订记录\n"
            f"- 用户新要求：{instruction}\n"
            "- 已按要求在执行步骤与交付标准中应用该约束，请在右侧继续手工微调。"
        )

    @staticmethod
    def _progress_summary(data: dict) -> str:
        state = str(data.get("state") or "EXECUTING")
        phase = str(data.get("phase") or "UNKNOWN")
        progress = data.get("progress")
        progress_text = f"{progress}%" if isinstance(progress, (int, float)) else "--"
        node_title = str(data.get("currentNodeTitle") or "").strip()
        section_title = str(data.get("currentSectionTitle") or "").strip()
        query = str(data.get("searchQuery") or "").strip()
        if section_title:
            return f"[{state}/{phase}] {progress_text} 正在写作：{section_title}"
        if node_title and query:
            return f"[{state}/{phase}] {progress_text} 节点：{node_title} | 查询：{query}"
        if node_title:
            return f"[{state}/{phase}] {progress_text} 节点：{node_title}"
        return f"[{state}/{phase}] {progress_text}"
