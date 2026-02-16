from __future__ import annotations

import asyncio
from pathlib import Path
import time

import pytest

from app.core.database import init_db
from app.core.utils import new_id
from app.models.schemas import ConversationStatus, MessageKind, MessageRole, TaskConfig, TaskStatus
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.task_repository import TaskRepository
from app.services.conversation_agent import ConversationAgent


class _DummyEngine:
    def __init__(self) -> None:
        self.aborted_task_ids: list[str] = []

    async def start(self, task_id: str) -> None:
        _ = task_id

    def abort(self, task_id: str) -> None:
        self.aborted_task_ids.append(task_id)


def _build_agent() -> ConversationAgent:
    agent, _ = _build_agent_with_engine()
    return agent


def _build_agent_with_engine() -> tuple[ConversationAgent, _DummyEngine]:
    engine = _DummyEngine()
    return ConversationAgent(
        repository=ConversationRepository(),
        task_repository=TaskRepository(),
        execution_engine=engine,  # type: ignore[arg-type]
    ), engine


def test_parse_front_matter_success() -> None:
    agent = _build_agent()
    markdown = """---
title: 自定义标题
topic: 测试主题
max_depth: 3
max_nodes: 12
priority: 5
search_sources: [arXiv, Semantic Scholar, Tavily]
---

## 研究目标
测试正文
"""
    parsed = agent._parse_plan(  # noqa: SLF001
        markdown,
        topic="默认主题",
        base_config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    assert parsed.title == "自定义标题"
    assert parsed.config.maxDepth == 3
    assert parsed.config.maxNodes == 12
    assert parsed.config.priority == 5
    assert parsed.config.searchSources == ["arXiv", "Semantic Scholar", "Tavily"]
    assert parsed.warnings == []


def test_parse_front_matter_fallback_when_missing() -> None:
    agent = _build_agent()
    base = TaskConfig(maxDepth=2, maxNodes=9, priority=4, searchSources=["arXiv"])
    parsed = agent._parse_plan(  # noqa: SLF001
        "## 没有 front matter",
        topic="默认主题",
        base_config=base,
    )
    assert parsed.title == "默认主题"
    assert parsed.config == base
    assert any("front matter" in warning for warning in parsed.warnings)


def test_rewrite_plan_topic_with_existing_front_matter() -> None:
    agent = _build_agent()
    markdown = """---
title: 原始标题
topic: 原始主题
max_depth: 2
max_nodes: 8
priority: 3
search_sources: [arXiv]
---

## 执行步骤
保持正文不变。
"""
    rewritten = agent._rewrite_plan_topic(  # noqa: SLF001
        markdown,
        topic="更新后的主题",
        config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    assert 'title: "更新后的主题"' in rewritten
    assert 'topic: "更新后的主题"' in rewritten
    assert "max_depth: 2" in rewritten
    assert "保持正文不变。" in rewritten


def test_rewrite_plan_topic_without_front_matter() -> None:
    agent = _build_agent()
    rewritten = agent._rewrite_plan_topic(  # noqa: SLF001
        "## 只有正文",
        topic="无头部主题",
        config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    assert rewritten.startswith("---")
    assert "title: 无头部主题" in rewritten
    assert "topic: 无头部主题" in rewritten
    assert "## 只有正文" in rewritten


@pytest.mark.asyncio
async def test_revise_plan_creates_new_version_and_keeps_history(monkeypatch: pytest.MonkeyPatch) -> None:
    init_db()
    repo = ConversationRepository()
    conversation_id = new_id()
    repo.create_conversation(
        conversation_id=conversation_id,
        topic="多智能体可靠性",
        status=ConversationStatus.PLAN_READY,
        config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    repo.add_plan_revision(
        conversation_id,
        author=MessageRole.ASSISTANT,
        markdown="---\ntitle: v1\ntopic: t\nmax_depth: 2\nmax_nodes: 8\npriority: 3\nsearch_sources: [arXiv]\n---\n",
    )

    agent = _build_agent()
    monkeypatch.setattr(
        agent,
        "_generate_revised_plan",
        lambda **kwargs: "---\ntitle: v2\ntopic: t\nmax_depth: 2\nmax_nodes: 8\npriority: 3\nsearch_sources: [arXiv]\n---\n## 新方案\n",
    )

    revised_plan, revised_message = await agent.revise_plan(
        conversation_id=conversation_id,
        instruction="请增加风险章节",
    )
    assert revised_plan.version == 2
    assert revised_message.kind == MessageKind.PLAN_REVISION
    assert repo.get_plan_revision(conversation_id, 1).version == 1
    assert "新方案" in repo.get_current_plan(conversation_id).markdown


@pytest.mark.asyncio
async def test_revise_plan_allows_completed_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    init_db()
    repo = ConversationRepository()
    conversation_id = new_id()
    repo.create_conversation(
        conversation_id=conversation_id,
        topic="完成态继续修订",
        status=ConversationStatus.COMPLETED,
        config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    repo.add_plan_revision(
        conversation_id,
        author=MessageRole.ASSISTANT,
        markdown="---\ntitle: v1\ntopic: t\nmax_depth: 2\nmax_nodes: 8\npriority: 3\nsearch_sources: [arXiv]\n---\n",
    )

    agent = _build_agent()
    monkeypatch.setattr(
        agent,
        "_generate_revised_plan",
        lambda **kwargs: "---\ntitle: v2\ntopic: t\nmax_depth: 2\nmax_nodes: 8\npriority: 3\nsearch_sources: [arXiv]\n---\n## 补充章节\n",
    )
    revised_plan, _ = await agent.revise_plan(
        conversation_id=conversation_id,
        instruction="请补充风险与局限",
    )
    assert revised_plan.version == 2
    assert repo.get_summary(conversation_id).status == ConversationStatus.PLAN_READY


@pytest.mark.asyncio
async def test_revise_plan_routes_to_report_revision_when_report_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    init_db()
    repo = ConversationRepository()
    task_repo = TaskRepository()
    conversation_id = new_id()
    repo.create_conversation(
        conversation_id=conversation_id,
        topic="报告改写测试",
        status=ConversationStatus.COMPLETED,
        config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    plan = repo.add_plan_revision(
        conversation_id,
        author=MessageRole.ASSISTANT,
        markdown="---\ntitle: v1\ntopic: t\nmax_depth: 2\nmax_nodes: 8\npriority: 3\nsearch_sources: [arXiv]\n---\n",
    )
    task = task_repo.create_task(
        task_id=new_id(),
        title="报告改写测试任务",
        description="已有报告，继续改写",
        config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    report_path = tmp_path / f"{task.taskId}.md"
    report_path.write_text("# 原始报告\n\n旧内容。", encoding="utf-8")
    task_repo.set_report_path(task.taskId, str(report_path))
    repo.set_task_id(conversation_id, task.taskId)

    agent = _build_agent()
    monkeypatch.setattr(
        agent,
        "_rewrite_report_with_llm",
        lambda **kwargs: "# 演讲稿版本\n\n这是改写后的内容。",
    )
    revised_plan, revised_message = await agent.revise_plan(
        conversation_id=conversation_id,
        instruction="请你修改为演讲稿的格式",
    )

    assert revised_plan.version == plan.version
    assert revised_message.kind == MessageKind.USER_TEXT
    assert "正在修改中" in revised_message.content

    deadline = time.time() + 2
    final_report = ""
    final_status = ""
    while time.time() < deadline:
        detail = repo.get_detail(conversation_id)
        final_status = detail.status.value
        final_messages = [message for message in detail.messages if message.kind == MessageKind.FINAL_REPORT]
        if final_messages:
            final_report = final_messages[-1].content
        if final_status == ConversationStatus.COMPLETED.value and final_report:
            break
        await asyncio.sleep(0.05)

    assert final_status == ConversationStatus.COMPLETED.value
    assert "演讲稿版本" in final_report
    assert report_path.read_text(encoding="utf-8").startswith("# 演讲稿版本")
    progress_messages = [message for message in detail.messages if message.kind == MessageKind.PROGRESS_GROUP]
    assert len(progress_messages) >= 1
    progress_entries = [
        entry
        for message in progress_messages
        for entry in (message.metadata.get("entries") if isinstance(message.metadata.get("entries"), list) else [])
        if isinstance(entry, dict)
    ]
    assert any(entry.get("phase") == "WRITING_DRAFT" for entry in progress_entries)
    assert any(entry.get("phase") == "REPORT_COMPLETED" for entry in progress_entries)


def test_revise_report_and_record_prefers_current_report_over_rebuild(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    init_db()
    repo = ConversationRepository()
    task_repo = TaskRepository()
    conversation_id = new_id()
    repo.create_conversation(
        conversation_id=conversation_id,
        topic="基于现有报告改写",
        status=ConversationStatus.COMPLETED,
        config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    repo.add_plan_revision(
        conversation_id,
        author=MessageRole.ASSISTANT,
        markdown="---\ntitle: v1\ntopic: t\nmax_depth: 2\nmax_nodes: 8\npriority: 3\nsearch_sources: [arXiv]\n---\n",
    )
    task = task_repo.create_task(
        task_id=new_id(),
        title="改写任务",
        description="已有报告",
        config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    report_path = tmp_path / f"{task.taskId}.md"
    report_path.write_text("# 旧报告\n\n保留核心结论。", encoding="utf-8")
    task_repo.set_report_path(task.taskId, str(report_path))
    repo.set_task_id(conversation_id, task.taskId)

    agent = _build_agent()
    rebuild_called = False

    def _fake_rebuild(**kwargs: object) -> str:
        nonlocal rebuild_called
        rebuild_called = True
        _ = kwargs
        return "# 重建版本"

    monkeypatch.setattr(agent, "_regenerate_report_from_existing_artifacts", _fake_rebuild)
    monkeypatch.setattr(agent, "_rewrite_report_with_llm", lambda **kwargs: "# 改写版本\n\n这是在旧稿基础上的改写。")

    revised_message = agent._revise_report_and_record(  # noqa: SLF001
        conversation_id=conversation_id,
        task_id=task.taskId,
        instruction="请改成演讲稿风格",
    )

    assert rebuild_called is False
    assert revised_message.kind == MessageKind.FINAL_REPORT
    assert revised_message.content.startswith("# 改写版本")
    assert report_path.read_text(encoding="utf-8").startswith("# 改写版本")


@pytest.mark.asyncio
async def test_revise_plan_restarts_research_when_instruction_requires_new_retrieval(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    init_db()
    repo = ConversationRepository()
    task_repo = TaskRepository()
    conversation_id = new_id()
    repo.create_conversation(
        conversation_id=conversation_id,
        topic="补充资料并重跑",
        status=ConversationStatus.COMPLETED,
        config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    repo.add_plan_revision(
        conversation_id,
        author=MessageRole.ASSISTANT,
        markdown=(
            "---\n"
            "title: 补充资料并重跑\n"
            "topic: 补充资料并重跑\n"
            "max_depth: 2\n"
            "max_nodes: 8\n"
            "priority: 3\n"
            "search_sources: [arXiv]\n"
            "---\n"
            "## 研究目标\n"
            "验证可重跑。\n"
        ),
    )
    old_task = task_repo.create_task(
        task_id=new_id(),
        title="旧任务",
        description="旧任务描述",
        config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    report_path = tmp_path / f"{old_task.taskId}.md"
    report_path.write_text("# 旧报告\n\n旧内容。", encoding="utf-8")
    task_repo.set_report_path(old_task.taskId, str(report_path))
    repo.set_task_id(conversation_id, old_task.taskId)

    agent = _build_agent()
    monkeypatch.setattr(
        agent,
        "_generate_revised_plan",
        lambda **kwargs: (
            "---\n"
            "title: 新方案\n"
            "topic: 补充资料并重跑\n"
            "max_depth: 2\n"
            "max_nodes: 8\n"
            "priority: 3\n"
            "search_sources: [arXiv]\n"
            "---\n"
            "## 研究目标\n"
            "请补充资料并重新研究。\n"
        ),
    )
    revised_plan, response_message = await agent.revise_plan(
        conversation_id=conversation_id,
        instruction="请补充资料并重新研究",
    )

    assert revised_plan.version == 2
    assert "研究任务已启动" in response_message.content
    summary = repo.get_summary(conversation_id)
    assert summary.status == ConversationStatus.RUNNING
    assert summary.taskId and summary.taskId != old_task.taskId


def test_update_plan_allows_failed_conversation() -> None:
    init_db()
    repo = ConversationRepository()
    conversation_id = new_id()
    repo.create_conversation(
        conversation_id=conversation_id,
        topic="失败态继续编辑",
        status=ConversationStatus.FAILED,
        config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    repo.add_plan_revision(
        conversation_id,
        author=MessageRole.ASSISTANT,
        markdown="---\ntitle: 初始\ntopic: t\nmax_depth: 2\nmax_nodes: 8\npriority: 3\nsearch_sources: [arXiv]\n---\n",
    )

    agent = _build_agent()
    revision = agent.update_plan(
        conversation_id=conversation_id,
        markdown=(
            "---\n"
            "title: 新方案\n"
            "topic: t\n"
            "max_depth: 2\n"
            "max_nodes: 8\n"
            "priority: 3\n"
            "search_sources: [arXiv]\n"
            "---\n"
            "## 目标\n"
            "继续优化。\n"
        ),
    )
    assert revision.version == 2
    assert repo.get_summary(conversation_id).status == ConversationStatus.PLAN_READY


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_status", [ConversationStatus.COMPLETED, ConversationStatus.FAILED])
async def test_start_research_allows_terminal_conversation(initial_status: ConversationStatus) -> None:
    init_db()
    repo = ConversationRepository()
    conversation_id = new_id()
    repo.create_conversation(
        conversation_id=conversation_id,
        topic="终态重跑",
        status=initial_status,
        config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    repo.add_plan_revision(
        conversation_id,
        author=MessageRole.ASSISTANT,
        markdown=(
            "---\n"
            "title: 终态重跑\n"
            "topic: 终态重跑\n"
            "max_depth: 2\n"
            "max_nodes: 8\n"
            "priority: 3\n"
            "search_sources: [arXiv]\n"
            "---\n"
            "## 研究目标\n"
            "验证终态可继续执行。\n"
        ),
    )

    agent = _build_agent()
    result = await agent.start_research(conversation_id=conversation_id)
    assert result.status == ConversationStatus.RUNNING
    assert result.taskId
    summary = repo.get_summary(conversation_id)
    assert summary.status == ConversationStatus.RUNNING
    assert summary.taskId == result.taskId


@pytest.mark.asyncio
async def test_on_task_event_groups_progress_by_phase() -> None:
    init_db()
    repo = ConversationRepository()
    conversation_id = new_id()
    repo.create_conversation(
        conversation_id=conversation_id,
        topic="进度分组测试",
        status=ConversationStatus.RUNNING,
        config=TaskConfig(),
    )
    repo.add_plan_revision(
        conversation_id,
        author=MessageRole.ASSISTANT,
        markdown="---\ntitle: test\ntopic: test\nmax_depth: 2\nmax_nodes: 8\npriority: 3\nsearch_sources: [arXiv]\n---\n",
    )
    task_id = new_id()
    repo.set_task_id(conversation_id, task_id)
    agent = _build_agent()

    await agent.on_task_event(
        task_id=task_id,
        event="TASK_PROGRESS",
        data={
            "state": "EXECUTING",
            "phase": "SEARCHING",
            "progress": 30,
            "currentNodeTitle": "背景研究",
            "searchQuery": "query 1",
        },
    )
    await agent.on_task_event(
        task_id=task_id,
        event="TASK_PROGRESS",
        data={
            "state": "EXECUTING",
            "phase": "SEARCHING",
            "progress": 40,
            "currentNodeTitle": "背景研究",
            "searchQuery": "query 2",
        },
    )

    messages = repo.get_detail(conversation_id).messages
    groups = [message for message in messages if message.kind == MessageKind.PROGRESS_GROUP]
    assert len(groups) == 1
    assert groups[0].collapsed is True
    assert groups[0].metadata["taskId"] == task_id
    assert groups[0].metadata["phase"] == "SEARCHING"
    assert len(groups[0].metadata["entries"]) == 2


def test_delete_all_conversations_aborts_running_tasks() -> None:
    init_db()
    repo = ConversationRepository()
    task_repo = TaskRepository()
    agent, engine = _build_agent_with_engine()

    conversation_id = new_id()
    repo.create_conversation(
        conversation_id=conversation_id,
        topic="批量删除测试",
        status=ConversationStatus.RUNNING,
        config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    task = task_repo.create_task(
        task_id=new_id(),
        title="运行中的任务",
        description="测试批量删除时中断任务",
        config=TaskConfig(maxDepth=2, maxNodes=8, priority=3, searchSources=["arXiv"]),
    )
    task_repo.update_status(task.taskId, TaskStatus.EXECUTING)
    repo.set_task_id(conversation_id, task.taskId)

    deleted_count = agent.delete_all_conversations()

    assert deleted_count >= 1
    assert task.taskId in engine.aborted_task_ids
    assert repo.list_summaries() == []
