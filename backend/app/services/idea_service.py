from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from app.core.config import settings
from app.core.utils import new_id
from app.models.schemas import (
    ExperimentProposal,
    Evidence,
    IdeaStatus,
    LLMProvider,
    RelatedWorkItem,
    ResearchIdea,
    ResearchMode,
    ResearchScoreCard,
    RiskAssessment,
    TaskConfig,
)
from app.prompts.ideation import build_ideation_system_prompt, build_ideation_user_prompt
from app.services.retrieval import RetrievalService


class IdeaService:
    def __init__(self, retrieval_service: RetrievalService | None = None) -> None:
        self.retrieval_service = retrieval_service

    def generate_ideas(self, *, topic: str, config: TaskConfig) -> tuple[list[ResearchIdea], list[Evidence]]:
        evidences = self._collect_seed_evidence(topic=topic, config=config)
        llm_ideas: list[ResearchIdea] = []
        if config.researchMode in {ResearchMode.EXPERIMENTAL_RESEARCH, ResearchMode.PAPER_WRITEUP}:
            llm_ideas = self._generate_with_llm(topic=topic, config=config, evidences=evidences)
        ideas = llm_ideas or self._fallback_ideas(topic=topic, config=config, evidences=evidences)
        return ideas[: config.numInitialIdeas], evidences

    def _collect_seed_evidence(self, *, topic: str, config: TaskConfig) -> list[Evidence]:
        if self.retrieval_service is None:
            return []
        try:
            asyncio.get_running_loop()
            return []
        except RuntimeError:
            pass
        try:
            results = asyncio.run(
                self.retrieval_service.retrieve(
                    task_id="conversation-idea",
                    node_id="conversation-idea",
                    query=topic,
                    sources=config.searchSources,
                )
            )
            return results[:6]
        except Exception:
            return []

    def _generate_with_llm(
        self,
        *,
        topic: str,
        config: TaskConfig,
        evidences: list[Evidence],
    ) -> list[ResearchIdea]:
        if settings.use_mock_sources:
            return []
        base_url, api_key, model = self._resolve_provider(config.llmProvider)
        if not base_url or not api_key:
            return []

        evidence_snippets = self._evidence_snippets(evidences)
        system_prompt = build_ideation_system_prompt(
            num_ideas=config.numInitialIdeas,
            num_reflections=config.numReflections,
        )
        user_prompt = build_ideation_user_prompt(
            topic=topic,
            search_sources=config.searchSources,
            evidence_snippets=evidence_snippets,
        )
        try:
            with httpx.Client(timeout=settings.llm_timeout_medium) as client:
                response = client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "temperature": 0.4,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
                response.raise_for_status()
                content = (
                    response.json().get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
        except Exception:
            return []

        payload = self._extract_json_payload(content)
        ideas_raw = payload.get("ideas") if isinstance(payload, dict) else None
        if not isinstance(ideas_raw, list):
            return []
        normalized: list[ResearchIdea] = []
        for index, item in enumerate(ideas_raw[: config.numInitialIdeas]):
            if not isinstance(item, dict):
                continue
            normalized.append(
                self._normalize_idea_payload(
                    payload=item,
                    topic=topic,
                    fallback_index=index,
                    evidences=evidences,
                )
            )
        return normalized

    def _fallback_ideas(
        self,
        *,
        topic: str,
        config: TaskConfig,
        evidences: list[Evidence],
    ) -> list[ResearchIdea]:
        evidence_ids = [ev.id for ev in evidences[:4]]
        evidence_titles = [ev.metadata.title for ev in evidences[:3] if ev.metadata.title]
        directions = [
            "现状与瓶颈",
            "方法机制与改进空间",
            "评估体系与风险边界",
            "落地条件与组织影响",
            "与现有方案的差异化价值",
        ]
        ideas: list[ResearchIdea] = []
        for index in range(config.numInitialIdeas):
            direction = directions[index % len(directions)]
            title = f"{topic}：{direction}"
            related = [
                RelatedWorkItem(
                    title=evidence_titles[i] if i < len(evidence_titles) else f"{topic} 相关工作线索 {i + 1}",
                    summary=f"与“{title}”相关的已有研究线索，用于后续 novelty 对照。",
                    relevanceScore=round(max(0.35, 0.72 - i * 0.1), 2),
                )
                for i in range(min(2, max(1, len(evidence_titles) or 1)))
            ]
            ideas.append(
                ResearchIdea(
                    ideaId=new_id(),
                    title=title,
                    problemStatement=f"围绕“{topic}”识别{direction}，建立可验证的问题定义与分析边界。",
                    shortHypothesis=f"如果围绕“{direction}”组织研究链路，可以更系统地回答“{topic}”的核心问题。",
                    abstract=(
                        f"该 idea 聚焦“{topic}”的{direction}，通过相关工作对照、证据归纳和实验/验证设想，"
                        "形成可执行的研究入口。"
                    ),
                    relatedWork=related,
                    differentiators=[
                        f"强调“{direction}”作为独立切入点，而不是泛泛罗列资料。",
                        "要求把差异点、风险和验证方法前置到研究入口。",
                    ],
                    experimentProposals=[
                        ExperimentProposal(
                            title=f"{direction}验证方案",
                            objective=f"验证“{topic}”在“{direction}”上的关键判断是否成立。",
                            method="整理代表性案例、提炼对照维度，并用统一指标比较优劣。",
                            metrics=["结论一致性", "证据覆盖度", "实施复杂度"],
                            expectedOutcome="得到可写入研究方案的核心判断和待验证假设。",
                        )
                    ],
                    riskFactors=[
                        RiskAssessment(
                            risk="相关工作重叠度可能偏高",
                            severity="medium",
                            mitigation="在 novelty gate 中补充与已有工作的差异化对照。",
                        )
                    ],
                    limitations=[
                        "首轮 idea 仍基于有限证据线索，后续需补充更系统的相关工作检查。"
                    ],
                    scoreCard=ResearchScoreCard(),
                    sourceEvidenceIds=evidence_ids,
                    status=IdeaStatus.CANDIDATE,
                )
            )
        return ideas

    def _normalize_idea_payload(
        self,
        *,
        payload: dict[str, Any],
        topic: str,
        fallback_index: int,
        evidences: list[Evidence],
    ) -> ResearchIdea:
        related_raw = payload.get("relatedWork")
        experiments_raw = payload.get("experimentProposals")
        risks_raw = payload.get("riskFactors")
        related = [
            RelatedWorkItem.model_validate(item)
            for item in related_raw
            if isinstance(item, dict)
        ] if isinstance(related_raw, list) else []
        experiments = [
            ExperimentProposal.model_validate(item)
            for item in experiments_raw
            if isinstance(item, dict)
        ] if isinstance(experiments_raw, list) else []
        risks = [
            RiskAssessment.model_validate(item)
            for item in risks_raw
            if isinstance(item, dict)
        ] if isinstance(risks_raw, list) else []

        return ResearchIdea(
            ideaId=str(payload.get("ideaId") or new_id()),
            title=str(payload.get("title") or f"{topic} 候选方案 {fallback_index + 1}")[:200],
            problemStatement=str(payload.get("problemStatement") or f"围绕“{topic}”构建问题定义。")[:2000],
            shortHypothesis=str(payload.get("shortHypothesis") or f"该 idea 用于回答“{topic}”的关键研究问题。")[:1000],
            abstract=str(payload.get("abstract") or f"围绕“{topic}”形成结构化研究构想。")[:3000],
            relatedWork=related,
            differentiators=[str(item)[:300] for item in payload.get("differentiators", []) if str(item).strip()],
            experimentProposals=experiments,
            riskFactors=risks,
            limitations=[str(item)[:300] for item in payload.get("limitations", []) if str(item).strip()],
            sourceEvidenceIds=[ev.id for ev in evidences[:4]],
            status=IdeaStatus.CANDIDATE,
        )

    @staticmethod
    def _extract_json_payload(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _evidence_snippets(evidences: list[Evidence]) -> str:
        if not evidences:
            return ""
        return "\n".join(
            f"- [{ev.id}] {ev.metadata.title} | {ev.metadata.publishDate or '未知'} | {ev.metadata.abstract[:180]}"
            for ev in evidences[:4]
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
