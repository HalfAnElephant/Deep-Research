from __future__ import annotations

from app.models.schemas import (
    ExperimentProposal,
    NoveltyAssessment,
    ResearchIdea,
    ResearchMode,
    TaskConfig,
)


def test_task_config_applies_research_mode_defaults() -> None:
    config = TaskConfig(researchMode=ResearchMode.EXPERIMENTAL_RESEARCH)
    assert config.requiresNoveltyCheck is True

    default_config = TaskConfig()
    assert default_config.researchMode == ResearchMode.EVIDENCE_REPORT
    assert default_config.requiresNoveltyCheck is False
    assert default_config.numReflections == 2
    assert default_config.numInitialIdeas == 3


def test_research_idea_related_models_validate() -> None:
    idea = ResearchIdea(
        ideaId="idea-1",
        title="结构化候选方案",
        problemStatement="验证结构化 idea 是否可用",
        shortHypothesis="结构化入口会提升后续研究质量",
        abstract="围绕结构化 idea 建立研究入口",
        noveltyAssessment=NoveltyAssessment(noveltyScore=0.7, isNovel=True),
        experimentProposals=[
            ExperimentProposal(
                title="验证实验",
                objective="检查结构化输出",
                method="构造最小样例",
                metrics=["完整率"],
                expectedOutcome="输出合法 idea",
            )
        ],
    )

    assert idea.title == "结构化候选方案"
    assert idea.noveltyAssessment.noveltyScore == 0.7
    assert idea.experimentProposals[0].title == "验证实验"
