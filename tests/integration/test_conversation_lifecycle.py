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
        assert created["messages"][0]["role"] == "user"
        assert created["messages"][0]["content"] == "AI Agent 代码评审提效研究"

        rename_resp = client.patch(
            f"/api/v1/conversations/{conversation_id}",
            json={"topic": "AI Agent 代码评审提效研究（重命名）", "syncCurrentPlan": True},
        )
        assert rename_resp.status_code == 200
        renamed = rename_resp.json()
        assert renamed["topic"] == "AI Agent 代码评审提效研究（重命名）"
        assert "AI Agent 代码评审提效研究（重命名）" in renamed["currentPlan"]["markdown"]
        renamed_plan_version = renamed["currentPlan"]["version"]

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
        assert update_resp.json()["version"] == renamed_plan_version + 1

        detail_resp = client.get(f"/api/v1/conversations/{conversation_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["currentPlan"]["version"] == renamed_plan_version + 1
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
        first_task_id = final_payload["taskId"]
        assert first_task_id

        download_resp = client.get(f"/api/v1/conversations/{conversation_id}/report/download")
        assert download_resp.status_code == 200
        assert "text/markdown" in download_resp.headers.get("content-type", "")
        assert "代码评审提效研究" in download_resp.text

        rerun_resp = client.post(f"/api/v1/conversations/{conversation_id}/run", json={})
        assert rerun_resp.status_code == 200
        rerun_payload = rerun_resp.json()
        assert rerun_payload["status"] == "RUNNING"
        assert rerun_payload["taskId"] != first_task_id

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
        second_task_id = final_payload["taskId"]
        assert second_task_id == rerun_payload["taskId"]

        revise_resp = client.post(
            f"/api/v1/conversations/{conversation_id}/plan/revise",
            json={"instruction": "请补充局限性与后续工作章节"},
        )
        assert revise_resp.status_code == 200
        revised_payload = revise_resp.json()
        assert revised_payload["plan"]["version"] >= renamed_plan_version

        deadline = time.time() + 6
        detail_json = {}
        while time.time() < deadline:
            detail_after_revise = client.get(f"/api/v1/conversations/{conversation_id}")
            assert detail_after_revise.status_code == 200
            detail_json = detail_after_revise.json()
            if detail_json["status"] in {"COMPLETED", "FAILED"}:
                break
            time.sleep(0.2)

        assert detail_json["status"] == "COMPLETED"
        report_messages = [message for message in detail_json["messages"] if message["kind"] == "FINAL_REPORT"]
        assert len(report_messages) >= 3

        create_resp2 = client.post(
            "/api/v1/conversations",
            json={
                "topic": "第二个会话",
                "config": {
                    "maxDepth": 2,
                    "maxNodes": 8,
                    "searchSources": ["arXiv"],
                    "priority": 4,
                },
            },
        )
        assert create_resp2.status_code == 201

        bulk_delete_resp = client.delete("/api/v1/conversations")
        assert bulk_delete_resp.status_code == 200
        assert bulk_delete_resp.json()["deleted"] is True
        assert bulk_delete_resp.json()["deletedCount"] >= 2

        list_resp = client.get("/api/v1/conversations")
        assert list_resp.status_code == 200
        assert list_resp.json() == []
