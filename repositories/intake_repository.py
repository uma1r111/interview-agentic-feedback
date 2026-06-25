# repositories/intake_repository.py
"""
IntakeRepository

Handles the two-step candidate intake staging lifecycle:
  awaiting_files → ready → evaluated

WHAT MOVED HERE (from services/database.py):
  - create_candidate_intake()
  - update_candidate_intake_files()
  - mark_intake_evaluated()
  - delete_intake_candidate()
  - patch_intake_candidate()
  - get_all_intake_candidates()
  - find_intake_by_name()
  - get_intake_candidate()

WHY SEPARATE FROM CandidateRepository
--------------------------------------
The intake table is a staging area — a mutable, short-lived record that
tracks file upload progress. The candidates table is an immutable audit
record of completed evaluations. They have different consumers, different
mutation patterns, and may eventually live in different storage backends.
Keeping them in separate repositories honours the Single Responsibility
Principle at the persistence layer.
"""

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from repositories.base import BaseRepository

logger = logging.getLogger(__name__)

# Fields that must all be non-null for status to become 'ready'
_REQUIRED_FILE_FIELDS = (
    "mcq_path",
    "programming_path",
    "cv_path",
    "session1_path",
    "session2_path",
)


class IntakeRepository(BaseRepository[Dict[str, Any]]):
    """
    Concrete SQLite implementation of the intake repository.

    The `candidate_intake` table stores file paths and status.
    Status auto-recalculates whenever file paths are patched:
      - All 5 paths present  → 'ready'
      - Any path missing     → 'awaiting_files'
    """

    def __init__(self, db_path: str):
        self._db_path = db_path

    # ──────────────────────────────────────────────────────────────────
    # Connection management
    # ──────────────────────────────────────────────────────────────────

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # ──────────────────────────────────────────────────────────────────
    # Schema bootstrap
    # ──────────────────────────────────────────────────────────────────

    def init_schema(self) -> None:
        """
        Creates the `candidate_intake` table and applies any pending
        column migrations. Safe to call on every startup.
        """
        with self._connect() as conn:
            conn.execute("""
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
            """)

            # Migrations: add columns that may be missing from older DBs
            for migration_sql in [
                "ALTER TABLE candidate_intake ADD COLUMN mcq_path TEXT",
                "ALTER TABLE candidate_intake ADD COLUMN programming_path TEXT",
            ]:
                try:
                    conn.execute(migration_sql)
                    conn.commit()
                    logger.info(f"IntakeRepository: migration applied: {migration_sql[:60]}")
                except Exception:
                    pass  # Column already exists — safe to ignore

            # Repair stale 'ready' rows missing required file paths
            # (artefacts from pre-migration schema)
            repair = conn.execute("""
                UPDATE candidate_intake
                SET status = 'awaiting_files'
                WHERE status = 'ready'
                  AND (
                      mcq_path IS NULL OR programming_path IS NULL
                      OR cv_path IS NULL OR session1_path IS NULL
                      OR session2_path IS NULL
                  )
            """)
            conn.commit()
            if repair.rowcount > 0:
                logger.warning(
                    f"IntakeRepository: reset {repair.rowcount} stale 'ready' row(s) "
                    "to 'awaiting_files' (schema migration artefact)."
                )

        logger.info("IntakeRepository: schema verified.")

    # ──────────────────────────────────────────────────────────────────
    # BaseRepository interface implementation
    # ──────────────────────────────────────────────────────────────────

    def get_by_id(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """Returns the full intake record for a single candidate."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM candidate_intake WHERE candidate_id = ?",
                (candidate_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_all(self) -> List[Dict[str, Any]]:
        """Returns all intake rows ordered newest-first."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT candidate_id, candidate_name, role_type,
                       mcq_path, programming_path,
                       cv_path, session1_path, session2_path,
                       status, created_at, evaluated_at
                FROM candidate_intake
                ORDER BY created_at DESC
            """).fetchall()
        return [dict(row) for row in rows]

    def save(self, candidate_id: str, data: Dict[str, Any]) -> None:
        """
        Phase 1 registration — inserts a new intake stub.
        Also creates the candidate's fixtures folder on disk.
        """
        folder_path = os.path.join("fixtures", "candidates", candidate_id)
        os.makedirs(folder_path, exist_ok=True)
        logger.info(f"IntakeRepository: created folder {folder_path}")

        created_at = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO candidate_intake
                    (candidate_id, candidate_name, role_type, status, created_at)
                VALUES (?, ?, ?, 'awaiting_files', ?)
            """, (
                candidate_id,
                data["candidate_name"],
                data["role_type"],
                created_at,
            ))
            conn.commit()

        logger.info(
            f"IntakeRepository: registered {candidate_id} "
            f"({data['candidate_name']}, {data['role_type']})"
        )

    def delete(self, candidate_id: str) -> bool:
        """Hard-deletes the intake row. Caller is responsible for removing the folder."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM candidate_intake WHERE candidate_id = ?",
                (candidate_id,)
            )
            conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"IntakeRepository: deleted {candidate_id}")
        else:
            logger.warning(f"IntakeRepository: delete attempted, no row found: {candidate_id}")
        return deleted

    def update(self, candidate_id: str, fields: Dict[str, Any]) -> bool:
        """
        Partial update — patches only the supplied keyword fields.

        After patching, recalculates completeness status:
          - All 5 required paths non-null → status = 'ready'
          - Otherwise                     → status = 'awaiting_files'

        Allowed field names (must match DB column names):
          mcq_path, programming_path, cv_path, session1_path, session2_path
        """
        allowed = set(_REQUIRED_FILE_FIELDS)
        filtered = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not filtered:
            return False

        set_clauses = ", ".join(f"{col} = ?" for col in filtered)
        values = list(filtered.values()) + [candidate_id]

        with self._connect() as conn:
            conn.execute(
                f"UPDATE candidate_intake SET {set_clauses} WHERE candidate_id = ?",
                values
            )
            conn.commit()

            # Re-fetch to determine completeness
            row = conn.execute(
                f"SELECT {', '.join(_REQUIRED_FILE_FIELDS)} "
                f"FROM candidate_intake WHERE candidate_id = ?",
                (candidate_id,)
            ).fetchone()

            if row and all(row[f] is not None for f in _REQUIRED_FILE_FIELDS):
                new_status = "ready"
            else:
                new_status = "awaiting_files"

            conn.execute(
                "UPDATE candidate_intake SET status = ? WHERE candidate_id = ?",
                (new_status, candidate_id)
            )
            conn.commit()

        logger.info(
            f"IntakeRepository: patched {candidate_id} | "
            f"fields={list(filtered.keys())} | status={new_status}"
        )
        return True

    # ──────────────────────────────────────────────────────────────────
    # Domain-specific operations beyond the base interface
    # ──────────────────────────────────────────────────────────────────

    def mark_evaluated(self, candidate_id: str) -> None:
        """Transitions intake status to 'evaluated' after pipeline completes."""
        with self._connect() as conn:
            conn.execute("""
                UPDATE candidate_intake
                SET status = 'evaluated', evaluated_at = ?
                WHERE candidate_id = ?
            """, (datetime.now(timezone.utc).isoformat(), candidate_id))
            conn.commit()
        logger.info(f"IntakeRepository: marked {candidate_id} as evaluated")

    def find_by_name(self, candidate_name: str) -> List[Dict[str, Any]]:
        """
        Case-insensitive name lookup for duplicate detection.
        Used by the dashboard before Step 1 registration.
        """
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT candidate_id, candidate_name, role_type, status, created_at
                FROM candidate_intake
                WHERE LOWER(candidate_name) = LOWER(?)
            """, (candidate_name.strip(),)).fetchall()
        return [dict(row) for row in rows]