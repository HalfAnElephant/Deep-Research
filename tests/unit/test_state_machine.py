import pytest

from app.models.schemas import TaskStatus
from app.services.state_machine import InvalidStateTransition, transition_or_raise


def test_valid_transition() -> None:
    assert transition_or_raise(TaskStatus.READY, TaskStatus.PLANNING) == TaskStatus.PLANNING


def test_ready_to_executing_is_allowed_for_prebuilt_dag() -> None:
    assert transition_or_raise(TaskStatus.READY, TaskStatus.EXECUTING) == TaskStatus.EXECUTING


def test_invalid_transition() -> None:
    with pytest.raises(InvalidStateTransition):
        transition_or_raise(TaskStatus.READY, TaskStatus.COMPLETED)
