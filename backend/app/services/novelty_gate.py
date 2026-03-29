from __future__ import annotations

import json

import httpx

from app.core.config import settings
from app.models.schemas import (
    Evidence,
    FeasibilityAssessment,
    IdeaStatus,
    LLMProvider,
    NoveltyAssessment,
    ResearchIdea,
    ResearchScoreCard,
)
from app.prompts.novelty import build_novelty_system_prompt, build_novelty_user_prompt


class NoveltyGateService:
    NOVELTY_THRESHOLD = 0.55
    FEASIBILITY_THRESHOLD = 0.5

    def evaluate_ideas(
        self,
        *,
        topic: str,
        ideas: list[ResearchIdea],
        evidences: list[Evidence],
        llm_provider: LLMProvider | str | None = None,
        enforce_thresholds: bool = True,
    ) -> list[ResearchIdea]:
        evaluated = [
            self._evaluate_single_idea(
                topic=topic,
                idea=idea,
                evidences=evidences,
                llm_provider=llm_provider,
                enforce_thresholds=enforce_thresholds,
            )
            for idea in ideas
        ]
        if not evaluated:
            return []

        best = max(evaluated, key=lambda idea: idea.scoreCard.overallScore)
        selected_id = best.ideaId
        normalized: list[ResearchIdea] = []
        for idea in evaluated:
            if idea.ideaId == selected_id:
                normalized.append(idea.model_copy(update={"status": IdeaStatus.SELECTED}))
                continue
            status = IdeaStatus.REJECTED if enforce_thresholds and not (
                idea.noveltyAssessment.noveltyScore >= self.NOVELTY_THRESHOLD
                and idea.feasibilityAssessment.feasibilityScore >= self.FEASIBILITY_THRESHOLD
            ) else IdeaStatus.CANDIDATE
            normalized.append(idea.model_copy(update={"status": status}))
        return normalized

    def _evaluate_single_idea(
        self,
        *,
        topic: str,
        idea: ResearchIdea,
        evidences: list[Evidence],
        llm_provider: LLMProvider | str | None,
        enforce_thresholds: bool,
    ) -> ResearchIdea:
        llm_assessment = self._evaluate_with_llm(
            topic=topic,
            idea=idea,
            evidences=evidences,
            llm_provider=llm_provider,
        )

        evidence_strength = min(1.0, 0.3 + 0.12 * min(len(idea.sourceEvidenceIds or evidences), 4))
        writeup_readiness = min(
            1.0,
            0.35
            + (0.15 if idea.abstract.strip() else 0.0)
            + (0.15 if idea.problemStatement.strip() else 0.0)
            + (0.15 if idea.shortHypothesis.strip() else 0.0)
            + 0.05 * min(len(idea.limitations), 2),
        )

        novelty = llm_assessment["novelty"].noveltyScore if llm_assessment else min(
            1.0,
            0.34
            + 0.08 * min(len(idea.differentiators), 3)
            + 0.05 * min(len(idea.experimentProposals), 2)
            + self._title_variation_boost(idea.title),
        )
        feasibility = llm_assessment["feasibility"].feasibilityScore if llm_assessment else min(
            1.0,
            0.32
            + 0.1 * min(len(idea.experimentProposals), 3)
            + 0.06 * min(len(idea.limitations), 2)
            + 0.08 * min(len(idea.riskFactors), 2)
            + 0.08 * evidence_strength,
        )
        novelty_assessment = llm_assessment["novelty"] if llm_assessment else NoveltyAssessment(
            summary="基于差异点、相关工作和验证方案做了启发式 novelty 评估。",
            noveltyScore=round(novelty, 4),
            isNovel=novelty >= self.NOVELTY_THRESHOLD if enforce_thresholds else True,
            similarWork=[item.title for item in idea.relatedWork[:2]],
            differentiationNotes=idea.differentiators[:3],
        )
        feasibility_assessment = llm_assessment["feasibility"] if llm_assessment else FeasibilityAssessment(
            summary="基于验证方案、限制与风险因素做了启发式 feasibility 评估。",
            feasibilityScore=round(feasibility, 4),
            isFeasible=feasibility >= self.FEASIBILITY_THRESHOLD if enforce_thresholds else True,
            blockers=[],
            assumptions=["后续仍需补充更多相关工作和证据。"],
        )
        overall = round(
            novelty_assessment.noveltyScore * 0.35
            + feasibility_assessment.feasibilityScore * 0.3
            + evidence_strength * 0.2
            + writeup_readiness * 0.15,
            4,
        )
        status = IdeaStatus.CANDIDATE
        if enforce_thresholds and (
            novelty_assessment.noveltyScore < self.NOVELTY_THRESHOLD
            or feasibility_assessment.feasibilityScore < self.FEASIBILITY_THRESHOLD
        ):
            status = IdeaStatus.REJECTED

        return idea.model_copy(
            update={
                "noveltyAssessment": novelty_assessment,
                "feasibilityAssessment": feasibility_assessment,
                "scoreCard": ResearchScoreCard(
                    noveltyScore=round(novelty_assessment.noveltyScore, 4),
                    feasibilityScore=round(feasibility_assessment.feasibilityScore, 4),
                    evidenceStrengthScore=round(evidence_strength, 4),
                    writeupReadinessScore=round(writeup_readiness, 4),
                    overallScore=overall,
                ),
                "status": status,
            }
        )

    def _evaluate_with_llm(
        self,
        *,
        topic: str,
        idea: ResearchIdea,
        evidences: list[Evidence],
        llm_provider: LLMProvider | str | None,
    ) -> dict[str, NoveltyAssessment | FeasibilityAssessment] | None:
        if settings.use_mock_sources:
            return None
        base_url, api_key, model = self._resolve_provider(llm_provider)
        if not base_url or not api_key:
            return None
        try:
            with httpx.Client(timeout=settings.llm_timeout_short) as client:
                response = client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "temperature": 0.2,
                        "messages": [
                            {"role": "system", "content": build_novelty_system_prompt()},
                            {
                                "role": "user",
                                "content": build_novelty_user_prompt(
                                    topic=topic,
                                    idea_json=idea.model_dump_json(indent=2),
                                    evidence_snippets=self._evidence_snippets(evidences),
                                ),
                            },
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
            payload = self._extract_json(content)
            novelty = NoveltyAssessment(
                summary=str(payload.get("summary") or ""),
                noveltyScore=float(payload.get("noveltyScore") or 0.0),
                isNovel=bool(payload.get("isNovel")),
                similarWork=[str(item) for item in payload.get("similarWork", []) if str(item).strip()],
                differentiationNotes=[str(item) for item in payload.get("differentiationNotes", []) if str(item).strip()],
            )
            feasibility = FeasibilityAssessment(
                summary=str(payload.get("feasibilitySummary") or payload.get("summary") or ""),
                feasibilityScore=float(payload.get("feasibilityScore") or 0.0),
                isFeasible=bool(payload.get("isFeasible")),
                blockers=[str(item) for item in payload.get("blockers", []) if str(item).strip()],
                assumptions=[str(item) for item in payload.get("assumptions", []) if str(item).strip()],
            )
            return {"novelty": novelty, "feasibility": feasibility}
        except Exception:
            return None

    @staticmethod
    def _extract_json(content: str) -> dict:
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
    def _title_variation_boost(title: str) -> float:
        return (sum(ord(ch) for ch in title[:24]) % 12) / 100

    @staticmethod
    def _evidence_snippets(evidences: list[Evidence]) -> str:
        return "\n".join(
            f"- {ev.metadata.title} | {ev.metadata.publishDate or '未知'}"
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
