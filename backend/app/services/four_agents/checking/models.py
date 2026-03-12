"""Data models for the checking agent."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CheckIssue:
    """检查发现的问题。"""
    severity: str  # "critical", "major", "minor"
    description: str
    location: str | None = None
    suggestion: str | None = None
