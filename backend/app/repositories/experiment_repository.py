from __future__ import annotations

import json

from app.core.database import get_connection
from app.models.schemas import ExperimentArtifact, ExperimentMetric, ExperimentRun, ExperimentRunStatus


class ExperimentRepository:
    def create_run(self, run: ExperimentRun) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO experiment_runs(
                  run_id, task_id, branch_id, node_id, status,
                  objective, stdout, stderr, exit_code,
                  metrics_json, started_at, completed_at, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.runId,
                    run.taskId,
                    run.branchId,
                    run.nodeId,
                    run.status.value,
                    run.objective,
                    run.stdout,
                    run.stderr,
                    run.exitCode,
                    json.dumps([metric.model_dump() for metric in run.metrics]),
                    run.startedAt,
                    run.completedAt,
                    run.startedAt,
                ),
            )
            for artifact in run.artifacts:
                conn.execute(
                    """
                    INSERT INTO experiment_artifacts(
                      artifact_id, run_id, task_id, branch_id, node_id,
                      artifact_type, path, summary, created_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact.artifactId,
                        artifact.runId,
                        artifact.taskId,
                        artifact.branchId,
                        artifact.nodeId,
                        artifact.artifactType,
                        artifact.path,
                        artifact.summary,
                        artifact.createdAt,
                    ),
                )
            conn.commit()

    def list_runs(self, task_id: str) -> list[ExperimentRun]:
        with get_connection() as conn:
            runs = conn.execute(
                "SELECT * FROM experiment_runs WHERE task_id = ? ORDER BY started_at ASC",
                (task_id,),
            ).fetchall()
            artifact_rows = conn.execute(
                "SELECT * FROM experiment_artifacts WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            ).fetchall()

        artifacts_by_run: dict[str, list[ExperimentArtifact]] = {}
        for row in artifact_rows:
            artifact = ExperimentArtifact(
                artifactId=row["artifact_id"],
                runId=row["run_id"],
                taskId=row["task_id"],
                branchId=row["branch_id"],
                nodeId=row["node_id"],
                artifactType=row["artifact_type"],
                path=row["path"],
                summary=row["summary"],
                createdAt=row["created_at"],
            )
            artifacts_by_run.setdefault(artifact.runId, []).append(artifact)

        output: list[ExperimentRun] = []
        for row in runs:
            metrics_payload = json.loads(row["metrics_json"])
            metrics = [ExperimentMetric.model_validate(item) for item in metrics_payload]
            run = ExperimentRun(
                runId=row["run_id"],
                taskId=row["task_id"],
                branchId=row["branch_id"],
                nodeId=row["node_id"],
                status=ExperimentRunStatus(row["status"]),
                objective=row["objective"],
                stdout=row["stdout"],
                stderr=row["stderr"],
                exitCode=row["exit_code"],
                metrics=metrics,
                artifacts=artifacts_by_run.get(row["run_id"], []),
                startedAt=row["started_at"],
                completedAt=row["completed_at"],
            )
            output.append(run)
        return output
