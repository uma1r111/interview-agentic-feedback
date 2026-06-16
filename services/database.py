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
        # Core candidates table (stores fully evaluated candidates)
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

        # Intake staging table — tracks candidates from registration through evaluation
        # status lifecycle: 'awaiting_files' → 'ready' → 'evaluated'
        conn.execute("""
            CREATE TABLE IF NOT EXISTS candidate_intake (
                candidate_id            TEXT PRIMARY KEY,
                candidate_name          TEXT NOT NULL,
                role_type               TEXT NOT NULL,
                mcq_path                TEXT,
                programming_path        TEXT,
                cv_path                 TEXT,
                session1_path           TEXT,
                session2_path           TEXT,
                status                  TEXT NOT NULL DEFAULT 'awaiting_files',
                created_at              TEXT NOT NULL,
                evaluated_at            TEXT
            )
        """)

        # Migrations: add new columns for DBs created before schema changes
        for migration_sql in [
            "ALTER TABLE candidate_intake ADD COLUMN mcq_path TEXT",
            "ALTER TABLE candidate_intake ADD COLUMN programming_path TEXT",
        ]:
            try:
                conn.execute(migration_sql)
                conn.commit()
                logger.info(f"Migration applied: {migration_sql[:60]}")
            except Exception:
                pass  # Column already exists — safe to ignore

        # Status repair: reset any 'ready' rows that are missing required paths
        # (these were created under the old schema before path-based storage)
        repair = conn.execute("""
            UPDATE candidate_intake
            SET status = 'awaiting_files'
            WHERE status = 'ready'
              AND (mcq_path IS NULL OR programming_path IS NULL
                   OR cv_path IS NULL OR session1_path IS NULL OR session2_path IS NULL)
        """)
        conn.commit()
        if repair.rowcount > 0:
            logger.warning(
                f"Status repair: reset {repair.rowcount} stale 'ready' record(s) to "
                "'awaiting_files' due to missing file paths (schema migration artefact)."
            )

        conn.commit()

    logger.info("Database initialized. All tables verified.")


# ==============================================================================
# Intake Write Operations
# ==============================================================================

def create_candidate_intake(candidate_id: str, candidate_name: str, role_type: str) -> None:
    """
    Phase 1: Registers a new candidate stub immediately after Step 1 form submission.
    Sets status to 'awaiting_files' — no files or scores yet.
    Also creates the candidate's folder under fixtures/candidates/.
    """
    import os
    folder_path = os.path.join("fixtures", "candidates", candidate_id)
    os.makedirs(folder_path, exist_ok=True)
    logger.info(f"Created candidate folder: {folder_path}")

    created_at = datetime.now(timezone.utc).isoformat()

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO candidate_intake
                (candidate_id, candidate_name, role_type, status, created_at)
            VALUES (?, ?, ?, 'awaiting_files', ?)
        """, (candidate_id, candidate_name, role_type, created_at))
        conn.commit()

    logger.info(f"Candidate intake record created: {candidate_id} ({candidate_name}, {role_type})")


def update_candidate_intake_files(
    candidate_id: str,
    mcq_score: float,
    mcq_selections: str,
    programming_answer_1: str,
    programming_answer_2: str,
    cv_path: str,
    session1_path: str,
    session2_path: str,
) -> None:
    """
    Phase 2: Updates all file paths and scores after Step 2 upload.
    Sets status to 'ready' when all required fields are present.
    """
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE candidate_intake SET
                mcq_score            = ?,
                mcq_selections       = ?,
                programming_answer_1 = ?,
                programming_answer_2 = ?,
                cv_path              = ?,
                session1_path        = ?,
                session2_path        = ?,
                status               = 'ready'
            WHERE candidate_id = ?
        """, (
            mcq_score,
            mcq_selections,
            programming_answer_1,
            programming_answer_2,
            cv_path,
            session1_path,
            session2_path,
            candidate_id
        ))
        conn.commit()

    logger.info(f"Candidate intake files updated: {candidate_id} → status=ready")


