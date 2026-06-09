import os
import json
import sqlite3
import logging
from datetime import datetime, timezone
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field
from typing import Dict, Any, List

# Core system schema and graph imports
from models.enums import RoleType, Decision
from models.candidate import CandidateBundle
from models.evaluation import FeedbackReport
from models.bias import BiasLog
from graph.pipeline import create_interview_graph
from services.pdf_extractor import PDFExtractorService

# Setup modular logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API_Server")

# Initialize the global application framework
app = FastAPI(
    title="AI Interview Feedback Pipeline Server",
    version="1.0.0",
    description="Backend microservice serving multi-agent evaluation DAG pipelines via LangGraph."
)

# Compile the single, persistent global Graph layout into memory
interview_graph = create_interview_graph()

# Instantiate shared PDF extraction utility
pdf_extractor = PDFExtractorService()

# ==============================================================================
# SQLite Configuration
# ==============================================================================
DATABASE_PATH = "database.db"

def init_database():
    """Creates the candidates table if it does not already exist."""
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id    TEXT PRIMARY KEY,
                candidate_name  TEXT NOT NULL,
                role_type       TEXT NOT NULL,
                mcq_score       REAL NOT NULL,
                ai_recommendation TEXT,
                hiring_decision TEXT NOT NULL DEFAULT 'Hold',
                evaluated_at    TEXT NOT NULL,
                feedback_report TEXT NOT NULL,
                bias_log        TEXT
            )
        """)
        conn.commit()
    logger.info("Database initialized. Candidates table verified.")

@contextmanager
def get_db_connection():
    """Context manager providing a clean SQLite connection with automatic cleanup."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# ==============================================================================
# Database Helper Functions
# ==============================================================================

def db_save_candidate(candidate_id: str, final_state: Dict[str, Any]) -> None:
    """Serializes and persists a completed candidate evaluation to SQLite."""
    feedback_report = final_state.get("feedback_report")
    bias_log = final_state.get("bias_log")

    # Serialize Pydantic objects to JSON strings for storage
    feedback_report_json = feedback_report.model_dump_json() if feedback_report else None
    bias_log_json = bias_log.model_dump_json() if bias_log else None

    # Extract flat fields for queryable columns
    ai_recommendation = feedback_report.ai_recommendation.value if feedback_report else None
    hiring_decision = feedback_report.hiring_manager_decision.value if feedback_report else "Hold"

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
            final_state.get("role_type").value if hasattr(final_state.get("role_type"), "value") else str(final_state.get("role_type")),
            final_state.get("mcq_score"),
            ai_recommendation,
            hiring_decision,
            datetime.now(timezone.utc).isoformat(),
            feedback_report_json,
            bias_log_json
        ))
        conn.commit()
    logger.info(f"Candidate {candidate_id} persisted to SQLite.")

def db_get_candidate_report(candidate_id: str) -> FeedbackReport:
    """
    Fetches a candidate's FeedbackReport from SQLite.
    Overrides hiring_manager_decision with the authoritative column value at read time.
    """
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT feedback_report, hiring_decision FROM candidates WHERE candidate_id = ?",
            (candidate_id,)
        ).fetchone()

    if not row:
        return None

    # Deserialize the blob back into a FeedbackReport
    report = FeedbackReport.model_validate_json(row["feedback_report"])

    # Override decision with the authoritative column value
    report.hiring_manager_decision = Decision(row["hiring_decision"])

    return report

def db_update_hiring_decision(candidate_id: str, decision: Decision) -> bool:
    """Updates only the hiring_decision column for a candidate. Returns False if not found."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "UPDATE candidates SET hiring_decision = ? WHERE candidate_id = ?",
            (decision.value, candidate_id)
        )
        conn.commit()
        return cursor.rowcount > 0

def db_get_all_candidates() -> List[Dict[str, Any]]:
    """
    Fetches lightweight candidate list rows for the dashboard candidate list view.
    Does not deserialize the full feedback_report blob — uses flat columns only.
    """
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT candidate_id, candidate_name, role_type, mcq_score,
                   ai_recommendation, hiring_decision, evaluated_at
            FROM candidates
            ORDER BY evaluated_at DESC
        """).fetchall()
    return [dict(row) for row in rows]

# ==============================================================================
# API Request/Response Models
# ==============================================================================


class DecisionPatchPayload(BaseModel):
    """Strict data payload covering human-override hiring actions."""
    decision: Decision

# ==============================================================================
# Application Startup
# ==============================================================================

@app.on_event("startup")
def on_startup():
    """Initializes the SQLite database on server startup."""
    init_database()

# ==============================================================================
# Functional Route Handlers
# ==============================================================================

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, str]:
    """Basic diagnostic heartbeat verifying system availability."""
    return {"status": "healthy", "service": "interview-agentic-feedback"}


