import time

from fastapi.testclient import TestClient

from app.main import app


def test_conversation_plan_run_and_download() -> None:
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/v1/conversations",
            json={
                "topic": "AI Agent 代码评审提效研究",
                "config": {
                    "maxDepth": 2,
                    "maxNodes": 8,
                    "searchSources": ["arXiv"],
                    "priority": 4,
                },
            },
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        conversation_id = created["conversationId"]
        assert created["status"] == "PLAN_READY"
        assert created["currentPlan"]["version"] == 1

        updated_markdown = """---
title: 代码评审提效研究
topic: AI Agent 代码评审提效研究
max_depth: 2
max_nodes: 8
priority: 4
search_sources: [arXiv]
---

## 研究目标
验证 AI Agent 在代码评审中的收益与风险。
"""
        update_resp = client.put(
            f"/api/v1/conversations/{conversation_id}/plan",
            json={"markdown": updated_markdown},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["version"] == 2

        detail_resp = client.get(f"/api/v1/conversations/{conversation_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["currentPlan"]["version"] == 2
        assert "代码评审提效研究" in detail_resp.json()["currentPlan"]["markdown"]

        run_resp = client.post(f"/api/v1/conversations/{conversation_id}/run", json={})
        assert run_resp.status_code == 200
        assert run_resp.json()["status"] == "RUNNING"

        deadline = time.time() + 6
        final_status = ""
        final_payload = {}
        while time.time() < deadline:
            payload = client.get(f"/api/v1/conversations/{conversation_id}").json()
            final_status = payload["status"]
            final_payload = payload
            if final_status in {"COMPLETED", "FAILED"}:
                break
            time.sleep(0.2)

        assert final_status == "COMPLETED"
        assert final_payload["taskId"]

        download_resp = client.get(f"/api/v1/conversations/{conversation_id}/report/download")
        assert download_resp.status_code == 200
        assert "text/markdown" in download_resp.headers.get("content-type", "")
        assert "代码评审提效研究" in download_resp.text
