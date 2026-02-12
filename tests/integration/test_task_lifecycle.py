import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_task_create_get_dag_and_start() -> None:
    with TestClient(app) as client:
        payload = {
            "title": "LLM hallucination study",
            "description": "Investigate causes and mitigations",
            "config": {"maxDepth": 2, "maxNodes": 8, "searchSources": ["arXiv"], "priority": 4},
        }
        create_resp = client.post("/api/v1/tasks", json=payload)
        assert create_resp.status_code == 201
        task_id = create_resp.json()["taskId"]

        get_resp = client.get(f"/api/v1/tasks/{task_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "READY"

        dag_resp = client.get(f"/api/v1/tasks/{task_id}/dag")
        assert dag_resp.status_code == 200
        assert dag_resp.json()["nodes"] == []

        start_resp = client.post(f"/api/v1/tasks/{task_id}/start")
        assert start_resp.status_code == 200

        # Give async engine time to generate evidences in background.
        time.sleep(1.0)
        evidence_resp = client.get("/api/v1/evidence", params={"taskId": task_id})
        assert evidence_resp.status_code == 200
        assert evidence_resp.json()["total"] >= 1

        deadline = time.time() + 4
        final_task = None
        while time.time() < deadline:
            final_task = client.get(f"/api/v1/tasks/{task_id}").json()
            if final_task["status"] in {"COMPLETED", "FAILED", "ABORTED"}:
                break
            time.sleep(0.2)
        assert final_task is not None
        assert final_task["status"] == "COMPLETED"
        assert final_task["reportPath"] is not None
        assert Path(final_task["reportPath"]).exists()

        conflicts_resp = client.get(f"/api/v1/tasks/{task_id}/conflicts")
        assert conflicts_resp.status_code == 200
        conflicts = conflicts_resp.json()
        if conflicts:
            conflict = conflicts[0]
            selected = conflict["disputedValues"][0]["evidenceId"]
            vote_resp = client.post(
                f"/api/v1/evidence/{selected}/vote",
                json={
                    "conflictId": conflict["conflictId"],
                    "selectedEvidenceId": selected,
                    "reason": "Choose highest relevance",
                },
            )
            assert vote_resp.status_code == 200

        mcp_read = client.post(
            "/api/v1/mcp/execute",
            json={"toolName": "python-executor", "method": "tools/call", "params": {"code": "1+1"}, "mode": "read"},
        )
        assert mcp_read.status_code == 200
        assert mcp_read.json()["status"] == "SUCCESS"

        mcp_write = client.post(
            "/api/v1/mcp/execute",
            json={
                "toolName": "filesystem",
                "method": "tools/write",
                "params": {"path": "/tmp/a.txt", "content": "x"},
                "mode": "write",
            },
        )
        assert mcp_write.status_code == 200
        assert mcp_write.json()["status"] == "USER_CONFIRMATION_REQUIRED"


def test_snapshot_and_recover_flow() -> None:
    with TestClient(app) as client:
        payload = {
            "title": "Recovery demo",
            "description": "Test pause and recover",
            "config": {"maxDepth": 2, "maxNodes": 8, "searchSources": ["arXiv"], "priority": 3},
        }
        task_id = client.post("/api/v1/tasks", json=payload).json()["taskId"]
        client.post(f"/api/v1/tasks/{task_id}/start")
        time.sleep(0.8)
        pause = client.post(f"/api/v1/tasks/{task_id}/pause")
        assert pause.status_code == 200

        snapshot = client.get(f"/api/v1/tasks/{task_id}/snapshot")
        assert snapshot.status_code == 200
        assert "completed_nodes" in snapshot.json()

        recover = client.post(f"/api/v1/tasks/{task_id}/recover")
        assert recover.status_code == 200