def mark_intake_evaluated(candidate_id: str) -> None:
    """Marks a candidate's intake record as 'evaluated' after the pipeline completes."""
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE candidate_intake
            SET status = 'evaluated', evaluated_at = ?
            WHERE candidate_id = ?
        """, (datetime.now(timezone.utc).isoformat(), candidate_id))
        conn.commit()

    logger.info(f"Candidate intake marked as evaluated: {candidate_id}")


def delete_intake_candidate(candidate_id: str) -> bool:
    """
    Hard-deletes a candidate_intake row by ID.

    Only intended for candidates in 'awaiting_files' status.
    Returns True if a row was deleted, False if no row matched.
    The caller is responsible for removing the fixtures folder.
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM candidate_intake WHERE candidate_id = ?",
            (candidate_id,)
        )
        conn.commit()
        deleted = cursor.rowcount > 0

    if deleted:
        logger.info(f"Intake record deleted: {candidate_id}")
    else:
        logger.warning(f"Delete attempted but no record found: {candidate_id}")
    return deleted


def patch_intake_candidate(candidate_id: str, **fields) -> None:
    """
    Partially updates a candidate_intake row with only the supplied keyword args.
    Automatically recalculates status:
      - 'ready'          if all 6 required fields are now non-null
      - 'awaiting_files' otherwise

    Supported field names (all map to DB columns):
      mcq_path, programming_path, cv_path, session1_path, session2_path
    """
    REQUIRED_FIELDS = (
        "mcq_path", "programming_path",
        "cv_path", "session1_path", "session2_path"
    )
    ALLOWED = set(REQUIRED_FIELDS)
    filtered = {k: v for k, v in fields.items() if k in ALLOWED and v is not None}
    if not filtered:
        return

    set_clauses = ", ".join(f"{col} = ?" for col in filtered)
    values = list(filtered.values()) + [candidate_id]

    with get_db_connection() as conn:
        conn.execute(
            f"UPDATE candidate_intake SET {set_clauses} WHERE candidate_id = ?",
            values
        )
        conn.commit()

        # Re-fetch to determine new completeness
        row = conn.execute(
            f"SELECT {', '.join(REQUIRED_FIELDS)} FROM candidate_intake WHERE candidate_id = ?",
            (candidate_id,)
        ).fetchone()
        if row and all(row[f] is not None for f in REQUIRED_FIELDS):
            conn.execute(
                "UPDATE candidate_intake SET status = 'ready' WHERE candidate_id = ?",
                (candidate_id,)
            )
            conn.commit()
            logger.info(f"Intake {candidate_id} → all fields complete, status=ready")
        else:
            conn.execute(
                "UPDATE candidate_intake SET status = 'awaiting_files' WHERE candidate_id = ?",
                (candidate_id,)
            )
            conn.commit()

    logger.info(f"Intake patched: {candidate_id} | fields updated: {list(filtered.keys())}")


# ==============================================================================
# Intake Read Operations
# ==============================================================================

def get_all_intake_candidates() -> List[Dict[str, Any]]:
    """Returns all intake rows ordered by creation time (newest first)."""
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT candidate_id, candidate_name, role_type,
                   mcq_path, programming_path,
                   cv_path, session1_path, session2_path,
                   status, created_at, evaluated_at
            FROM candidate_intake
            ORDER BY created_at DESC
        """).fetchall()
    return [dict(row) for row in rows]


def find_intake_by_name(candidate_name: str) -> List[Dict[str, Any]]:
    """
    Returns all intake rows whose candidate_name matches (case-insensitive).
    Used for duplicate-name detection before creating a new intake record.
    """
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT candidate_id, candidate_name, role_type, status, created_at
            FROM candidate_intake
            WHERE LOWER(candidate_name) = LOWER(?)
        """, (candidate_name.strip(),)).fetchall()
    return [dict(row) for row in rows]


def get_intake_candidate(candidate_id: str) -> Optional[Dict[str, Any]]:
    """Fetches a single intake record by ID. Returns None if not found."""
    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT *
            FROM candidate_intake
            WHERE candidate_id = ?
        """, (candidate_id,)).fetchone()
    return dict(row) if row else None


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