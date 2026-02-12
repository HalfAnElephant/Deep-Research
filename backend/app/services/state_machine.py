from __future__ import annotations

from app.models.schemas import TaskStatus


ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.READY: {TaskStatus.PLANNING, TaskStatus.SUSPENDED, TaskStatus.ABORTED},
    TaskStatus.PLANNING: {TaskStatus.EXECUTING, TaskStatus.SUSPENDED, TaskStatus.ABORTED, TaskStatus.FAILED},
    TaskStatus.EXECUTING: {
        TaskStatus.REVIEWING,
        TaskStatus.SYNTHESIZING,
        TaskStatus.SUSPENDED,
        TaskStatus.ABORTED,
        TaskStatus.FAILED,
    },
    TaskStatus.REVIEWING: {
        TaskStatus.EXECUTING,
        TaskStatus.SYNTHESIZING,
        TaskStatus.SUSPENDED,
        TaskStatus.ABORTED,
        TaskStatus.FAILED,
    },
    TaskStatus.SYNTHESIZING: {TaskStatus.FINALIZING, TaskStatus.SUSPENDED, TaskStatus.ABORTED, TaskStatus.FAILED},
    TaskStatus.FINALIZING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.SUSPENDED: {TaskStatus.READY, TaskStatus.PLANNING, TaskStatus.EXECUTING, TaskStatus.REVIEWING},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.ABORTED: set(),
}


class InvalidStateTransition(ValueError):
    pass


def transition_or_raise(current: TaskStatus, target: TaskStatus) -> TaskStatus:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidStateTransition(f"Invalid transition: {current.value} -> {target.value}")
    return target
