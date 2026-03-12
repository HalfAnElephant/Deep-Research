from __future__ import annotations

from app.core.database import init_db
from app.core.utils import new_id
from app.models.schemas import ConversationStatus, MessageKind, TaskConfig
from app.repositories.conversation_repository import ConversationRepository


def test_append_progress_entry_reuses_group_for_same_task_and_phase() -> None:
    init_db()
    repo = ConversationRepository()
    conversation_id = new_id()
    task_id = new_id()
    repo.create_conversation(
        conversation_id=conversation_id,
        topic="进度聚合复用",
        status=ConversationStatus.RUNNING,
        config=TaskConfig(),
    )
    repo.set_task_id(conversation_id, task_id)

    first = repo.append_progress_entry(
        conversation_id,
        task_id=task_id,
        message_id=new_id(),
        phase="SEARCHING",
        state="EXECUTING",
        summary="检索 query 1",
        progress=30,
        payload={"taskId": task_id, "state": "EXECUTING", "phase": "SEARCHING"},
    )
    second = repo.append_progress_entry(
        conversation_id,
        task_id=task_id,
        message_id=new_id(),
        phase="SEARCHING",
        state="EXECUTING",
        summary="检索 query 2",
        progress=40,
        payload={"taskId": task_id, "state": "EXECUTING", "phase": "SEARCHING"},
    )

    assert second.messageId == first.messageId
    groups = [message for message in repo.get_detail(
        conversation_id).messages if message.kind == MessageKind.PROGRESS_GROUP]
    assert len(groups) == 1
    assert groups[0].metadata["taskId"] == task_id
    assert len(groups[0].metadata["entries"]) == 2


def test_append_progress_entry_separates_group_for_different_task_ids() -> None:
    init_db()
    repo = ConversationRepository()
    conversation_id = new_id()
    repo.create_conversation(
        conversation_id=conversation_id,
        topic="进度聚合分轮次",
        status=ConversationStatus.RUNNING,
        config=TaskConfig(),
    )

    task_id_first = new_id()
    task_id_second = new_id()
    first = repo.append_progress_entry(
        conversation_id,
        task_id=task_id_first,
        message_id=new_id(),
        phase="SEARCHING",
        state="EXECUTING",
        summary="第一轮检索",
        progress=35,
        payload={"taskId": task_id_first,
                 "state": "EXECUTING", "phase": "SEARCHING"},
    )
    second = repo.append_progress_entry(
        conversation_id,
        task_id=task_id_second,
        message_id=new_id(),
        phase="SEARCHING",
        state="EXECUTING",
        summary="第二轮检索",
        progress=20,
        payload={"taskId": task_id_second,
                 "state": "EXECUTING", "phase": "SEARCHING"},
    )

    assert second.messageId != first.messageId
    groups = [message for message in repo.get_detail(
        conversation_id).messages if message.kind == MessageKind.PROGRESS_GROUP]
    assert len(groups) == 2
    task_ids = {str(message.metadata.get("taskId")) for message in groups}
    assert task_id_first in task_ids
    assert task_id_second in task_ids


def test_get_detail_derives_agent_states_from_phase_progress() -> None:
    init_db()
    repo = ConversationRepository()
    conversation_id = new_id()
    task_id = new_id()
    repo.create_conversation(
        conversation_id=conversation_id,
        topic="Agent 状态推导",
        status=ConversationStatus.RUNNING,
        config=TaskConfig(),
    )
    repo.set_task_id(conversation_id, task_id)

    repo.append_progress_entry(
        conversation_id,
        task_id=task_id,
        message_id=new_id(),
        phase="WRITING_SECTION",
        state="SYNTHESIZING",
        summary="正在写作章节",
        progress=92,
        payload={"taskId": task_id, "phase": "WRITING_SECTION",
                 "state": "SYNTHESIZING", "progress": 92},
    )

    detail = repo.get_detail(conversation_id)
    state_map = {state.agentType.value: state for state in detail.agentStates}

    assert state_map["IDEATION"].status.value == "COMPLETED"
    assert state_map["PLANNING"].status.value == "COMPLETED"
    assert state_map["WRITING"].status.value == "RUNNING"
    assert state_map["CHECKING"].status.value == "IDLE"


def test_get_detail_prefers_agent_status_payload_when_available() -> None:
    init_db()
    repo = ConversationRepository()
    conversation_id = new_id()
    task_id = new_id()
    repo.create_conversation(
        conversation_id=conversation_id,
        topic="Agent 事件状态",
        status=ConversationStatus.RUNNING,
        config=TaskConfig(),
    )
    repo.set_task_id(conversation_id, task_id)

    repo.append_progress_entry(
        conversation_id,
        task_id=task_id,
        message_id=new_id(),
        phase="AGENT_STATUS",
        state="RUNNING",
        summary="WRITING RUNNING",
        progress=60,
        payload={
            "taskId": task_id,
            "event": "AGENT_STATUS",
            "agentType": "WRITING",
            "status": "RUNNING",
            "progress": 60,
            "currentActivity": "写作中",
        },
    )

    detail = repo.get_detail(conversation_id)
    state_map = {state.agentType.value: state for state in detail.agentStates}

    assert state_map["WRITING"].status.value == "RUNNING"
    assert state_map["WRITING"].progress == 60
    assert state_map["WRITING"].currentActivity == "写作中"


def test_get_detail_resets_prior_agent_activity_to_completed() -> None:
    init_db()
    repo = ConversationRepository()
    conversation_id = new_id()
    task_id = new_id()
    repo.create_conversation(
        conversation_id=conversation_id,
        topic="完成态活动文案",
        status=ConversationStatus.RUNNING,
        config=TaskConfig(),
    )
    repo.set_task_id(conversation_id, task_id)

    repo.append_progress_entry(
        conversation_id,
        task_id=task_id,
        message_id=new_id(),
        phase="SEARCHING",
        state="EXECUTING",
        summary="IDEATION RUNNING",
        progress=30,
        payload={
            "taskId": task_id,
            "event": "AGENT_STATUS",
            "agentType": "IDEATION",
            "status": "RUNNING",
            "progress": 30,
            "currentActivity": "当前阶段持续 25 秒未出现新进展，系统仍在运行，建议继续等待或稍后重试。",
        },
    )
    repo.append_progress_entry(
        conversation_id,
        task_id=task_id,
        message_id=new_id(),
        phase="WRITING_SECTION",
        state="SYNTHESIZING",
        summary="WRITING RUNNING",
        progress=92,
        payload={
            "taskId": task_id,
            "event": "AGENT_STATUS",
            "agentType": "WRITING",
            "status": "RUNNING",
            "progress": 92,
            "currentActivity": "正在写作内容片段",
        },
    )

    detail = repo.get_detail(conversation_id)
    state_map = {state.agentType.value: state for state in detail.agentStates}

    assert state_map["IDEATION"].status.value == "COMPLETED"
    assert state_map["IDEATION"].currentActivity == "阶段完成"
    assert state_map["PLANNING"].status.value == "COMPLETED"
    assert state_map["PLANNING"].currentActivity == "阶段完成"
