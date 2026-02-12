from __future__ import annotations

from collections import defaultdict

from app.core.utils import new_id
from app.models.schemas import ConflictRecord, DisputedValue, Evidence, ResolutionStatus, SourceType


class AnalystService:
    SOURCE_WEIGHT: dict[SourceType, float] = {
        SourceType.PAPER: 1.0,
        SourceType.PATENT: 0.8,
        SourceType.WEB: 0.5,
        SourceType.MCP: 0.9,
    }

    def score(self, evidence: Evidence) -> float:
        base = self.SOURCE_WEIGHT[evidence.sourceType]
        impact_boost = min(1.5, 1 + (evidence.metadata.impactFactor / 10))
        peer_boost = 1.2 if evidence.metadata.isPeerReviewed else 1.0
        freshness = 1.0
        year = self._year_from_date(evidence.metadata.publishDate)
        if year <= 2016:
            freshness = 0.5
        elif year <= 2021:
            freshness = 0.8
        score = base * impact_boost * peer_boost * freshness * evidence.metadata.relevanceScore
        return round(min(1.0, score), 4)

    def detect_conflicts(self, task_id: str, evidences: list[Evidence], threshold: float = 0.15) -> list[ConflictRecord]:
        buckets: dict[str, list[tuple[Evidence, dict]]] = defaultdict(list)
        for ev in evidences:
            for value in ev.extractedData.numericalValues:
                unit, normalized = self.normalize_unit(value.get("unit", ""), float(value.get("value", 0)))
                context = value.get("context", "unknown")
                key = f"{context}:{unit}"
                buckets[key].append((ev, {"value": normalized, "unit": unit, "context": context}))

        conflicts: list[ConflictRecord] = []
        for key, items in buckets.items():
            if len(items) < 2:
                continue
            values = [it[1]["value"] for it in items]
            max_v = max(values)
            min_v = min(values)
            if max_v == 0:
                continue
            variance = (max_v - min_v) / max_v
            if variance <= threshold:
                continue
            disputed = [
                DisputedValue(
                    value=it[1]["value"],
                    unit=it[1]["unit"],
                    evidenceId=it[0].id,
                    source=it[0].url,
                )
                for it in items
            ]
            context = items[0][1]["context"]
            conflicts.append(
                ConflictRecord(
                    conflictId=new_id(),
                    taskId=task_id,
                    parameter=key,
                    disputedValues=disputed,
                    variance=round(variance, 4),
                    context=context,
                    resolutionStatus=ResolutionStatus.OPEN,
                )
            )
        return conflicts

    @staticmethod
    def normalize_unit(unit: str, value: float) -> tuple[str, float]:
        normalized = unit.lower().strip()
        if normalized == "km":
            return "m", value * 1000
        if normalized == "cm":
            return "m", value / 100
        if normalized == "gb":
            return "bytes", value * 1e9
        if normalized == "mb":
            return "bytes", value * 1e6
        return normalized or "unitless", value

    @staticmethod
    def _year_from_date(date_str: str) -> int:
        try:
            return int(date_str[:4])
        except ValueError:
            return 2026
