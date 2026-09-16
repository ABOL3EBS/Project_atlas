from pathlib import Path
from sqlite3 import connect
from uuid import uuid4

from app.services.document_store import utc_now


class ConversationStore:
    def __init__(self, db_path: str):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with connect(self._path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    knowledge_base_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_conversation "
                "ON messages(conversation_id, created_at)"
            )

    def ensure_conversation(
        self, knowledge_base_id: str, conversation_id: str | None = None
    ) -> str:
        if conversation_id:
            with connect(self._path) as connection:
                row = connection.execute(
                    "SELECT id FROM conversations WHERE id = ? AND knowledge_base_id = ?",
                    (conversation_id, knowledge_base_id),
                ).fetchone()
            if row:
                return conversation_id
            conversation_id = None
        conversation_id = conversation_id or str(uuid4())
        with connect(self._path) as connection:
            connection.execute(
                "INSERT INTO conversations (id, knowledge_base_id, created_at) VALUES (?, ?, ?)",
                (conversation_id, knowledge_base_id, utc_now()),
            )
        return conversation_id

    def append_message(self, conversation_id: str, role: str, content: str) -> dict:
        message_id = str(uuid4())
        created_at = utc_now()
        with connect(self._path) as connection:
            connection.execute(
                "INSERT INTO messages (id, conversation_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (message_id, conversation_id, role, content, created_at),
            )
        return {
            "id": message_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "created_at": created_at,
        }

    def list_messages(self, conversation_id: str, limit: int = 200) -> list[dict]:
        with connect(self._path) as connection:
            rows = connection.execute(
                "SELECT id, role, content, created_at FROM messages "
                "WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
        messages = [
            {
                "id": row[0],
                "role": row[1],
                "content": row[2],
                "created_at": row[3],
            }
            for row in rows
        ]
        messages.reverse()
        return messages

    def list_conversations(self, knowledge_base_id: str) -> list[dict]:
        with connect(self._path) as connection:
            rows = connection.execute(
                "SELECT id, knowledge_base_id, created_at FROM conversations "
                "WHERE knowledge_base_id = ? ORDER BY created_at DESC",
                (knowledge_base_id,),
            ).fetchall()
        conversations = []
        for row in rows:
            conversation_id = row[0]
            with connect(self._path) as connection:
                message = connection.execute(
                    "SELECT role, content, created_at FROM messages "
                    "WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 1",
                    (conversation_id,),
                ).fetchone()
                count = connection.execute(
                    "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()[0]
            conversations.append(
                {
                    "id": conversation_id,
                    "knowledge_base_id": row[1],
                    "created_at": row[2],
                    "message_count": count,
                    "last_message": message[1] if message else None,
                    "last_role": message[0] if message else None,
                }
            )
        return conversations

    def get_conversation(self, knowledge_base_id: str, conversation_id: str) -> dict | None:
        with connect(self._path) as connection:
            row = connection.execute(
                "SELECT id, knowledge_base_id, created_at FROM conversations "
                "WHERE id = ? AND knowledge_base_id = ?",
                (conversation_id, knowledge_base_id),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "knowledge_base_id": row[1],
            "created_at": row[2],
        }