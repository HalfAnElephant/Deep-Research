#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

# Force real-provider path unless user explicitly overrides it.
os.environ.setdefault("DR_USE_MOCK_SOURCES", "false")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.main import app


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one real Deep Research case and generate a report.")
    parser.add_argument(
        "--title",
        default="2026年AI Agent在软件工程中的应用现状与挑战",
        help="Research title",
    )
    parser.add_argument(
        "--description",
        default="基于公开资料，分析AI Agent在代码生成、测试自动化与工程协同中的进展、风险与落地策略。",
        help="Research description",
    )
    parser.add_argument("--sources", default="tavily", help="Comma-separated sources, e.g. tavily,serper")
    parser.add_argument("--timeout", type=int, default=120, help="Max seconds to wait for task completion")
    args = parser.parse_args()

    with TestClient(app) as client:
        payload = {
            "title": args.title,
            "description": args.description,
            "config": {
                "maxDepth": 2,
                "maxNodes": 12,
                "searchSources": [s.strip() for s in args.sources.split(",") if s.strip()],
                "priority": 4,
            },
        }
        create_resp = client.post("/api/v1/tasks", json=payload)
        create_resp.raise_for_status()
        task_id = create_resp.json()["taskId"]
        start_resp = client.post(f"/api/v1/tasks/{task_id}/start")
        start_resp.raise_for_status()

        deadline = time.time() + args.timeout
        final_status = ""
        while time.time() < deadline:
            task = client.get(f"/api/v1/tasks/{task_id}").json()
            final_status = task["status"]
            if final_status in {"COMPLETED", "FAILED", "ABORTED"}:
                break
            time.sleep(0.5)

        evidence_resp = client.get("/api/v1/evidence", params={"taskId": task_id})
        evidence_resp.raise_for_status()
        evidence_total = evidence_resp.json().get("total", 0)

        print(f"task_id={task_id}")
        print(f"final_status={final_status}")
        print(f"evidence_total={evidence_total}")

        if final_status != "COMPLETED":
            return 2

        report_resp = client.get(f"/api/v1/tasks/{task_id}/report")
        report_resp.raise_for_status()
        report_content = report_resp.json()["content"]

        report_path = Path(f"backend/.data/reports/{task_id}.md")
        print(f"report_path={report_path}")
        print("report_preview:")
        print("-" * 60)
        print("\n".join(report_content.splitlines()[:30]))
        print("-" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
