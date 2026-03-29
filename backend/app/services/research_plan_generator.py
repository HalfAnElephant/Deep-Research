"""Research Plan Generator - Generates structured research questions using LLM."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings
from app.core.utils import new_id
from app.models.schemas import LLMProvider, TaskConfig


@dataclass(frozen=True)
class ResearchQuestion:
    """A structured research question node."""
    question_id: str
    title: str
    description: str
    level: int
    rank: int
    parent_id: str | None
    children: list[str]


@dataclass(frozen=True)
class StructuredResearchPlan:
    """A complete structured research plan with hierarchical questions."""
    root_question: ResearchQuestion
    all_questions: dict[str, ResearchQuestion]
    total_nodes: int
    max_depth: int


class ResearchPlanGenerator:
    """Generates structured research questions using LLM."""

    _SYSTEM_PROMPT = """你是一个研究规划专家。你的任务是将用户的研究主题分解为一个结构化的研究问题树。

输出要求：
1. 必须输出有效的 JSON 格式
2. 每个问题节点包含：title（标题）、description（描述）、level（层级，从0开始）、rank（同级排序）
3. 问题树必须是一个合理的层级结构，根节点 level=0
4. 每个层级最多 4 个子问题
5. 每个问题应该独立、可研究

输出格式示例：
{
  "questions": [
    {
      "title": "核心研究问题",
      "description": "问题的详细描述",
      "level": 0,
      "rank": 0,
      "children": [
        {
          "title": "子问题1",
          "description": "子问题描述",
          "level": 1,
          "rank": 0,
          "children": []
        }
      ]
    }
  ]
}

注意：
- 不要输出任何额外的解释文本
- 确保 JSON 格式正确
- title 应简洁（不超过30字）
- description 应具体（50-150字）"""

    def generate(
        self,
        *,
        topic: str,
        description: str,
        config: TaskConfig,
    ) -> StructuredResearchPlan:
        """Generate a structured research plan using LLM."""
        user_prompt = self._build_user_prompt(topic=topic, description=description, config=config)

        try:
            response_text = self._call_llm(
                system_prompt=self._SYSTEM_PROMPT,
                user_prompt=user_prompt,
                provider=config.llmProvider,
            )
            return self._parse_response(response_text, topic=topic, description=description)
        except Exception:
            # Fallback to template-based generation if LLM fails
            return self._fallback_plan(topic=topic, description=description, config=config)

    def _build_user_prompt(
        self,
        *,
        topic: str,
        description: str,
        config: TaskConfig,
    ) -> str:
        max_nodes = min(config.maxNodes, 12)
        max_depth = min(config.maxDepth, 3)

        return f"""研究主题：{topic}

研究背景：{description[:500]}

约束条件：
- 最大深度：{max_depth} 层
- 最大节点数：{max_nodes} 个
- 每个层级最多 4 个并列问题

