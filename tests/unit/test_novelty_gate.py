from __future__ import annotations

from app.core.utils import new_id
from app.models.schemas import (
    ExperimentProposal,
    RelatedWorkItem,
    ResearchIdea,
    RiskAssessment,
)
from app.services.novelty_gate import NoveltyGateService


def _build_idea(title: str) -> ResearchIdea:
    return ResearchIdea(
        ideaId=new_id(),
        title=title,
        problemStatement=f"围绕 {title} 的问题定义",
        shortHypothesis=f"{title} 能带来更好的研究入口",
        abstract=f"{title} 的摘要",
        relatedWork=[RelatedWorkItem(title=f"{title} 相关工作", summary="已有工作线索")],
        differentiators=["差异点一", "差异点二"],
        experimentProposals=[
            ExperimentProposal(
                title=f"{title} 验证方案",
                objective="验证核心假设",
                method="对比研究",
                metrics=["准确率", "覆盖度"],
                expectedOutcome="得到可用结论",
            )
        ],
        riskFactors=[RiskAssessment(risk="与已有工作重叠", severity="medium", mitigation="补充 novelty check")],
        limitations=["首轮证据有限"],
        sourceEvidenceIds=[new_id(), new_id()],
    )


def test_novelty_gate_selects_single_best_idea() -> None:
    gate = NoveltyGateService()
    ideas = gate.evaluate_ideas(
        topic="AI Agent 代码评审提效研究",
        ideas=[_build_idea("方案 A"), _build_idea("方案 B"), _build_idea("方案 C")],
        evidences=[],
        enforce_thresholds=True,
    )

    assert len(ideas) == 3
    selected = [idea for idea in ideas if idea.status.value == "SELECTED"]
    assert len(selected) == 1
    assert all(0 <= idea.scoreCard.overallScore <= 1 for idea in ideas)
    assert all(0 <= idea.noveltyAssessment.noveltyScore <= 1 for idea in ideas)
    assert all(0 <= idea.feasibilityAssessment.feasibilityScore <= 1 for idea in ideas)

