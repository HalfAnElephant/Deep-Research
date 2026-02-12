from __future__ import annotations

from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.task_repository import TaskRepository
from app.services.execution_engine import ExecutionEngine
from app.services.planner import MasterPlanner
from app.services.progress_hub import ProgressHub
from app.services.retrieval import RetrievalService

task_repository = TaskRepository()
evidence_repository = EvidenceRepository()
planner = MasterPlanner()
progress_hub = ProgressHub()
retrieval_service = RetrievalService()
execution_engine = ExecutionEngine(task_repository, planner, progress_hub, evidence_repository, retrieval_service)
