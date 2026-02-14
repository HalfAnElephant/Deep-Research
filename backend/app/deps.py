from __future__ import annotations

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.conflict_repository import ConflictRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.task_repository import TaskRepository
from app.services.agents import ReportAgent, ResearchAgent
from app.services.analyst import AnalystService
from app.services.conversation_agent import ConversationAgent
from app.services.execution_engine import ExecutionEngine
from app.services.mcp_executor import MCPExecutor
from app.services.planner import MasterPlanner
from app.services.progress_hub import ProgressHub
from app.services.retrieval import RetrievalService
from app.services.writer import WriterService

task_repository = TaskRepository()
evidence_repository = EvidenceRepository()
conflict_repository = ConflictRepository()
conversation_repository = ConversationRepository()
planner = MasterPlanner()
progress_hub = ProgressHub()
retrieval_service = RetrievalService()
analyst_service = AnalystService()
writer_service = WriterService()
mcp_executor = MCPExecutor()
research_agent = ResearchAgent(retrieval_service=retrieval_service, mcp_executor=mcp_executor)
report_agent = ReportAgent(writer_service=writer_service)
execution_engine = ExecutionEngine(
    task_repository,
    planner,
    progress_hub,
    evidence_repository,
    retrieval_service,
    conflict_repository,
    analyst_service,
    writer_service,
    research_agent,
    report_agent,
)
conversation_agent = ConversationAgent(
    repository=conversation_repository,
    task_repository=task_repository,
    execution_engine=execution_engine,
)
execution_engine.set_event_listener(conversation_agent.on_task_event)