请生成结构化的研究问题树。"""

    def _call_llm(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        provider: LLMProvider | str | None = None,
    ) -> str:
        if settings.use_mock_sources:
            raise ValueError("Mock sources enabled")

        base_url, api_key, model = self._resolve_provider(provider)
        if not base_url or not api_key:
            raise ValueError("LLM provider not configured")

        with httpx.Client(timeout=settings.llm_timeout_medium) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "temperature": 0.3,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()

        return (
            payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

    @staticmethod
    def _resolve_provider(provider: LLMProvider | str | None = None) -> tuple[str, str, str]:
        selected = (provider.value if isinstance(provider, LLMProvider) else provider) or settings.default_llm_provider
        provider_name = selected.lower().strip()
        if provider_name == "openrouter":
            return settings.openrouter_base_url, settings.openrouter_api_key, settings.openrouter_model
        if provider_name == "deepseek":
            return settings.deepseek_base_url, settings.deepseek_api_key, settings.deepseek_model
        if provider_name == "openai":
            return settings.openai_base_url, settings.openai_api_key, settings.openai_model
        return "", "", ""

    def _parse_response(
        self,
        response_text: str,
        *,
        topic: str,
        description: str,
    ) -> StructuredResearchPlan:
        """Parse LLM response into a structured research plan."""
        # Extract JSON from response
        json_text = self._extract_json(response_text)

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            return self._fallback_plan(topic=topic, description=description, config=TaskConfig())

        questions_data = data.get("questions", [])
        if not questions_data:
            return self._fallback_plan(topic=topic, description=description, config=TaskConfig())

        all_questions: dict[str, ResearchQuestion] = {}
        root_id = new_id()

        def process_node(
            node_data: dict[str, Any],
            level: int,
            parent_id: str | None,
        ) -> str:
            question_id = new_id()
            children_data = node_data.get("children", [])
            children_ids: list[str] = []

            # Process children first to get their IDs
            for child_data in children_data:
                child_id = process_node(child_data, level + 1, question_id)
                children_ids.append(child_id)

            question = ResearchQuestion(
                question_id=question_id,
                title=node_data.get("title", "研究问题")[:60],
                description=node_data.get("description", "")[:500],
                level=level,
                rank=node_data.get("rank", 0),
                parent_id=parent_id,
                children=children_ids,
            )
            all_questions[question_id] = question
            return question_id

        # Process root node(s)
        root_questions = []
        for i, q_data in enumerate(questions_data):
            if i == 0:
                # First question becomes the root
                root_id = process_node(q_data, 0, None)
                root_questions.append(root_id)
            else:
                # Additional top-level questions become children of root
                q_id = process_node(q_data, 1, root_id)
                root_questions.append(q_id)

        if not all_questions:
            return self._fallback_plan(topic=topic, description=description, config=TaskConfig())

        root = all_questions.get(root_id)
        if not root:
            root = ResearchQuestion(
                question_id=root_id,
                title=topic[:60],
                description=description[:500],
                level=0,
                rank=0,
                parent_id=None,
                children=[],
            )
            all_questions[root_id] = root

        return StructuredResearchPlan(
            root_question=root,
            all_questions=all_questions,
            total_nodes=len(all_questions),
            max_depth=max(q.level for q in all_questions.values()) if all_questions else 0,
        )

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text that might contain markdown code blocks."""
        text = text.strip()

        # Try to find JSON in code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        # Try to find JSON object directly
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return text[start:end + 1]

        return text

    def _fallback_plan(
        self,
        *,
        topic: str,
        description: str,
        config: TaskConfig,
    ) -> StructuredResearchPlan:
        """Generate a fallback plan when LLM fails."""
        root_id = new_id()

        questions: dict[str, ResearchQuestion] = {
            root_id: ResearchQuestion(
                question_id=root_id,
                title=topic[:60],
                description=description[:500],
                level=0,
                rank=0,
                parent_id=None,
                children=[],
            ),
        }

        # Generate sub-questions based on topic
        sub_topics = [
            f"{topic}的核心问题",
            f"{topic}的关键证据",
            f"{topic}的争议与边界",
            f"{topic}的落地条件",
        ]

        for i, sub_title in enumerate(sub_topics[:4]):
            sub_id = new_id()
            questions[sub_id] = ResearchQuestion(
                question_id=sub_id,
                title=sub_title[:60],
                description=f'围绕"{sub_title}"展开深入研究',
                level=1,
                rank=i,
                parent_id=root_id,
                children=[],
            )
            # Update root's children
            root = questions[root_id]
            questions[root_id] = ResearchQuestion(
                question_id=root_id,
                title=root.title,
                description=root.description,
                level=root.level,
                rank=root.rank,
                parent_id=root.parent_id,
                children=list(root.children) + [sub_id],
            )

        return StructuredResearchPlan(
            root_question=questions[root_id],
            all_questions=questions,
            total_nodes=len(questions),
            max_depth=1,
        )


# Singleton instance
research_plan_generator = ResearchPlanGenerator()