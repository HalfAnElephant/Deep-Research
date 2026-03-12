"""API dependencies and utility decorators for FastAPI routes."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from fastapi import HTTPException

F = TypeVar("F", bound=Callable[..., Any])


def handle_key_error(entity_name: str) -> Callable[[F], F]:
    """Decorator to convert KeyError exceptions to HTTP 404 responses.

    Args:
        entity_name: The name of the entity being accessed (e.g., "Task", "Conversation")

    Example:
        @router.get("/tasks/{task_id}")
        @handle_key_error("Task")
        def get_task(task_id: str) -> Task:
            return task_repository.get_task(task_id)  # Raises KeyError if not found
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except KeyError as e:
                raise HTTPException(
                    status_code=404,
                    detail=f"{entity_name} not found: {e.args[0]}"
                ) from e

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except KeyError as e:
                raise HTTPException(
                    status_code=404,
                    detail=f"{entity_name} not found: {e.args[0]}"
                ) from e

        # Return async or sync wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    return decorator
