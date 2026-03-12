"""LLM-based deep checking for the checking agent."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

import httpx

from app.core.config import settings

from .constants import MECHANICAL_TONE_PROMPT_TEMPLATE
from .models import CheckIssue

if TYPE_CHECKING:
    from .agent import CheckingAgent

logger = logging.getLogger(__name__)


class LLMChecker:
    """Uses LLM for deep content analysis."""

    def __init__(self, agent: "CheckingAgent") -> None:
        self.agent = agent

    async def check(self, content: str) -> list[CheckIssue]:
        """Use LLM to deep detect mechanical tone and writing quality issues."""
        issues = []

        # Analyze first 3000 characters
        sample_content = content[:3000]
        prompt = MECHANICAL_TONE_PROMPT_TEMPLATE.format(content=sample_content)

        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_medium) as client:
                response = await client.post(
                    self.agent.longcat_api_url,
                    headers={
                        "Authorization": f"Bearer {self.agent.longcat_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.agent.longcat_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                    },
                )
                response.raise_for_status()
                payload = response.json()

            result_text = (
                payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )

            # Parse JSON result
            if result_text:
                json_match = re.search(r'\{[\s\S]*\}', result_text)
                if json_match:
                    result = json.loads(json_match.group())
                    for issue in result.get("issues", []):
                        issues.append(CheckIssue(
                            severity=issue.get("severity", "minor"),
                            description=issue.get("type", "写作质量问题"),
                            location=issue.get("location"),
                            suggestion=issue.get("suggestion", "请人工检查并修改"),
                        ))

        except httpx.TimeoutException:
            logger.warning(f"LLM 深度检测超时 ({settings.llm_timeout_medium}s)")
        except httpx.HTTPStatusError as e:
            logger.warning(f"LLM 深度检测 HTTP 错误: {e.response.status_code}")
        except Exception as e:
            logger.warning(f"LLM 深度检测失败: {type(e).__name__}: {e}")

        return issues
