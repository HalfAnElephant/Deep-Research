from __future__ import annotations

from app.repositories.task_repository import TaskRepository
from app.services.execution_engine import ExecutionEngine
from app.services.planner import MasterPlanner
from app.services.progress_hub import ProgressHub

task_repository = TaskRepository()
planner = MasterPlanner()
progress_hub = ProgressHub()
execution_engine = ExecutionEngine(task_repository, planner, progress_hub)
