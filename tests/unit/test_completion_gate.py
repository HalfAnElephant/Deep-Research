from app.models.schemas import ResearchScoreCard, TaskConfig, ResearchMode
from app.services.execution_engine import _build_scorecard, _validate_completion


def test_build_scorecard_contains_phase_b_dimensions() -> None:
    score = _build_scorecard(
        evidence_count=6,
        conflict_count=1,
        review_passed=True,
        report_path="/tmp/report.md",
        completed_nodes=8,
        total_nodes=10,
    )
    assert score.executionSuccessScore > 0
    assert score.reviewScore > 0
    assert 0 <= score.overallScore <= 1


def test_completion_gate_blocks_missing_peer_review_for_paper_mode() -> None:
    config = TaskConfig(researchMode=ResearchMode.PAPER_WRITEUP)
    score = ResearchScoreCard(
        noveltyScore=0.8,
        feasibilityScore=0.8,
        evidenceStrengthScore=0.8,
        executionSuccessScore=0.9,
        writeupReadinessScore=0.9,
        reviewScore=0.4,
        overallScore=0.75,
    )
    error = _validate_completion(
        deliverable_types=config.deliverableTypes,
        requires_experiment_loop=config.requiresExperimentLoop,
        requires_peer_review=config.requiresPeerReview,
        scorecard=score,
        report_path="/tmp/paper.md",
        review_passed=False,
    )
    assert error is not None
    assert "审稿" in error
