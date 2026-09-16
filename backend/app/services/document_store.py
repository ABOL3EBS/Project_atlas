from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from sqlite3 import connect
from uuid import uuid4


class DocumentStatus(StrEnum):
    INGESTING = "ingesting"
    INDEXED = "indexed"
    FAILED = "failed"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class DocumentStore:
    def __init__(self, db_path: str):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with connect(self._path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    knowledge_base_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    sha256 TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )

    def create(self, knowledge_base_id: str, name: str, size: int, sha256: str | None) -> str:
        document_id = str(uuid4())
        with connect(self._path) as connection:
            connection.execute(
                "INSERT INTO documents "
                "(id, knowledge_base_id, name, size, sha256, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    document_id,
                    knowledge_base_id,
                    name,
                    size,
                    sha256,
                    DocumentStatus.INGESTING.value,
                    utc_now(),
                ),
            )
        return document_id

    def mark_indexed(self, document_id: str, chunk_count: int) -> None:
        with connect(self._path) as connection:
            connection.execute(
                "UPDATE documents SET status = ?, chunk_count = ? WHERE id = ?",
                (DocumentStatus.INDEXED.value, chunk_count, document_id),
            )

    def mark_failed(self, document_id: str, error: str) -> None:
        with connect(self._path) as connection:
            connection.execute(
                "UPDATE documents SET status = ?, error = ? WHERE id = ?",
                (DocumentStatus.FAILED.value, error, document_id),
            )

    def list_knowledge_bases(self) -> list[dict]:
        with connect(self._path) as connection:
            rows = connection.execute(
                "SELECT knowledge_base_id, COUNT(*) AS document_count, "
                "COALESCE(SUM(chunk_count), 0) AS chunk_count, "
                "MIN(created_at) AS created_at "
                "FROM documents GROUP BY knowledge_base_id ORDER BY created_at",
            ).fetchall()
        return [
            {
                "knowledge_base_id": row[0],
                "document_count": row[1],
                "chunk_count": row[2],
                "created_at": row[3],
            }
            for row in rows
        ]

    def list(self, knowledge_base_id: str) -> list[dict]:
        with connect(self._path) as connection:
            rows = connection.execute(
                "SELECT id, knowledge_base_id, name, size, status, error, chunk_count, created_at "
                "FROM documents WHERE knowledge_base_id = ? ORDER BY created_at DESC",
                (knowledge_base_id,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get(self, knowledge_base_id: str, document_id: str) -> dict | None:
        with connect(self._path) as connection:
            row = connection.execute(
                "SELECT id, knowledge_base_id, name, size, status, error, chunk_count, created_at "
                "FROM documents WHERE id = ? AND knowledge_base_id = ?",
                (document_id, knowledge_base_id),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def find_existing(self, knowledge_base_id: str, sha256: str) -> dict | None:
        with connect(self._path) as connection:
            row = connection.execute(
                "SELECT id, knowledge_base_id, name, size, status, error, chunk_count, created_at "
                "FROM documents WHERE knowledge_base_id = ? AND sha256 = ? LIMIT 1",
                (knowledge_base_id, sha256),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def delete(self, knowledge_base_id: str, document_id: str) -> bool:
        with connect(self._path) as connection:
            cursor = connection.execute(
                "DELETE FROM documents WHERE id = ? AND knowledge_base_id = ?",
                (document_id, knowledge_base_id),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_dict(row: tuple) -> dict:
        columns = [
            "id",
            "knowledge_base_id",
            "name",
            "size",
            "status",
            "error",
            "chunk_count",
            "created_at",
        ]
        return dict(zip(columns, row, strict=True))