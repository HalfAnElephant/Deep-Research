from __future__ import annotations

import pytest

from app.core.database import init_db
from app.core.utils import new_id
from app.models.schemas import ConversationStatus, MessageKind, MessageRole, TaskConfig
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.task_repository import TaskRepository
from app.services.conversation_agent import ConversationAgent


class _DummyEngine:
    async def start(self, task_id: str) -> None:
        _ = task_id


def _build_agent() -> ConversationAgent:
    return ConversationAgent(
        repository=ConversationRepository(),
        task_repository=TaskRepository(),
        execution_engine=_DummyEngine(),  # type: ignore[arg-type]
    )


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
    assert groups[0].metadata["phase"] == "SEARCHING"
    assert len(groups[0].metadata["entries"]) == 2
