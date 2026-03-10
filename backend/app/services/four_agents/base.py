"""Agent 基础类定义。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

from app.models.schemas import AgentStatus, AgentType


@dataclass
class AgentContext:
    """Agent 执行上下文。"""
    task_id: str
    conversation_id: str
    topic: str
    config: dict[str, Any]


@dataclass
class AgentResult:
    """Agent 执行结果。"""
    success: bool
    output: dict[str, Any]
    error: str | None = None


class BaseAgent(ABC):
    """Agent 基础类。

    所有智能体都应继承此类并实现 run 方法。
    """

    agent_type: AgentType

    def __init__(
        self,
        on_progress: Callable[[int, str], None] | None = None
    ) -> None:
        """初始化 Agent。

        Args:
            on_progress: 进度回调函数，接收 (progress, activity) 参数。
        """
        self._status: AgentStatus = AgentStatus.IDLE
        self._progress: int = 0
        self._current_activity: str = ""
        self._on_progress = on_progress

    @property
    def status(self) -> AgentStatus:
        """当前状态。"""
        return self._status

    @property
    def progress(self) -> int:
        """当前进度 (0-100)。"""
        return self._progress

    @property
    def current_activity(self) -> str:
        """当前活动描述。"""
        return self._current_activity

    def _set_status(self, status: AgentStatus) -> None:
        """设置状态。"""
        self._status = status

    def _set_progress(self, progress: int, activity: str = "") -> None:
        """设置进度并通知回调。"""
        self._progress = max(0, min(100, progress))
        self._current_activity = activity
        if self._on_progress:
            self._on_progress(self._progress, activity)

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult:
        """执行 Agent 任务。

        Args:
            context: 执行上下文。

        Returns:
            执行结果。
        """
        ...

    async def execute(self, context: AgentContext) -> AgentResult:
        """执行 Agent 任务（带状态管理）。

        Args:
            context: 执行上下文。

        Returns:
            执行结果。
        """
        self._set_status(AgentStatus.RUNNING)
        self._set_progress(0, "开始执行")

        try:
            result = await self.run(context)
            if result.success:
                self._set_status(AgentStatus.COMPLETED)
                self._set_progress(100, "执行完成")
            else:
                self._set_status(AgentStatus.FAILED)
            return result
        except Exception as e:
            self._set_status(AgentStatus.FAILED)
            return AgentResult(
                success=False,
                output={},
                error=str(e)
            )