@app.post("/candidates", status_code=status.HTTP_201_CREATED)
async def submit_candidate_intake(
    candidate_name: str = Form(..., description="Full name of the candidate"),
    role_type: str = Form(..., description="Role enum value: SWE | AI | BA | Trainee"),
    mcq_score: float = Form(..., description="Pre-interview MCQ score (0.0 – 5.0)"),
    programming_answer_1: str = Form(..., description="Raw code text for programming question 1"),
    programming_answer_2: str = Form(..., description="Raw code text for programming question 2"),
    mcq_selections: str = Form(..., description="JSON string: { question_id: selected_answer }"),
    session1_transcript: str = Form(..., description="Full diarized text of Session 1 (technical panel)"),
    session2_transcript: str = Form(..., description="Full diarized text of Session 2 (HR behavioural)"),
    cv_file: UploadFile = File(..., description="Candidate CV in PDF format"),
) -> Dict[str, str]:
    """
    Accepts a multipart/form-data submission containing candidate details,
    interview transcripts, MCQ data, and a PDF CV file.

    The PDF is extracted to plain text at the API boundary before any pipeline
    node or LLM sees it. The rest of the flow is identical to before.
    """
    logger.info(f"API: Received pipeline evaluation request for candidate: {candidate_name}")

    # ------------------------------------------------------------------
    # 1. Validate and extract the uploaded CV PDF
    # ------------------------------------------------------------------
    if cv_file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{cv_file.content_type}'. Only PDF files are accepted."
        )

    try:
        pdf_bytes = await cv_file.read()
        raw_cv_text = pdf_extractor.extract_text(pdf_bytes)
        logger.info(f"API: PDF extraction successful. Extracted {len(raw_cv_text)} characters from CV.")
    except ValueError as pdf_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CV PDF extraction failed: {str(pdf_err)}"
        )
    except Exception as pdf_err:
        logger.error(f"API: Unexpected PDF extraction error: {str(pdf_err)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process uploaded CV file: {str(pdf_err)}"
        )

    # ------------------------------------------------------------------
    # 2. Parse the MCQ selections JSON string sent as a form field
    # ------------------------------------------------------------------
    try:
        mcq_selections_dict = json.loads(mcq_selections)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="mcq_selections must be a valid JSON string. Example: '{\"q1\": \"A\", \"q2\": \"C\"}'"
        )

    # ------------------------------------------------------------------
    # 3. Validate the full candidate bundle with Pydantic
    # ------------------------------------------------------------------
    try:
        candidate_bundle = CandidateBundle(
            candidate_name=candidate_name,
            role_type=RoleType(role_type),
            raw_cv=raw_cv_text,
            mcq_score=mcq_score,
            programming_answers=[programming_answer_1, programming_answer_2],
            session1_transcript=session1_transcript,
            session2_transcript=session2_transcript,
        )
    except Exception as validation_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Candidate bundle validation failed: {str(validation_err)}"
        )

    # ------------------------------------------------------------------
    # 4. Build initial state and invoke the LangGraph pipeline
    # ------------------------------------------------------------------
    try:

        initial_inputs = {
            "candidate_name": candidate_bundle.candidate_name,
            "role_type":      candidate_bundle.role_type,
            "raw_cv":         candidate_bundle.raw_cv,
            "mcq_score":      candidate_bundle.mcq_score,
            "programming_answers": candidate_bundle.programming_answers,
            "session1_transcript": candidate_bundle.session1_transcript,
            "session2_transcript": candidate_bundle.session2_transcript,
            "raw_payload":    candidate_bundle.model_dump(),
            "mcq_responses":  mcq_selections_dict
        }

        final_output_state = interview_graph.invoke(initial_inputs)

        logger.info(f"Final state keys: {list(final_output_state.keys())}")
        logger.info(f"feedback_report: {final_output_state.get('feedback_report')}")
        logger.info(f"bias_clear: {final_output_state.get('bias_clear')}")
        logger.info(f"bias_log: {final_output_state.get('bias_log')}")
        logger.info(f"error: {final_output_state.get('error')}")
        if final_output_state.get("error"):
            logger.error(f"API: Graph pipeline aborted: {final_output_state['error']}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Graph processing halted: {final_output_state['error']}"
            )

        candidate_id = final_output_state["candidate_id"]
        # Persist to SQLite
        db_save_candidate(candidate_id, final_output_state)
        logger.info(f"API: Evaluation cycle completed. Candidate saved with ID: {candidate_id}")

        return {
            "candidate_id": candidate_id,
            "status": "compiled",
            "message": "Multi-agent evaluation and compliance bias checks completed successfully."
        }

    except HTTPException:
        raise
    except Exception as general_error:
        logger.error(f"API Fatal Exception: {str(general_error)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal graph runtime execution error: {str(general_error)}"
        )

@app.get("/candidates", status_code=status.HTTP_200_OK)
def get_all_candidates() -> List[Dict[str, Any]]:
    """Returns lightweight candidate list for dashboard navigation."""
    return db_get_all_candidates()

@app.get("/candidates/{candidate_id}/report", status_code=status.HTTP_200_OK)
def get_compiled_feedback_report(candidate_id: str) -> Any:
    """Fetches the final structured, sanitized evaluation feedback report for a candidate."""
    report = db_get_candidate_report(candidate_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate profile record for ID '{candidate_id}' not found in active data indices."
        )

    return report


@app.patch("/candidates/{candidate_id}/decision", status_code=status.HTTP_200_OK)
def patch_hiring_decision(candidate_id: str, payload: DecisionPatchPayload) -> Dict[str, str]:
    """Updates a candidate's hiring decision. Only the decision column is updated."""
    updated = db_update_hiring_decision(candidate_id, payload.decision)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cannot append decision parameters. Candidate ID '{candidate_id}' not found."
        )

    logger.info(f"API: Human decision recorded for {candidate_id}. Status changed to: {payload.decision}")

    return {
        "candidate_id": candidate_id,
        "decision_status": payload.decision,
        "message": "Hiring decision successfully recorded and committed to candidate profile."
    }