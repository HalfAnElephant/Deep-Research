"""检查智能体 - 评审文章质量，确保符合要求。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.schemas import AgentType
from app.services.four_agents.base import AgentContext, AgentResult, BaseAgent


@dataclass
class CheckIssue:
    """检查发现的问题。"""
    severity: str  # "critical", "major", "minor"
    description: str
    location: str | None = None
    suggestion: str | None = None


class CheckingAgent(BaseAgent):
    """检查智能体。

    职责：
    - 评审文章质量
    - 检测提示词泄露
    - 验证引用格式
    - 如有问题可打回写作智能体
    """

    agent_type = AgentType.CHECKING

    # 需要检测的禁止模式
    FORBIDDEN_PATTERNS = [
        (r"_taskId:\s*\S+_", "内部任务 ID 泄露", "critical"),
        (r"\#\#\s*AI\s*综合解读", "AI 提示词泄露", "critical"),
        (r"\#\#\s*输出格式", "输出格式信息泄露", "major"),
        (r"\#\#\s*Trace\s*Section", "调试信息泄露", "major"),
        (r"\[locked\]", "锁定标记泄露", "minor"),
        (r"system\s*prompt", "系统提示词泄露", "critical"),
        (r"你是.*助手", "角色设定泄露", "major"),
    ]

    def __init__(self, on_progress=None) -> None:
        super().__init__(on_progress)

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

        # 读取文章
        try:
            article_content = Path(article_path).read_text(encoding="utf-8")
        except Exception as e:
            return AgentResult(
                success=False,
                output={},
                error=f"无法读取文章: {e}"
            )

        self._set_progress(30, "检测提示词泄露")

        # 检测泄露
        issues = self._check_prompt_leakage(article_content)
        self._set_progress(50, f"发现 {len(issues)} 个问题")

        # 检测结构
        self._set_progress(60, "检查文章结构")
        structure_issues = self._check_structure(article_content)
        issues.extend(structure_issues)

        # 检测引用
        self._set_progress(80, "验证引用格式")
        citation_issues = self._check_citations(article_content)
        issues.extend(citation_issues)

        self._set_progress(95, "生成检查报告")

        # 判断是否通过
        critical_issues = [i for i in issues if i.severity == "critical"]
        major_issues = [i for i in issues if i.severity == "major"]

        approved = len(critical_issues) == 0 and len(major_issues) <= 2

        return AgentResult(
            success=approved,
            output={
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
                }
            }
        )

    def _check_prompt_leakage(self, content: str) -> list[CheckIssue]:
        """检测提示词泄露。"""
        issues = []
        for pattern, description, severity in self.FORBIDDEN_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                issues.append(CheckIssue(
                    severity=severity,
                    description=description,
                    location=f"位置 {match.start()}-{match.end()}",
                    suggestion="删除或修改该内容"
                ))
        return issues

    def _check_structure(self, content: str) -> list[CheckIssue]:
        """检查文章结构。"""
        issues = []

        # 检查标题
        if not content.strip().startswith("# "):
            issues.append(CheckIssue(
                severity="major",
                description="文章缺少主标题",
                suggestion="在文章开头添加一级标题"
            ))

        # 检查章节
        sections = re.findall(r"^##\s+.+$", content, re.MULTILINE)
        if len(sections) < 3:
            issues.append(CheckIssue(
                severity="minor",
                description=f"文章章节较少（{len(sections)} 个）",
                suggestion="考虑添加更多章节以增强结构"
            ))

        # 检查字数
        word_count = len(content)
        if word_count < 1000:
            issues.append(CheckIssue(
                severity="major",
                description=f"文章内容过短（{word_count} 字）",
                suggestion="扩充文章内容至至少 1000 字"
            ))

        return issues

    def _check_citations(self, content: str) -> list[CheckIssue]:
        """检查引用格式。"""
        issues = []

        # 检查证据引用
        evidence_refs = re.findall(r"\[evidence:[\w-]+\]", content)
        if evidence_refs:
            # 检查是否有对应的参考文献
            if "## 参考文献" not in content and "## References" not in content:
                issues.append(CheckIssue(
                    severity="major",
                    description="文章包含证据引用但缺少参考文献章节",
                    suggestion="在文章末尾添加参考文献章节"
                ))

        return issues