"""Checking agent package - exports the main CheckingAgent class."""

from __future__ import annotations

from .agent import CheckingAgent
from .models import CheckIssue

__all__ = ["CheckingAgent", "CheckIssue"]
