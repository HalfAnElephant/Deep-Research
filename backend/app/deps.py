from __future__ import annotations

from app.repositories.conflict_repository import ConflictRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.task_repository import TaskRepository
from app.services.analyst import AnalystService
from app.services.execution_engine import ExecutionEngine
from app.services.mcp_executor import MCPExecutor
from app.services.planner import MasterPlanner
from app.services.progress_hub import ProgressHub
from app.services.retrieval import RetrievalService
from app.services.writer import WriterService

task_repository = TaskRepository()
evidence_repository = EvidenceRepository()
conflict_repository = ConflictRepository()
planner = MasterPlanner()
progress_hub = ProgressHub()
retrieval_service = RetrievalService()
analyst_service = AnalystService()
writer_service = WriterService()
mcp_executor = MCPExecutor()
execution_engine = ExecutionEngine(
    task_repository,
    planner,
    progress_hub,
    evidence_repository,
    retrieval_service,
    conflict_repository,
    analyst_service,
    writer_service,
)
