# repositories/postgres_candidate_repository.py
"""
PostgreSQL implementation of the candidate repository.

DIP IN ACTION
--------------
This class inherits from BaseRepository[FeedbackReport] — the same
abstract interface as CandidateRepository (SQLite). The api/main.py
startup code injects whichever concrete class is appropriate based on
whether DATABASE_URL is set. Nothing in the route handlers knows or
cares which implementation is running.

SQLAlchemy Core vs psycopg2 directly
--------------------------------------
We use SQLAlchemy Core (engine.connect()) rather than raw psycopg2 for:
  1. Connection pooling via DatabaseManager singleton
  2. Parameterised queries use :name syntax (cleaner than %s)
  3. No manual connection management per method
  4. Future dialect portability (CockroachDB, Aurora, etc.)

SQL DIALECT DIFFERENCES FROM SQLITE
-------------------------------------
SQLite:  INSERT OR REPLACE INTO ...
Postgres: INSERT INTO ... ON CONFLICT (id) DO UPDATE SET ...

SQLite:  No RETURNING clause needed (lastrowid)
Postgres: INSERT ... RETURNING column  (preferred way to get back values)

Both are handled here — SQLite repo is unchanged.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from models.bias import BiasLog
from models.enums import Decision
from models.evaluation import FeedbackReport
from repositories.base import BaseRepository
from services.connection_manager import DatabaseManager

logger = logging.getLogger(__name__)


class PostgresCandidateRepository(BaseRepository[FeedbackReport]):
    """
    PostgreSQL-backed candidate repository.

    Injected via DatabaseManager singleton — never creates its own
    connections. All connection lifecycle is managed by the pool.

    Constructor takes no arguments because it uses the global
    DatabaseManager singleton. This keeps construction simple
    (same as the SQLite version) while the pooling happens inside
    DatabaseManager.get_connection().
    """

    def __init__(self) -> None:
        self._db = DatabaseManager()

    # ──────────────────────────────────────────────────────────────────
    # Schema bootstrap
    # ──────────────────────────────────────────────────────────────────

    def init_schema(self) -> None:
        """
        Creates the candidates and decision_audit tables if absent.
        Safe to call on every startup (CREATE TABLE IF NOT EXISTS).

        Postgres-specific:
          - TEXT for all string columns (same as SQLite but explicit)
          - SERIAL for audit_id autoincrement (Postgres syntax)
          - DOUBLE PRECISION for mcq_score (vs REAL in SQLite)
        """
        with self._db.get_connection() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id        TEXT PRIMARY KEY,
                    candidate_name      TEXT NOT NULL,
                    role_type           TEXT NOT NULL,
                    mcq_score           DOUBLE PRECISION NOT NULL,
                    ai_recommendation   TEXT,
                    hiring_decision     TEXT NOT NULL DEFAULT 'Hold',
                    evaluated_at        TEXT NOT NULL,
                    feedback_report     TEXT NOT NULL,
                    bias_log            TEXT
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS decision_audit (
                    audit_id            SERIAL PRIMARY KEY,
                    candidate_id        TEXT NOT NULL
                                        REFERENCES candidates(candidate_id),
                    previous_decision   TEXT,
                    new_decision        TEXT NOT NULL,
                    changed_at          TEXT NOT NULL,
                    changed_by          TEXT DEFAULT 'system'
                )
            """))
        logger.info("PostgresCandidateRepository: schema verified.")

    # ──────────────────────────────────────────────────────────────────
    # BaseRepository interface
    # ──────────────────────────────────────────────────────────────────

    def get_by_id(self, candidate_id: str) -> Optional[FeedbackReport]:
        """
        Fetches FeedbackReport, overriding hiring_manager_decision
        with the authoritative DB column value.
        """
        with self._db.get_connection() as conn:
            row = conn.execute(
                text("""
                    SELECT feedback_report, hiring_decision
                    FROM candidates
                    WHERE candidate_id = :candidate_id
                """),
                {"candidate_id": candidate_id}
            ).fetchone()

        if not row:
            return None

        report = FeedbackReport.model_validate_json(row.feedback_report)
        report.hiring_manager_decision = Decision(row.hiring_decision)
        return report

    def get_all(self) -> List[Dict[str, Any]]:
        """
        Lightweight summary rows for dashboard — does NOT deserialize
        the full feedback_report JSON blob.
        """
        with self._db.get_connection() as conn:
            rows = conn.execute(text("""
                SELECT candidate_id, candidate_name, role_type, mcq_score,
                       ai_recommendation, hiring_decision, evaluated_at
                FROM candidates
                ORDER BY evaluated_at DESC
            """)).fetchall()

        return [row._asdict() for row in rows]

    def save(self, candidate_id: str, final_state: Dict[str, Any]) -> None:
        """
        Upserts a completed evaluation.

        POSTGRES SYNTAX: INSERT ... ON CONFLICT DO UPDATE
        vs SQLite's:     INSERT OR REPLACE INTO

        Also seeds the decision audit trail with the initial 'Hold'.
        """
        feedback_report: Optional[FeedbackReport] = final_state.get("feedback_report")
        bias_log: Optional[BiasLog] = final_state.get("bias_log")

        feedback_report_json = feedback_report.model_dump_json() if feedback_report else None
        bias_log_json        = bias_log.model_dump_json() if bias_log else None
        ai_recommendation    = feedback_report.ai_recommendation.value if feedback_report else None
        hiring_decision      = (
            feedback_report.hiring_manager_decision.value
            if feedback_report else "Hold"
        )
        role_type = final_state.get("role_type")
        role_type_str = role_type.value if hasattr(role_type, "value") else str(role_type)
        now = datetime.now(timezone.utc).isoformat()

        with self._db.get_connection() as conn:
            conn.execute(text("""
                INSERT INTO candidates (
                    candidate_id, candidate_name, role_type, mcq_score,
                    ai_recommendation, hiring_decision, evaluated_at,
                    feedback_report, bias_log
                )
                VALUES (
                    :candidate_id, :candidate_name, :role_type, :mcq_score,
                    :ai_recommendation, :hiring_decision, :evaluated_at,
                    :feedback_report, :bias_log
                )
                ON CONFLICT (candidate_id) DO UPDATE SET
                    candidate_name    = EXCLUDED.candidate_name,
                    role_type         = EXCLUDED.role_type,
                    mcq_score         = EXCLUDED.mcq_score,
                    ai_recommendation = EXCLUDED.ai_recommendation,
                    hiring_decision   = EXCLUDED.hiring_decision,
                    evaluated_at      = EXCLUDED.evaluated_at,
                    feedback_report   = EXCLUDED.feedback_report,
                    bias_log          = EXCLUDED.bias_log
            """), {
                "candidate_id":     candidate_id,
                "candidate_name":   final_state.get("candidate_name"),
                "role_type":        role_type_str,
                "mcq_score":        final_state.get("mcq_score"),
                "ai_recommendation": ai_recommendation,
                "hiring_decision":  hiring_decision,
                "evaluated_at":     now,
                "feedback_report":  feedback_report_json,
                "bias_log":         bias_log_json,
            })

            # Seed audit trail with the initial pipeline decision
            conn.execute(text("""
                INSERT INTO decision_audit
                    (candidate_id, previous_decision, new_decision,
                     changed_at, changed_by)
                VALUES
                    (:candidate_id, :previous_decision, :new_decision,
                     :changed_at, :changed_by)
            """), {
                "candidate_id":      candidate_id,
                "previous_decision": None,
                "new_decision":      hiring_decision,
                "changed_at":        now,
                "changed_by":        "pipeline",
            })

        logger.info(f"PostgresCandidateRepository: saved {candidate_id}")

    def delete(self, candidate_id: str) -> bool:
        with self._db.get_connection() as conn:
            result = conn.execute(
                text("DELETE FROM candidates WHERE candidate_id = :id"),
                {"id": candidate_id}
            )
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"PostgresCandidateRepository: deleted {candidate_id}")
        return deleted

    # ──────────────────────────────────────────────────────────────────
    # Domain-specific operations
    # ──────────────────────────────────────────────────────────────────

    def update_decision(
        self,
        candidate_id: str,
        new_decision: Decision,
        changed_by: str = "hiring_manager",
    ) -> bool:
        """
        Updates hiring_decision and appends an audit entry atomically.
        Both statements run inside the same connection transaction.
        """
        now = datetime.now(timezone.utc).isoformat()

        with self._db.get_connection() as conn:
            row = conn.execute(
                text("SELECT hiring_decision FROM candidates WHERE candidate_id = :id"),
                {"id": candidate_id}
            ).fetchone()

            if not row:
                return False

            previous_decision = row.hiring_decision

            conn.execute(
                text("""
                    UPDATE candidates
                    SET hiring_decision = :new_decision
                    WHERE candidate_id = :candidate_id
                """),
                {"new_decision": new_decision.value, "candidate_id": candidate_id}
            )

            conn.execute(text("""
                INSERT INTO decision_audit
                    (candidate_id, previous_decision, new_decision,
                     changed_at, changed_by)
                VALUES
                    (:candidate_id, :previous_decision, :new_decision,
                     :changed_at, :changed_by)
            """), {
                "candidate_id":      candidate_id,
                "previous_decision": previous_decision,
                "new_decision":      new_decision.value,
                "changed_at":        now,
                "changed_by":        changed_by,
            })

        logger.info(
            f"PostgresCandidateRepository: decision updated for {candidate_id}: "
            f"{previous_decision} → {new_decision.value} by {changed_by}"
        )
        return True

    def get_decision_audit(self, candidate_id: str) -> List[Dict[str, Any]]:
        """Full audit trail, oldest-first."""
        with self._db.get_connection() as conn:
            rows = conn.execute(text("""
                SELECT audit_id, previous_decision, new_decision,
                       changed_at, changed_by
                FROM decision_audit
                WHERE candidate_id = :candidate_id
                ORDER BY changed_at ASC
            """), {"candidate_id": candidate_id}).fetchall()

        return [row._asdict() for row in rows]
