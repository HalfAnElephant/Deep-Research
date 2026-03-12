"""检查智能体 - 向后兼容的导出模块。

该模块已重构为 checking 包。此文件保留以维持向后兼容性。
请使用以下方式导入：
    from app.services.four_agents.checking import CheckingAgent
"""

from __future__ import annotations

# Re-export from the new package for backward compatibility
from app.services.four_agents.checking import CheckingAgent, CheckIssue

__all__ = ["CheckingAgent", "CheckIssue"]
