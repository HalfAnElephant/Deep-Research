from __future__ import annotations

from dataclasses import dataclass, field

from app.models.schemas import TaskNode


@dataclass
class BranchScorer:
    """Compute a stable branch score so scheduler can rank candidates."""

    info_gain_weight: float = 0.6
    evidence_weight: float = 0.4

    def score(self, node: TaskNode, evidence_count: int = 0) -> float:
        info_gain = max(0.0, min(1.0, float(node.metadata.infoGainScore)))
        normalized_evidence = max(0.0, min(1.0, evidence_count / 5.0))
        total = (self.info_gain_weight * info_gain) + \
            (self.evidence_weight * normalized_evidence)
        return max(0.0, min(1.0, total))


@dataclass
class BestFirstSearchStrategy:
    """Prioritize high-score and shallow-depth nodes first."""

    scorer: BranchScorer = field(default_factory=BranchScorer)

    def order(self, nodes: list[TaskNode]) -> list[TaskNode]:
        return sorted(
            nodes,
            key=lambda n: (
                -max(0.0, min(1.0, float(n.metadata.branchScore))),
                -max(0.0, min(1.0, float(n.metadata.infoGainScore))),
                n.metadata.searchDepth,
                n.priority,
            ),
        )
