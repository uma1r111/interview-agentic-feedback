import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.bias import BiasLog
from models.enums import Decision
from models.evaluation import FeedbackReport
from config.settings import get_settings

logger = logging.getLogger("DatabaseService")
settings = get_settings()


# ==============================================================================
# Connection Management
# ==============================================================================

@contextmanager
def get_db_connection():
    """Context manager providing a clean SQLite connection with automatic cleanup."""
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ==============================================================================
# Schema Initialization
# ==============================================================================

def init_database() -> None:
    """
    Creates all required tables if they do not already exist.
    Safe to call on every startup — uses CREATE TABLE IF NOT EXISTS.
    """
    with get_db_connection() as conn:
        # Core candidates table
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

        # Hiring decision audit trail — every decision change is recorded
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

    logger.info("Database initialized. All tables verified.")


# ==============================================================================
# Candidate Write Operations
# ==============================================================================

def save_candidate(candidate_id: str, final_state: Dict[str, Any]) -> None:
    """
    Serializes and persists a completed candidate evaluation to SQLite.
    Uses INSERT OR REPLACE — re-evaluating the same candidate overwrites the previous record.
    """
    feedback_report: Optional[FeedbackReport] = final_state.get("feedback_report")
    bias_log: Optional[BiasLog] = final_state.get("bias_log")

    feedback_report_json = feedback_report.model_dump_json() if feedback_report else None
    bias_log_json = bias_log.model_dump_json() if bias_log else None

    ai_recommendation = feedback_report.ai_recommendation.value if feedback_report else None
    hiring_decision = feedback_report.hiring_manager_decision.value if feedback_report else "Hold"

    role_type = final_state.get("role_type")
    role_type_str = role_type.value if hasattr(role_type, "value") else str(role_type)

    with get_db_connection() as conn:
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
            datetime.now(timezone.utc).isoformat(),
            feedback_report_json,
            bias_log_json
        ))

        # Seed the audit trail with the initial Hold decision on first save
        conn.execute("""
            INSERT INTO decision_audit
                (candidate_id, previous_decision, new_decision, changed_at, changed_by)
            VALUES (?, ?, ?, ?, ?)
        """, (
            candidate_id,
            None,
            hiring_decision,
            datetime.now(timezone.utc).isoformat(),
            "pipeline"
        ))

        conn.commit()

    logger.info(f"Candidate {candidate_id} persisted to database.")


# ==============================================================================
# Candidate Read Operations
# ==============================================================================

def get_candidate_report(candidate_id: str) -> Optional[FeedbackReport]:
    """
    Fetches and deserializes a candidate's FeedbackReport.
    Overrides hiring_manager_decision with the authoritative column value at read time.
    """
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT feedback_report, hiring_decision FROM candidates WHERE candidate_id = ?",
            (candidate_id,)
        ).fetchone()

    if not row:
        return None

    report = FeedbackReport.model_validate_json(row["feedback_report"])
    report.hiring_manager_decision = Decision(row["hiring_decision"])
    return report


def get_all_candidates() -> List[Dict[str, Any]]:
    """
    Fetches lightweight candidate list rows for dashboard navigation.
    Reads flat columns only — does not deserialize the full feedback_report blob.
    """
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT candidate_id, candidate_name, role_type, mcq_score,
                   ai_recommendation, hiring_decision, evaluated_at
            FROM candidates
            ORDER BY evaluated_at DESC
        """).fetchall()

    return [dict(row) for row in rows]


def get_decision_audit(candidate_id: str) -> List[Dict[str, Any]]:
    """
    Returns the full decision audit trail for a candidate.
    Used for compliance review and dashboard history view.
    """
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT audit_id, previous_decision, new_decision, changed_at, changed_by
            FROM decision_audit
            WHERE candidate_id = ?
            ORDER BY changed_at ASC
        """, (candidate_id,)).fetchall()

    return [dict(row) for row in rows]


# ==============================================================================
# Candidate Update Operations
# ==============================================================================

def update_hiring_decision(
    candidate_id: str,
    new_decision: Decision,
    changed_by: str = "hiring_manager"
) -> bool:
    """
    Updates the hiring_decision column and writes an audit trail entry.
    Returns False if the candidate_id does not exist.
    """
    with get_db_connection() as conn:
        # Fetch current decision for audit trail
        row = conn.execute(
            "SELECT hiring_decision FROM candidates WHERE candidate_id = ?",
            (candidate_id,)
        ).fetchone()

        if not row:
            return False

        previous_decision = row["hiring_decision"]

        # Update the decision column
        conn.execute(
            "UPDATE candidates SET hiring_decision = ? WHERE candidate_id = ?",
            (new_decision.value, candidate_id)
        )

        # Write audit trail entry
        conn.execute("""
            INSERT INTO decision_audit
                (candidate_id, previous_decision, new_decision, changed_at, changed_by)
            VALUES (?, ?, ?, ?, ?)
        """, (
            candidate_id,
            previous_decision,
            new_decision.value,
            datetime.now(timezone.utc).isoformat(),
            changed_by
        ))

        conn.commit()

    logger.info(
        f"Hiring decision updated for {candidate_id}: "
        f"{previous_decision} → {new_decision.value} by {changed_by}"
    )
    return True