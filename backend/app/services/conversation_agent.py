from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import re

import httpx

from app.core.config import settings
from app.core.utils import new_id
from app.models.schemas import (
    ConversationDetail,
    ConversationMessage,
    ConversationStatus,
    MessageKind,
    MessageRole,
    PlanRevision,
    RunConversationResponse,
    TaskConfig,
)
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.task_repository import TaskRepository
from app.services.execution_engine import ExecutionEngine


@dataclass(frozen=True)
class ParsedPlan:
    title: str
    config: TaskConfig
    warnings: list[str]


class ConversationAgent:
    _FRONT_MATTER_PATTERN = re.compile(r"\A---\s*\n(?P<header>.*?)\n---\s*\n?", re.DOTALL)
    _KV_PATTERN = re.compile(r"^\s*([a-zA-Z_]+)\s*:\s*(.*?)\s*$")

    def __init__(
        self,
        *,
        repository: ConversationRepository,
        task_repository: TaskRepository,
        execution_engine: ExecutionEngine,
    ) -> None:
        self.repository = repository
        self.task_repository = task_repository
        self.execution_engine = execution_engine

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
            role=MessageRole.SYSTEM,
            kind=MessageKind.USER_TEXT,
            content=f"新研究会话已创建：{topic}",
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
            raise ValueError("研究执行中，暂不支持修订方案。")
        if summary.status in {ConversationStatus.COMPLETED, ConversationStatus.FAILED}:
            raise ValueError("会话已结束，不能继续修订方案。")
        current_plan = self.repository.get_current_plan(conversation_id)
        if current_plan is None:
            raise ValueError("当前会话没有可修订方案。")
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
            topic=summary.topic,
            config=config,
            current_plan=current_plan.markdown,
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
        if summary.status in {ConversationStatus.COMPLETED, ConversationStatus.FAILED}:
            raise ValueError("会话已结束，不能继续修改方案。")
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
        if summary.status in {ConversationStatus.COMPLETED, ConversationStatus.FAILED}:
            raise ValueError("会话已结束，请创建新会话。")

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
