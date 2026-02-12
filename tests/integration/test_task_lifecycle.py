import time

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
