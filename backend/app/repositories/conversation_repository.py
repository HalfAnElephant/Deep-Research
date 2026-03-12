from __future__ import annotations

import json

from app.core.database import get_connection
from app.core.utils import now_iso
from app.models.schemas import (
    AgentStateRecord,
    AgentStatus,
    AgentType,
    ConversationDetail,
    ConversationMessage,
    ConversationStatus,
    ConversationSummary,
    MessageKind,
    MessageRole,
    PlanRevision,
    TaskConfig,
)


_AGENT_ORDER: tuple[AgentType, ...] = (
    AgentType.IDEATION,
    AgentType.PLANNING,
    AgentType.WRITING,
    AgentType.CHECKING,
)


class ConversationRepository:
    def create_conversation(
        self,
        *,
        conversation_id: str,
        topic: str,
        status: ConversationStatus,
        config: TaskConfig,
    ) -> ConversationSummary:
        ts = now_iso()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO conversations(
                  conversation_id, topic, status, config_json, task_id, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (conversation_id, topic, status.value,
                 config.model_dump_json(), None, ts, ts),
            )
            conn.commit()
        return self.get_summary(conversation_id)

    def get_summary(self, conversation_id: str) -> ConversationSummary:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        if row is None:
            raise KeyError(conversation_id)
        return ConversationSummary(
            conversationId=row["conversation_id"],
            topic=row["topic"],
            status=ConversationStatus(row["status"]),
            taskId=row["task_id"],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )

    def list_summaries(self) -> list[ConversationSummary]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM conversations
                ORDER BY updated_at DESC, created_at DESC
                """
            ).fetchall()
        return [
            ConversationSummary(
                conversationId=row["conversation_id"],
                topic=row["topic"],
                status=ConversationStatus(row["status"]),
                taskId=row["task_id"],
                createdAt=row["created_at"],
                updatedAt=row["updated_at"],
            )
            for row in rows
        ]

    def get_config(self, conversation_id: str) -> TaskConfig:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT config_json FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        if row is None:
            raise KeyError(conversation_id)
        return TaskConfig.model_validate_json(row["config_json"])

    def set_status(self, conversation_id: str, status: ConversationStatus) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE conversations
                SET status = ?, updated_at = ?
                WHERE conversation_id = ?
                """,
                (status.value, now_iso(), conversation_id),
            )
            conn.commit()
            if conn.total_changes == 0:
                raise KeyError(conversation_id)

    def set_task_id(self, conversation_id: str, task_id: str) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE conversations
                SET task_id = ?, updated_at = ?
                WHERE conversation_id = ?
                """,
                (task_id, now_iso(), conversation_id),
            )
            conn.commit()
            if conn.total_changes == 0:
                raise KeyError(conversation_id)

    def find_by_task_id(self, task_id: str) -> ConversationSummary | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT conversation_id FROM conversations WHERE task_id = ? LIMIT 1",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return self.get_summary(row["conversation_id"])

    def update_topic(self, conversation_id: str, topic: str) -> ConversationSummary:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE conversations
                SET topic = ?, updated_at = ?
                WHERE conversation_id = ?
                """,
                (topic, now_iso(), conversation_id),
            )
            conn.commit()
            if conn.total_changes == 0:
                raise KeyError(conversation_id)
        return self.get_summary(conversation_id)

    def delete_conversation(self, conversation_id: str) -> None:
        self.get_summary(conversation_id)
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            conn.execute(
                "DELETE FROM plan_revisions WHERE conversation_id = ?",
                (conversation_id,),
            )
            conn.execute(
                "DELETE FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            )
            conn.commit()

    def delete_all_conversations(self) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM conversations").fetchone()
            deleted_count = int(row["count"]) if row else 0
            conn.execute("DELETE FROM conversation_messages")
            conn.execute("DELETE FROM plan_revisions")
            conn.execute("DELETE FROM conversations")
            conn.commit()
        return deleted_count

    def add_plan_revision(self, conversation_id: str, *, author: MessageRole, markdown: str) -> PlanRevision:
        self.get_summary(conversation_id)
        ts = now_iso()
        with get_connection() as conn:
            existing = conn.execute(
                """
                SELECT COALESCE(MAX(version), 0) AS max_version
                FROM plan_revisions
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()
            max_version = int(existing["max_version"]) if existing else 0
            next_version = max_version + 1
            conn.execute(
                """
                INSERT INTO plan_revisions(conversation_id, version, author, markdown, created_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (conversation_id, next_version, author.value, markdown, ts),
            )
            conn.execute(
                """
                UPDATE conversations
                SET updated_at = ?
                WHERE conversation_id = ?
                """,
                (ts, conversation_id),
            )
            conn.commit()
        return self.get_plan_revision(conversation_id, next_version)

    def get_plan_revision(self, conversation_id: str, version: int) -> PlanRevision:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM plan_revisions
                WHERE conversation_id = ? AND version = ?
                """,
                (conversation_id, version),
            ).fetchone()
        if row is None:
            raise KeyError(f"{conversation_id}:{version}")
        return PlanRevision(
            conversationId=row["conversation_id"],
            version=row["version"],
            author=MessageRole(row["author"]),
            markdown=row["markdown"],
            createdAt=row["created_at"],
        )

    def get_current_plan(self, conversation_id: str) -> PlanRevision | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM plan_revisions
                WHERE conversation_id = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (conversation_id,),
            ).fetchone()
        if row is None:
            return None
        return PlanRevision(
            conversationId=row["conversation_id"],
            version=row["version"],
            author=MessageRole(row["author"]),
            markdown=row["markdown"],
            createdAt=row["created_at"],
        )

    def add_message(
        self,
        conversation_id: str,
        *,
        message_id: str,
        role: MessageRole,
        kind: MessageKind,
        content: str,
        metadata: dict | None = None,
        collapsed: bool = False,
    ) -> ConversationMessage:
        self.get_summary(conversation_id)
        ts = now_iso()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO conversation_messages(
                  message_id, conversation_id, role, kind, content, metadata_json, collapsed, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    role.value,
                    kind.value,
                    content,
                    metadata_json,
                    1 if collapsed else 0,
                    ts,
                ),
            )
            conn.execute(
                """
                UPDATE conversations
                SET updated_at = ?
                WHERE conversation_id = ?
                """,
                (ts, conversation_id),
            )
            conn.commit()
        return self.get_message(message_id)

    def get_message(self, message_id: str) -> ConversationMessage:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM conversation_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        if row is None:
            raise KeyError(message_id)
        return ConversationMessage(
            messageId=row["message_id"],
            conversationId=row["conversation_id"],
            role=MessageRole(row["role"]),
            kind=MessageKind(row["kind"]),
            content=row["content"],
            metadata=json.loads(row["metadata_json"]),
            collapsed=bool(row["collapsed"]),
            createdAt=row["created_at"],
        )

    def list_messages(self, conversation_id: str, *, limit: int = 300) -> list[ConversationMessage]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
        return [
            ConversationMessage(
                messageId=row["message_id"],
                conversationId=row["conversation_id"],
                role=MessageRole(row["role"]),
                kind=MessageKind(row["kind"]),
                content=row["content"],
                metadata=json.loads(row["metadata_json"]),
                collapsed=bool(row["collapsed"]),
                createdAt=row["created_at"],
            )
            for row in rows
        ]

    def append_progress_entry(
        self,
        conversation_id: str,
        *,
        task_id: str,
        message_id: str,
        phase: str,
        state: str,
        summary: str,
        progress: int | None,
        payload: dict,
    ) -> ConversationMessage:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM conversation_messages
                WHERE conversation_id = ? AND kind = ?
                ORDER BY created_at DESC
                LIMIT 8
                """,
                (conversation_id, MessageKind.PROGRESS_GROUP.value),
            ).fetchall()

            for row in rows:
                metadata = json.loads(row["metadata_json"])
                metadata_task_id = str(metadata.get("taskId", "")).strip()
                if not metadata_task_id:
                    raw_entries = metadata.get("entries")
                    if isinstance(raw_entries, list):
                        for entry in reversed(raw_entries):
                            if not isinstance(entry, dict):
                                continue
                            raw = entry.get("raw")
                            if not isinstance(raw, dict):
                                continue
                            raw_task_id = raw.get("taskId")
                            if isinstance(raw_task_id, str) and raw_task_id.strip():
                                metadata_task_id = raw_task_id.strip()
                                break
                if metadata_task_id != task_id:
                    continue
                if str(metadata.get("phase", "")).strip() != phase:
                    continue
                entries = metadata.get("entries")
                if not isinstance(entries, list):
                    entries = []
                entries.append(
                    {
                        "summary": summary,
                        "state": state,
                        "phase": phase,
                        "progress": progress,
                        "detail": str(payload.get("detail") or "").strip() if isinstance(payload, dict) else "",
                        "raw": payload,
                    }
                )
                metadata["entries"] = entries[-50:]
                metadata["phase"] = phase
                metadata["state"] = state
                metadata["latestProgress"] = progress
                metadata["latestSummary"] = summary
                metadata["taskId"] = task_id
                conn.execute(
                    """
                    UPDATE conversation_messages
                    SET content = ?, metadata_json = ?
                    WHERE message_id = ?
                    """,
                    (summary, json.dumps(metadata,
                     ensure_ascii=False), row["message_id"]),
                )
                conn.execute(
                    """
                    UPDATE conversations
                    SET updated_at = ?
                    WHERE conversation_id = ?
                    """,
                    (now_iso(), conversation_id),
                )
                conn.commit()
                return self.get_message(row["message_id"])

        return self.add_message(
            conversation_id,
            message_id=message_id,
            role=MessageRole.SYSTEM,
            kind=MessageKind.PROGRESS_GROUP,
            content=summary,
            metadata={
                "taskId": task_id,
                "phase": phase,
                "state": state,
                "latestProgress": progress,
                "latestSummary": summary,
                "entries": [
                    {
                        "summary": summary,
                        "state": state,
                        "phase": phase,
                        "progress": progress,
                        "detail": str(payload.get("detail") or "").strip() if isinstance(payload, dict) else "",
                        "raw": payload,
                    }
                ],
            },
            collapsed=True,
        )

    def _default_agent_states(self) -> list[AgentStateRecord]:
        return [
            AgentStateRecord(
                agentType=agent_type,
                status=AgentStatus.IDLE,
                progress=0,
                currentActivity="等待任务开始",
            )
            for agent_type in _AGENT_ORDER
        ]

    def _phase_to_agent_type(self, phase: str) -> AgentType:
        phase_upper = phase.upper()
        if any(token in phase_upper for token in ("CHECK", "REVIEW")):
            return AgentType.CHECKING
        if any(token in phase_upper for token in ("WRIT", "SYNTH", "FINAL", "PERSIST", "MATERIAL")):
            return AgentType.WRITING
        if any(token in phase_upper for token in ("PLAN", "BUILD")):
            return AgentType.PLANNING
        return AgentType.IDEATION

    def _normalize_agent_status(self, raw: str) -> AgentStatus:
        value = (raw or "").upper().strip()
        if "FAIL" in value or "ERROR" in value or "ABORT" in value:
            return AgentStatus.FAILED
        if value in {"COMPLETED", "DONE", "SUCCESS", "PASSED", "REVIEW_PASSED"}:
            return AgentStatus.COMPLETED
        if value in {
            "RUNNING",
            "EXECUTING",
            "PLANNING",
            "REVIEWING",
            "SYNTHESIZING",
            "FINALIZING",
            "REPORT_REVISING",
        }:
            return AgentStatus.RUNNING
        return AgentStatus.IDLE

    def _clamp_progress(self, value: object, *, fallback: int = 0) -> int:
        if isinstance(value, float):
            value = int(value)
        if isinstance(value, int):
            return max(0, min(100, value))
        return fallback

    def _derive_agent_states_from_messages(self, messages: list[ConversationMessage]) -> list[AgentStateRecord]:
        states = {
            record.agentType: record for record in self._default_agent_states()}
        order_index = {agent_type: idx for idx,
                       agent_type in enumerate(_AGENT_ORDER)}

        for message in messages:
            if message.kind != MessageKind.PROGRESS_GROUP:
                continue
            metadata = message.metadata if isinstance(
                message.metadata, dict) else {}
            raw_entries = metadata.get("entries")
            entries = raw_entries if isinstance(
                raw_entries, list) else [metadata]
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                raw_payload = entry.get("raw")
                payload = raw_payload if isinstance(raw_payload, dict) else {}

                raw_agent_type = payload.get("agentType")
                if isinstance(raw_agent_type, str) and raw_agent_type.strip() in AgentType.__members__:
                    agent_type = AgentType[raw_agent_type.strip()]
                elif isinstance(raw_agent_type, str) and raw_agent_type.strip() in {a.value for a in _AGENT_ORDER}:
                    agent_type = AgentType(raw_agent_type.strip())
                else:
                    phase = str(entry.get("phase")
                                or payload.get("phase") or "")
                    if not phase:
                        continue
                    if phase.upper() in {"HEARTBEAT", "STALL_WARNING"}:
                        phase = str(payload.get("currentPhase")
                                    or payload.get("phase") or phase)
                    agent_type = self._phase_to_agent_type(phase)

                status_raw = str(entry.get("state") or payload.get(
                    "status") or payload.get("state") or "")
                status = self._normalize_agent_status(status_raw)
                progress = self._clamp_progress(
                    entry.get("progress"), fallback=states[agent_type].progress)
                detail = str(entry.get("detail") or payload.get(
                    "currentActivity") or payload.get("detail") or message.content or "").strip()
                timestamp = message.createdAt

                current = states[agent_type]
                current.status = status
                current.progress = progress
                current.currentActivity = detail or current.currentActivity or "处理中"
                if status == AgentStatus.RUNNING and not current.startedAt:
                    current.startedAt = timestamp
                if status == AgentStatus.COMPLETED:
                    current.progress = 100
                    current.completedAt = timestamp
                    current.currentActivity = "阶段完成"
                if status == AgentStatus.FAILED:
                    current.error = detail or "执行失败"

                current_index = order_index[agent_type]
                if status in {AgentStatus.RUNNING, AgentStatus.COMPLETED}:
                    for prior_type in _AGENT_ORDER[:current_index]:
                        prior = states[prior_type]
                        if prior.status != AgentStatus.FAILED:
                            prior.status = AgentStatus.COMPLETED
                            prior.progress = 100
                            prior.currentActivity = "阶段完成"
                            if not prior.completedAt:
                                prior.completedAt = timestamp

        return [states[agent_type] for agent_type in _AGENT_ORDER]

    def get_detail(self, conversation_id: str) -> ConversationDetail:
        summary = self.get_summary(conversation_id)
        messages = self.list_messages(conversation_id)
        return ConversationDetail(
            conversationId=summary.conversationId,
            topic=summary.topic,
            status=summary.status,
            taskId=summary.taskId,
            createdAt=summary.createdAt,
            updatedAt=summary.updatedAt,
            currentPlan=self.get_current_plan(conversation_id),
            messages=messages,
            agentStates=self._derive_agent_states_from_messages(messages),
        )
