# repositories/candidate_repository.py
"""
CandidateRepository

Single source of truth for ALL data access related to evaluated candidates
and their hiring decisions.

WHAT MOVED HERE (from services/database.py):
  - save_candidate()
  - get_candidate_report()
  - get_all_candidates()
  - update_hiring_decision()
  - get_decision_audit()

WHY THE SEPARATION FROM IntakeRepository
-----------------------------------------
Evaluated candidates (in the `candidates` table) have a fundamentally
different lifecycle and read pattern from intake candidates. They are
immutable once written (except for hiring_decision), and the primary
consumer is the dashboard read path. Keeping them separate lets us
optimise caching or even move them to a different store later without
touching intake logic.
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.bias import BiasLog
from models.enums import Decision
from models.evaluation import FeedbackReport
from repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class CandidateRepository(BaseRepository[FeedbackReport]):
    """
    Concrete SQLite implementation of the candidate repository.

    Constructor takes the DB path so it can be injected — this makes
    testing trivial (pass ":memory:") and makes Postgres migration a
    matter of swapping the connection factory, not rewriting queries.
    """

    def __init__(self, db_path: str):
        self._db_path = db_path

    # ──────────────────────────────────────────────────────────────────
    # Connection management
    # ──────────────────────────────────────────────────────────────────

    @contextmanager
    def _connect(self):
        """Yields a connected, row_factory-enabled SQLite connection."""
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
        Creates the `candidates` and `decision_audit` tables if absent.
        Safe to call on every startup.
        """
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id        TEXT PRIMARY KEY,
                    candidate_name      TEXT NOT NULL,
                    role_type           TEXT NOT NULL,
                    mcq_score           REAL NOT NULL,
                    ai_recommendation   TEXT,
                    hiring_decision     TEXT NOT NULL DEFAULT 'Hold',
                    evaluated_at        TEXT NOT NULL,
                    feedback_report     TEXT NOT NULL,
                    bias_log            TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_audit (
                    audit_id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id        TEXT NOT NULL,
                    previous_decision   TEXT,
                    new_decision        TEXT NOT NULL,
                    changed_at          TEXT NOT NULL,
                    changed_by          TEXT DEFAULT 'system',
                    FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id)
                )
            """)
            conn.commit()
        logger.info("CandidateRepository: schema verified.")

    # ──────────────────────────────────────────────────────────────────
    # BaseRepository interface implementation
    # ──────────────────────────────────────────────────────────────────

    def get_by_id(self, candidate_id: str) -> Optional[FeedbackReport]:
        """
        Returns the FeedbackReport for a candidate, with hiring_decision
        overridden by the authoritative DB column value at read time.

        This matters because the JSON blob stores the decision at the
        moment of evaluation — subsequent PATCH calls update the column
        but not the blob. Reading from the column keeps them in sync.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT feedback_report, hiring_decision FROM candidates WHERE candidate_id = ?",
                (candidate_id,)
            ).fetchone()

        if not row:
            return None

        report = FeedbackReport.model_validate_json(row["feedback_report"])
        report.hiring_manager_decision = Decision(row["hiring_decision"])
        return report

    def get_all(self) -> List[Dict[str, Any]]:
        """
        Returns lightweight summary rows for dashboard navigation.
        Does NOT deserialize the full feedback_report blob — that would
        be expensive and unnecessary for a list view.
        """
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT candidate_id, candidate_name, role_type, mcq_score,
                       ai_recommendation, hiring_decision, evaluated_at
                FROM candidates
                ORDER BY evaluated_at DESC
            """).fetchall()
        return [dict(row) for row in rows]

    def save(self, candidate_id: str, final_state: Dict[str, Any]) -> None:
        """
        Serializes and persists a completed evaluation.

        Uses INSERT OR REPLACE — re-evaluating the same candidate
        (same candidate_id) overwrites the previous record. This is
        intentional: if you re-run the pipeline for corrections, the
        latest result wins.

        Also seeds the audit trail with the initial 'Hold' decision.
        """
        feedback_report: Optional[FeedbackReport] = final_state.get("feedback_report")
        bias_log: Optional[BiasLog] = final_state.get("bias_log")

        feedback_report_json = feedback_report.model_dump_json() if feedback_report else None
        bias_log_json = bias_log.model_dump_json() if bias_log else None

        ai_recommendation = (
            feedback_report.ai_recommendation.value if feedback_report else None
        )
        hiring_decision = (
            feedback_report.hiring_manager_decision.value
            if feedback_report else "Hold"
        )

        role_type = final_state.get("role_type")
        role_type_str = role_type.value if hasattr(role_type, "value") else str(role_type)

        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO candidates
                    (candidate_id, candidate_name, role_type, mcq_score,
                     ai_recommendation, hiring_decision, evaluated_at,
                     feedback_report, bias_log)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                candidate_id,
                final_state.get("candidate_name"),
                role_type_str,
                final_state.get("mcq_score"),
                ai_recommendation,
                hiring_decision,
                now,
                feedback_report_json,
                bias_log_json,
            ))

            # Seed audit trail with the initial decision
            conn.execute("""
                INSERT INTO decision_audit
                    (candidate_id, previous_decision, new_decision, changed_at, changed_by)
                VALUES (?, ?, ?, ?, ?)
            """, (candidate_id, None, hiring_decision, now, "pipeline"))

            conn.commit()

        logger.info(f"CandidateRepository: saved candidate {candidate_id}")

    def delete(self, candidate_id: str) -> bool:
        """Hard delete. Not normally used for evaluated candidates."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM candidates WHERE candidate_id = ?",
                (candidate_id,)
            )
            conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"CandidateRepository: deleted {candidate_id}")
        return deleted

    # ──────────────────────────────────────────────────────────────────
    # Domain-specific operations beyond the base interface
    # ──────────────────────────────────────────────────────────────────

    def update_decision(
        self,
        candidate_id: str,
        new_decision: Decision,
        changed_by: str = "hiring_manager",
    ) -> bool:
        """
        Updates the hiring_decision column and appends an audit entry.

        Returns False if the candidate_id does not exist.

        WHY NOT use the generic update() method:
        This operation has a side effect (audit entry) that is tightly
        coupled to the domain rule "every decision change must be logged".
        A generic update() can't express that contract safely.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT hiring_decision FROM candidates WHERE candidate_id = ?",
                (candidate_id,)
            ).fetchone()

            if not row:
                return False

            previous_decision = row["hiring_decision"]
            now = datetime.now(timezone.utc).isoformat()

            conn.execute(
                "UPDATE candidates SET hiring_decision = ? WHERE candidate_id = ?",
                (new_decision.value, candidate_id)
            )
            conn.execute("""
                INSERT INTO decision_audit
                    (candidate_id, previous_decision, new_decision, changed_at, changed_by)
                VALUES (?, ?, ?, ?, ?)
            """, (
                candidate_id,
                previous_decision,
                new_decision.value,
                now,
                changed_by,
            ))
            conn.commit()

        logger.info(
            f"CandidateRepository: decision updated for {candidate_id}: "
            f"{previous_decision} → {new_decision.value} by {changed_by}"
        )
        return True

    def get_decision_audit(self, candidate_id: str) -> List[Dict[str, Any]]:
        """Full audit trail for a candidate, oldest-first."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT audit_id, previous_decision, new_decision, changed_at, changed_by
                FROM decision_audit
                WHERE candidate_id = ?
                ORDER BY changed_at ASC
            """, (candidate_id,)).fetchall()
        return [dict(row) for row in rows]