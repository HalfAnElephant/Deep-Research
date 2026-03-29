"""检查智能体 - 评审文章质量，确保符合要求。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.core.config import settings
from app.models.schemas import AgentType
from app.services.four_agents.base import AgentContext, AgentResult, BaseAgent

from .constants import REFERENCE_HEADING_PATTERN
from .llm_checker import LLMChecker
from .models import CheckIssue
from .validators import (
    CitationValidator,
    GarbageContentValidator,
    MechanicalToneValidator,
    PromptLeakageValidator,
    StructureValidator,
)

if TYPE_CHECKING:
    pass


class CheckingAgent(BaseAgent):
    """检查智能体。

    职责：
    - 评审文章质量
    - 检测提示词泄露
    - 验证引用格式
    - 检测"机器味"问题
    - 如有问题可打回写作智能体
    """

    agent_type = AgentType.CHECKING

    def __init__(self, on_progress=None) -> None:
        super().__init__(on_progress)
        self._validators = {
            "leakage": PromptLeakageValidator(),
            "mechanical": MechanicalToneValidator(),
            "structure": StructureValidator(),
            "citation": CitationValidator(),
            "garbage": GarbageContentValidator(),
        }
        self._llm_checker = LLMChecker(self)
        self._ref_pattern = REFERENCE_HEADING_PATTERN

    @property
    def longcat_api_url(self) -> str:
        """Get Longcat API URL from settings."""
        return f"{settings.longcat_base_url}/chat/completions"

    @property
    def longcat_model(self) -> str:
        """Get Longcat model from settings."""
        return settings.longcat_model

    @property
    def longcat_api_key(self) -> str:
        """Get Longcat API key from settings."""
        return settings.longcat_api_key

    async def run(self, context: AgentContext) -> AgentResult:
        """执行检查阶段任务。

        Args:
            context: 执行上下文，应包含 article_path。

        Returns:
            包含检查结果的执行结果。
        """
        article_path = context.config.get("article_path")
        if not article_path:
            return AgentResult(
                success=False,
                output={},
                error="缺少文章路径"
            )

        self._set_progress(10, "读取文章内容")

        # Read article
        try:
            article_content = Path(article_path).read_text(encoding="utf-8")
        except Exception as e:
            return AgentResult(
                success=False,
                output={},
                error=f"无法读取文章: {e}"
            )

        # Run all validators
        issues = self._run_validations(article_content)

        # Check with LLM if mechanical issues found
        if any(i for i in issues if "机器" in i.description or "机械" in i.description):
            self._set_progress(80, "使用 LLM 深度检测")
            llm_issues = await self._llm_checker.check(article_content)
            issues.extend(llm_issues)

        self._set_progress(95, "生成检查报告")

        # Determine approval status
        result = self._evaluate_approval(issues)
        return AgentResult(success=result["approved"], output=result)

    def _run_validations(self, content: str) -> list[CheckIssue]:
        """Run all validators on the content."""
        issues = []

        # Check for prompt leakage
        self._set_progress(20, "检测提示词泄露")
        issues.extend(self._validators["leakage"].validate(content))

        # Check for mechanical tone
        self._set_progress(40, "检测机器味")
        issues.extend(self._validators["mechanical"].validate(content))

        # Check structure
        self._set_progress(60, "检查文章结构")
        issues.extend(self._validators["structure"].validate(content))

        # Check citations
        self._set_progress(70, "验证引用格式")
        issues.extend(self._validators["citation"].validate(content))

        # Check garbage content
        self._set_progress(75, "检测垃圾内容")
        issues.extend(self._validators["garbage"].validate(content))

        return issues

    def _check_structure(self, content: str) -> list[CheckIssue]:
        """Backward-compatible shim for structure-only checks used by tests."""
        return self._validators["structure"].validate(content)

    def _evaluate_approval(self, issues: list[CheckIssue]) -> dict:
        """Evaluate if content passes based on issues found."""
        critical_issues = [i for i in issues if i.severity == "critical"]
        major_issues = [i for i in issues if i.severity == "major"]

        # Fail if critical issues exist
        approved = len(critical_issues) == 0 and len(major_issues) <= 1

        return {
            "approved": approved,
            "issues": [
                {
                    "severity": i.severity,
                    "description": i.description,
                    "location": i.location,
                    "suggestion": i.suggestion
                }
                for i in issues
            ],
            "summary": {
                "total_issues": len(issues),
                "critical": len(critical_issues),
                "major": len(major_issues),
                "minor": len(issues) - len(critical_issues) - len(major_issues)
            },
            "needs_rewrite": len(critical_issues) > 0 or len(major_issues) > 2
        }

    def _strip_reference_section(self, content: str) -> str:
        """Strip reference section from content."""
        match = self._ref_pattern.search(content)
        if not match:
            return content
        return content[:match.start()].rstrip()
