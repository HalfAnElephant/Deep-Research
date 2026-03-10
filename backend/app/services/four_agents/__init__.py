"""四 Agent 架构模块。

包含：
- IdeationAgent: 构思智能体（文献调研、研究方向分析、研究假设生成）
- PlanningAgent: 规划智能体（将假设转化为可执行方案）
- WritingAgent: 写作智能体（整合产出，撰写论文）
- CheckingAgent: 检查智能体（评审文章质量）
"""

from app.services.four_agents.base import BaseAgent
from app.services.four_agents.ideation_agent import IdeationAgent
from app.services.four_agents.planning_agent import PlanningAgent
from app.services.four_agents.writing_agent import WritingAgent
from app.services.four_agents.checking_agent import CheckingAgent

__all__ = [
    "BaseAgent",
    "IdeationAgent",
    "PlanningAgent",
    "WritingAgent",
    "CheckingAgent",
]