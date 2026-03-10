"""构思智能体 - 负责文献调研、研究方向分析和研究假设生成。"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.models.schemas import AgentType, ResearchHypothesis
from app.services.four_agents.base import AgentContext, AgentResult, BaseAgent
from app.services.retrieval import RetrievalService


class IdeationAgent(BaseAgent):
    """构思智能体。

    职责：
    - 文献扫描与知识整合
    - 研究方向分析
    - 研究假设生成
    """

    agent_type = AgentType.IDEATION

    def __init__(
        self,
        retrieval_service: RetrievalService,
        on_progress=None
    ) -> None:
        super().__init__(on_progress)
        self.retrieval = retrieval_service

    async def run(self, context: AgentContext) -> AgentResult:
        """执行构思阶段任务。

        Args:
            context: 执行上下文。

        Returns:
            包含 ResearchHypothesis 的执行结果。
        """
        self._set_progress(10, "开始文献扫描")

        # 1. 文献扫描
        evidences = await self._scan_literature(
            topic=context.topic,
            sources=context.config.get("searchSources", ["Web Search", "arXiv", "Semantic Scholar"])
        )
        self._set_progress(40, f"扫描完成，发现 {len(evidences)} 条证据")

        # 2. 分析研究方向
        self._set_progress(50, "分析研究方向")
        directions = await self._analyze_directions(context.topic, evidences)
        self._set_progress(70, f"识别到 {len(directions)} 个研究方向")

        # 3. 生成研究假设
        self._set_progress(80, "生成研究假设")
        hypothesis = await self._generate_hypothesis(context, evidences, directions)
        self._set_progress(95, "假设生成完成")

        return AgentResult(
            success=True,
            output={
                "hypothesis": hypothesis.model_dump(),
                "evidence_count": len(evidences),
                "directions": directions
            }
        )

    async def _scan_literature(
        self,
        topic: str,
        sources: list[str],
        max_results: int = 20
    ) -> list:
        """扫描文献获取证据。"""
        from app.models.schemas import Evidence

        evidences: list[Evidence] = []

        try:
            # 使用检索服务获取证据
            results = await self.retrieval.retrieve(
                task_id="ideation",
                node_id="ideation",
                query=topic,
                sources=sources
            )
            evidences.extend(results[:max_results])
        except Exception:
            pass

        return evidences

    async def _analyze_directions(
        self,
        topic: str,
        evidences: list
    ) -> list[dict]:
        """分析潜在的研究方向。"""
        if not evidences:
            return [{"title": f"关于「{topic}」的基础研究", "priority": 1}]

        # 简化的方向分析 - 基于证据类型和内容
        directions = []
        seen_keywords = set()

        for ev in evidences[:10]:
            content = ev.content.lower() if ev.content else ""
            # 提取关键词作为研究方向
            keywords = content.split()[:3]
            key = " ".join(keywords)
            if key not in seen_keywords and len(key) > 5:
                seen_keywords.add(key)
                directions.append({
                    "title": key[:50],
                    "priority": len(directions) + 1,
                    "evidence_id": ev.id
                })

        return directions[:5]

    async def _generate_hypothesis(
        self,
        context: AgentContext,
        evidences: list,
        directions: list[dict]
    ) -> ResearchHypothesis:
        """生成研究假设。"""
        import uuid
        from datetime import datetime

        # 构建假设标题和描述
        hypothesis_id = str(uuid.uuid4())

        if directions:
            primary_direction = directions[0]
            title = f"关于「{context.topic}」的研究假设"
            description = f"基于文献分析，建议研究方向：{primary_direction['title']}"
        else:
            title = f"「{context.topic}」研究假设"
            description = f"针对「{context.topic}」开展系统性研究。"

        return ResearchHypothesis(
            hypothesisId=hypothesis_id,
            title=title,
            description=description,
            sources=[ev.id for ev in evidences[:5]],
            confidence=min(0.9, len(evidences) / 20),  # 基于证据数量的置信度
            createdAt=datetime.utcnow().isoformat()
        )