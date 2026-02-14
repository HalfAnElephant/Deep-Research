from __future__ import annotations

import json

from app.core.database import get_connection
from app.core.utils import now_iso
from app.models.schemas import (
    ConversationDetail,
    ConversationMessage,
    ConversationStatus,
    ConversationSummary,
    MessageKind,
    MessageRole,
    PlanRevision,
    TaskConfig,
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
                (conversation_id, topic, status.value, config.model_dump_json(), None, ts, ts),
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
                        "raw": payload,
                    }
                )
                metadata["entries"] = entries[-50:]
                metadata["phase"] = phase
                metadata["state"] = state
                metadata["latestProgress"] = progress
                metadata["latestSummary"] = summary
                conn.execute(
                    """
                    UPDATE conversation_messages
                    SET content = ?, metadata_json = ?
                    WHERE message_id = ?
                    """,
                    (summary, json.dumps(metadata, ensure_ascii=False), row["message_id"]),
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
                        "raw": payload,
                    }
                ],
            },
            collapsed=True,
        )

    def get_detail(self, conversation_id: str) -> ConversationDetail:
        summary = self.get_summary(conversation_id)
        return ConversationDetail(
            conversationId=summary.conversationId,
            topic=summary.topic,
            status=summary.status,
            taskId=summary.taskId,
            createdAt=summary.createdAt,
            updatedAt=summary.updatedAt,
            currentPlan=self.get_current_plan(conversation_id),
            messages=self.list_messages(conversation_id),
        )
