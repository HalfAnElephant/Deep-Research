"""规划智能体 - 将研究假设转化为可执行的研究方案。"""

from __future__ import annotations

from app.models.schemas import AgentType, ResearchHypothesis, ResearchPlan
from app.services.four_agents.base import AgentContext, AgentResult, BaseAgent


class PlanningAgent(BaseAgent):
    """规划智能体。

    职责：
    - 分析假设可行性
    - 生成可执行研究方案
    - 定义实验/研究步骤
    """

    agent_type = AgentType.PLANNING

    def __init__(self, on_progress=None) -> None:
        super().__init__(on_progress)

    async def run(self, context: AgentContext) -> AgentResult:
        """执行规划阶段任务。

        Args:
            context: 执行上下文，应包含 hypothesis。

        Returns:
            包含 ResearchPlan 的执行结果。
        """
        hypothesis_data = context.config.get("hypothesis")
        if not hypothesis_data:
            return AgentResult(
                success=False,
                output={},
                error="缺少研究假设数据"
            )

        self._set_progress(10, "分析研究假设")

        # 解析假设
        hypothesis = ResearchHypothesis(**hypothesis_data)
        self._set_progress(30, "评估可行性")

        # 分析可行性
        feasibility = self._assess_feasibility(hypothesis, context)
        self._set_progress(50, "生成研究方案")

        # 生成方案
        plan = await self._create_plan(hypothesis, context, feasibility)
        self._set_progress(90, "方案生成完成")

        return AgentResult(
            success=True,
            output={
                "plan": plan.model_dump(),
                "feasibility": feasibility
            }
        )

    def _assess_feasibility(
        self,
        hypothesis: ResearchHypothesis,
        context: AgentContext
    ) -> dict:
        """评估假设可行性。"""
        # 简化的可行性评估
        return {
            "score": 0.8,
            "factors": {
                "evidence_support": min(1.0, len(hypothesis.sources) / 5),
                "complexity": "medium",
                "resource_requirement": "standard"
            }
        }

    async def _create_plan(
        self,
        hypothesis: ResearchHypothesis,
        context: AgentContext,
        feasibility: dict
    ) -> ResearchPlan:
        """创建研究方案。"""
        import uuid
        from datetime import datetime

        plan_id = str(uuid.uuid4())

        # 根据假设生成研究步骤
        steps = [
            {
                "step_id": 1,
                "title": "文献综述",
                "description": f"系统性回顾「{context.topic}」相关文献",
                "type": "research",
                "estimated_time": "2-3天"
            },
            {
                "step_id": 2,
                "title": "数据收集",
                "description": "收集和整理相关数据源",
                "type": "data_collection",
                "estimated_time": "3-5天"
            },
            {
                "step_id": 3,
                "title": "分析研究",
                "description": "对收集的数据进行深入分析",
                "type": "analysis",
                "estimated_time": "5-7天"
            },
            {
                "step_id": 4,
                "title": "结果整理",
                "description": "整理研究发现并撰写报告",
                "type": "synthesis",
                "estimated_time": "2-3天"
            }
        ]

        return ResearchPlan(
            planId=plan_id,
            hypothesisId=hypothesis.hypothesisId,
            steps=steps,
            createdAt=datetime.utcnow().isoformat()
        )