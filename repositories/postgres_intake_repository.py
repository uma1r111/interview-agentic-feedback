# repositories/postgres_intake_repository.py
"""
PostgreSQL implementation of the intake repository.

Mirrors IntakeRepository (SQLite) exactly — same interface, same status
transitions (awaiting_files → ready → evaluated). Only the SQL dialect
and connection management differ.

SQL DIALECT DIFFERENCES FROM SQLITE
-------------------------------------
SQLite:  INSERT INTO ... (?,?,?)
Postgres: INSERT INTO ... (:name,:name,:name)

SQLite:  conn.execute("ALTER TABLE ... ADD COLUMN")  — migrations
Postgres: migrations handled via CREATE TABLE IF NOT EXISTS directly
          (Postgres column additions use the same ALTER TABLE syntax,
           but we avoid them here since init_schema() runs on a fresh DB)

SQLite:  conn.row_factory = sqlite3.Row  → dict(row)
Postgres: result._asdict()               → same dict shape
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from repositories.base import BaseRepository
from services.connection_manager import DatabaseManager

logger = logging.getLogger(__name__)

_REQUIRED_FILE_FIELDS = (
    "mcq_path",
    "programming_path",
    "cv_path",
    "session1_path",
    "session2_path",
)


class PostgresIntakeRepository(BaseRepository[Dict[str, Any]]):
    """
    PostgreSQL-backed intake repository.

    Uses the global DatabaseManager singleton — no direct connection
    management. All connection lifecycle is handled by the pool.
    """

    def __init__(self) -> None:
        self._db = DatabaseManager()

    # ──────────────────────────────────────────────────────────────────
    # Schema bootstrap
    # ──────────────────────────────────────────────────────────────────

    def init_schema(self) -> None:
        """Creates the candidate_intake table if absent. Safe to call on every startup."""
        with self._db.get_connection() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS candidate_intake (
                    candidate_id        TEXT PRIMARY KEY,
                    candidate_name      TEXT NOT NULL,
                    role_type           TEXT NOT NULL,
                    mcq_path            TEXT,
                    programming_path    TEXT,
                    cv_path             TEXT,
                    session1_path       TEXT,
                    session2_path       TEXT,
                    status              TEXT NOT NULL DEFAULT 'awaiting_files',
                    created_at          TEXT NOT NULL,
                    evaluated_at        TEXT
                )
            """))
        logger.info("PostgresIntakeRepository: schema verified.")

    # ──────────────────────────────────────────────────────────────────
    # BaseRepository interface
    # ──────────────────────────────────────────────────────────────────

    def get_by_id(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        with self._db.get_connection() as conn:
            row = conn.execute(
                text("SELECT * FROM candidate_intake WHERE candidate_id = :id"),
                {"id": candidate_id}
            ).fetchone()
        return row._asdict() if row else None

    def get_all(self) -> List[Dict[str, Any]]:
        with self._db.get_connection() as conn:
            rows = conn.execute(text("""
                SELECT candidate_id, candidate_name, role_type,
                       mcq_path, programming_path,
                       cv_path, session1_path, session2_path,
                       status, created_at, evaluated_at
                FROM candidate_intake
                ORDER BY created_at DESC
            """)).fetchall()
        return [row._asdict() for row in rows]

    def save(self, candidate_id: str, data: Dict[str, Any]) -> None:
        """Phase 1 registration — inserts a new intake stub and creates fixtures folder."""
        folder_path = os.path.join("fixtures", "candidates", candidate_id)
        os.makedirs(folder_path, exist_ok=True)

        created_at = datetime.now(timezone.utc).isoformat()

        with self._db.get_connection() as conn:
            conn.execute(text("""
                INSERT INTO candidate_intake
                    (candidate_id, candidate_name, role_type, status, created_at)
                VALUES
                    (:candidate_id, :candidate_name, :role_type, 'awaiting_files', :created_at)
            """), {
                "candidate_id":   candidate_id,
                "candidate_name": data["candidate_name"],
                "role_type":      data["role_type"],
                "created_at":     created_at,
            })

        logger.info(f"PostgresIntakeRepository: registered {candidate_id}")

    def delete(self, candidate_id: str) -> bool:
        with self._db.get_connection() as conn:
            result = conn.execute(
                text("DELETE FROM candidate_intake WHERE candidate_id = :id"),
                {"id": candidate_id}
            )
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"PostgresIntakeRepository: deleted {candidate_id}")
        return deleted

    def update(self, candidate_id: str, fields: Dict[str, Any]) -> bool:
        """
        Partial update — patches only supplied file path fields.
        Recalculates status to 'ready' when all 5 paths are present.
        """
        allowed = set(_REQUIRED_FILE_FIELDS)
        filtered = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not filtered:
            return False

        set_clauses = ", ".join(f"{col} = :{col}" for col in filtered)
        params = {**filtered, "candidate_id": candidate_id}

        with self._db.get_connection() as conn:
            conn.execute(
                text(f"UPDATE candidate_intake SET {set_clauses} WHERE candidate_id = :candidate_id"),
                params
            )

            row = conn.execute(
                text(f"SELECT {', '.join(_REQUIRED_FILE_FIELDS)} FROM candidate_intake WHERE candidate_id = :id"),
                {"id": candidate_id}
            ).fetchone()

            new_status = (
                "ready"
                if row and all(getattr(row, f, None) is not None for f in _REQUIRED_FILE_FIELDS)
                else "awaiting_files"
            )

            conn.execute(
                text("UPDATE candidate_intake SET status = :status WHERE candidate_id = :id"),
                {"status": new_status, "id": candidate_id}
            )

        logger.info(f"PostgresIntakeRepository: patched {candidate_id} | status={new_status}")
        return True

    # ──────────────────────────────────────────────────────────────────
    # Domain-specific operations
    # ──────────────────────────────────────────────────────────────────

    def mark_evaluated(self, candidate_id: str) -> None:
        """Transitions intake status to 'evaluated' after pipeline completes."""
        with self._db.get_connection() as conn:
            conn.execute(text("""
                UPDATE candidate_intake
                SET status = 'evaluated', evaluated_at = :evaluated_at
                WHERE candidate_id = :id
            """), {
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "id": candidate_id,
            })
        logger.info(f"PostgresIntakeRepository: marked {candidate_id} as evaluated")

    def find_by_name(self, candidate_name: str) -> List[Dict[str, Any]]:
        """Case-insensitive name lookup for duplicate detection."""
        with self._db.get_connection() as conn:
            rows = conn.execute(text("""
                SELECT candidate_id, candidate_name, role_type, status, created_at
                FROM candidate_intake
                WHERE LOWER(candidate_name) = LOWER(:name)
            """), {"name": candidate_name.strip()}).fetchall()
        return [row._asdict() for row in rows]
