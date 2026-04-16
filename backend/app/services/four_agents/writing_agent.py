"""写作智能体 - 整合前序产出，撰写结构完整的文章。"""

from __future__ import annotations

from app.core.config import settings
from app.models.schemas import AgentType, Evidence
from app.services.four_agents.base import AgentContext, AgentResult, BaseAgent
from app.services.writer import WriterService


class WritingAgent(BaseAgent):
    """写作智能体。

    职责：
    - 整合前序所有阶段的产出
    - 撰写结构完整、符合学术规范的文章
    - 分离文章内容和引用列表
    """

    agent_type = AgentType.WRITING

    def __init__(
        self,
        output_dir: str | None = None,
        on_progress=None
    ) -> None:
        super().__init__(on_progress)
        self.writer = WriterService(output_dir or settings.reports_dir)

    async def run(self, context: AgentContext) -> AgentResult:
        """执行写作阶段任务。

        Args:
            context: 执行上下文，应包含 hypothesis、plan、evidences。

        Returns:
            包含文章和引用文件路径的执行结果。
        """
        hypothesis_data = context.config.get("hypothesis")
        evidences_data = context.config.get("evidences", [])

        if not evidences_data:
            return AgentResult(
                success=False,
                output={},
                error="缺少证据数据"
            )

        self._set_progress(10, "准备写作材料")

        # 解析证据
        evidences = [Evidence(**ev) if isinstance(ev, dict) else ev for ev in evidences_data]
        self._set_progress(20, f"整合 {len(evidences)} 条证据")

        # 解析假设和方案
        hypothesis_title = hypothesis_data.get("title", context.topic) if hypothesis_data else context.topic
        self._set_progress(30, "构建文章框架")

        # 生成文章
        self._set_progress(40, "撰写文章内容")

        # 使用 WriterService 生成报告
        article_path, references_path, citation_map = self.writer.write_report(
            task_id=context.task_id,
            task_title=hypothesis_title,
            task_description=context.config.get("description", ""),
            sections=[(f"section_{i}", f"Section {i}") for i in range(1, 4)],  # 简化的章节
            evidences=evidences
        )

        self._set_progress(90, "文章生成完成")

        return AgentResult(
            success=True,
            output={
                "article_path": article_path,
                "references_path": references_path,
                "citation_count": len(citation_map)
            }
        )
