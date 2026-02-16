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
    groups = [message for message in repo.get_detail(conversation_id).messages if message.kind == MessageKind.PROGRESS_GROUP]
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
        payload={"taskId": task_id_first, "state": "EXECUTING", "phase": "SEARCHING"},
    )
    second = repo.append_progress_entry(
        conversation_id,
        task_id=task_id_second,
        message_id=new_id(),
        phase="SEARCHING",
        state="EXECUTING",
        summary="第二轮检索",
        progress=20,
        payload={"taskId": task_id_second, "state": "EXECUTING", "phase": "SEARCHING"},
    )

    assert second.messageId != first.messageId
    groups = [message for message in repo.get_detail(conversation_id).messages if message.kind == MessageKind.PROGRESS_GROUP]
    assert len(groups) == 2
    task_ids = {str(message.metadata.get("taskId")) for message in groups}
    assert task_id_first in task_ids
    assert task_id_second in task_ids
