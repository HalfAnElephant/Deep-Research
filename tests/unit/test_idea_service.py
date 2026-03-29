from __future__ import annotations

from app.models.schemas import ResearchMode, TaskConfig
from app.services.idea_service import IdeaService


def test_idea_service_generates_structured_fallback_ideas() -> None:
    service = IdeaService()
    ideas, evidences = service.generate_ideas(
        topic="AI Agent 代码评审提效研究",
        config=TaskConfig(
            researchMode=ResearchMode.EXPERIMENTAL_RESEARCH,
            numInitialIdeas=3,
            numReflections=2,
        ),
    )

    assert evidences == []
    assert len(ideas) == 3
    assert all(idea.title for idea in ideas)
    assert all(idea.problemStatement for idea in ideas)
    assert all(idea.experimentProposals for idea in ideas)
    assert all(idea.riskFactors for idea in ideas)
    assert all(idea.status.value == "CANDIDATE" for idea in ideas)

