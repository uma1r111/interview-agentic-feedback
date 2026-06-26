# api/main.py
"""
FastAPI application entry point.

ARCHITECTURE CHANGES (Repository Pattern)
------------------------------------------
All database access has been moved out of this file into:
  - CandidateRepository  →  evaluated candidates + decision audit
  - IntakeRepository     →  two-step candidate intake staging

Route handlers now only:
  1. Validate HTTP input
  2. Call a repository or service
  3. Return an HTTP response

This file no longer contains any SQL, raw DB connections, or schema
definitions. To switch from SQLite to PostgreSQL, only the repository
classes change — nothing here.

DEPENDENCY INJECTION
---------------------
Both repositories are instantiated once at startup and attached to
app.state. This makes them accessible in every route via the `Request`
object, and makes them trivially replaceable in tests by swapping
app.state before the test runs.
"""

import json
import logging
import os
import shutil
import uuid
from typing import Any, Dict, List, Optional

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import (
    AITokenCostTrackingMiddleware,
    BestPracticeLoggingMiddleware,
    LimitUploadSizeMiddleware,
    RateLimiterMiddleware,
)
from api.schemas import DecisionPatchPayload
from config.settings import get_settings
from graph.pipeline import create_interview_graph
from models.candidate import CandidateBundle
from models.enums import Decision, RoleType
from repositories.candidate_repository import CandidateRepository
from repositories.intake_repository import IntakeRepository
from repositories.postgres_candidate_repository import PostgresCandidateRepository
from repositories.postgres_intake_repository import PostgresIntakeRepository
from services.connection_manager import DatabaseManager, CacheManager
from services.file_extractor import FileExtractorService
from services.pdf_extractor import PDFExtractorService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API_Server")

settings = get_settings()

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description="Backend microservice serving multi-agent evaluation DAG pipelines via LangGraph.",
)

# ── Middleware (order matters — outermost wraps first) ────────────────────────
app.add_middleware(LimitUploadSizeMiddleware)
app.add_middleware(AITokenCostTrackingMiddleware)
app.add_middleware(BestPracticeLoggingMiddleware)
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Shared service instances (stateless, safe to share) ──────────────────────
interview_graph = create_interview_graph()
pdf_extractor = PDFExtractorService()
file_extractor = FileExtractorService()

# ── In-memory progress store (per-process; Redis will replace this in Phase 2) ─
PROGRESS_STORE: Dict[str, Dict[str, Any]] = {}


# ==============================================================================
# Startup: initialise repositories and attach to app.state
# ==============================================================================

@app.on_event("startup")
def on_startup() -> None:
    """
    Injects Postgres repos when DATABASE_URL is set (Docker),
    falls back to SQLite repos for local development.
    """
    if settings.database_url:
        db = DatabaseManager()
        db.initialize(settings.database_url)
        CacheManager().initialize(settings.redis_url)

        candidate_repo = PostgresCandidateRepository()
        intake_repo = PostgresIntakeRepository()
        db_label = settings.database_url.split("@")[-1]  # hide credentials in log
    else:
        db_path = settings.database_path
        candidate_repo = CandidateRepository(db_path=db_path)
        intake_repo = IntakeRepository(db_path=db_path)
        db_label = db_path

    candidate_repo.init_schema()
    intake_repo.init_schema()

    app.state.candidate_repo = candidate_repo
    app.state.intake_repo = intake_repo

    logger.info(
        f"Repositories initialised. DB: {db_label} | "
        f"{type(candidate_repo).__name__} ✓ | {type(intake_repo).__name__} ✓"
    )


# ==============================================================================
# Dependency helpers — thin accessors so routes stay readable
# ==============================================================================

def get_candidate_repo(request: Request):
    return request.app.state.candidate_repo


def get_intake_repo(request: Request):
    return request.app.state.intake_repo


# ==============================================================================
# Health
# ==============================================================================

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, str]:
    return {"status": "healthy", "service": "interview-agentic-feedback"}


# ==============================================================================
# Intake Routes — Two-Step Structured Candidate Registration
# ==============================================================================

def _write_candidate_info_json(folder_path: str, data: dict) -> None:
    """Serialises candidate metadata to disk so the folder is self-contained."""
    info_path = os.path.join(folder_path, "candidate_info.json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@app.post("/intake/create", status_code=status.HTTP_201_CREATED)
def intake_create_candidate(
    request: Request,
    candidate_name: str = Form(...),
    role_type: str = Form(...),
) -> Dict[str, str]:
    """
    Step 1: Registers a new candidate.

    BEFORE: called create_candidate_intake() from services/database.py
    AFTER:  calls intake_repo.save() — no SQL in this file
    """
    try:
        RoleType(role_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role_type '{role_type}'. Valid values: SWE, AI, BA, Trainee",
        )

    name_slug = candidate_name.lower().replace(" ", "_")
    candidate_id = f"cand_{name_slug}_{str(uuid.uuid4())[:8]}"
    folder_path = os.path.join("fixtures", "candidates", candidate_id)

    # Repository handles DB insert + folder creation
    get_intake_repo(request).save(
        candidate_id=candidate_id,
        data={"candidate_name": candidate_name, "role_type": role_type},
    )

    _write_candidate_info_json(folder_path, {
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "role_type": role_type,
        "status": "awaiting_files",
    })

    logger.info(f"Intake Step 1 complete: {candidate_id}")
    return {
        "candidate_id": candidate_id,
        "status": "awaiting_files",
        "message": f"Candidate '{candidate_name}' registered. Upload files to complete intake.",
    }


@app.get("/intake/check-duplicate", status_code=status.HTTP_200_OK)
def check_duplicate_name(
    request: Request,
    name: str = Query(...),
) -> Dict[str, Any]:
    """
    BEFORE: called find_intake_by_name() from services/database.py
    AFTER:  calls intake_repo.find_by_name()
    """
    matches = get_intake_repo(request).find_by_name(name)
    return {
        "name": name,
        "has_duplicates": len(matches) > 0,
        "existing_records": matches,
    }


@app.get("/intake/candidates", status_code=status.HTTP_200_OK)
def list_intake_candidates(request: Request) -> List[Dict[str, Any]]:
    """
    BEFORE: called get_all_intake_candidates() from services/database.py
    AFTER:  calls intake_repo.get_all()
    """
    return get_intake_repo(request).get_all()


@app.delete("/intake/{candidate_id}", status_code=status.HTTP_200_OK)
def delete_intake_record(
    request: Request,
    candidate_id: str,
) -> Dict[str, str]:
    """
    BEFORE: called get_intake_candidate() + delete_intake_candidate() from services/database.py
    AFTER:  calls intake_repo.get_by_id() + intake_repo.delete()

    Only 'awaiting_files' candidates can be deleted — guards are unchanged.
    """
    intake_repo = get_intake_repo(request)
    intake = intake_repo.get_by_id(candidate_id)

    if not intake:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No intake record found for '{candidate_id}'.",
        )
    if intake["status"] != "awaiting_files":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete candidate '{candidate_id}' with status '{intake['status']}'. "
                "Only 'awaiting_files' candidates can be deleted."
            ),
        )

    intake_repo.delete(candidate_id)

    folder_path = os.path.join("fixtures", "candidates", candidate_id)
    if os.path.isdir(folder_path):
        shutil.rmtree(folder_path)
        logger.info(f"Deleted fixtures folder: {folder_path}")

    return {
        "candidate_id": candidate_id,
        "message": f"Candidate '{intake['candidate_name']}' deleted from DB and file system.",
    }


@app.get("/intake/{candidate_id}", status_code=status.HTTP_200_OK)
def get_intake_record(
    request: Request,
    candidate_id: str,
) -> Dict[str, Any]:
    """
    BEFORE: called get_intake_candidate() from services/database.py
    AFTER:  calls intake_repo.get_by_id()
    """
    record = get_intake_repo(request).get_by_id(candidate_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No intake record found for '{candidate_id}'.",
        )
    return record


@app.post("/intake/{candidate_id}/upload", status_code=status.HTTP_200_OK)
async def intake_upload_files(
    request: Request,
    candidate_id: str,
    cv_file:       Optional[UploadFile] = File(None),
    session1_file: Optional[UploadFile] = File(None),
    session2_file: Optional[UploadFile] = File(None),
    mcq_file:      Optional[UploadFile] = File(None),
    prog_file_1:   Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """
    Partial/incremental upload — all files optional per call.

    BEFORE: called get_intake_candidate() + patch_intake_candidate()
            from services/database.py
    AFTER:  calls intake_repo.get_by_id() + intake_repo.update()

    Status auto-recalculates inside intake_repo.update() — no logic
    needed here.
    """
    intake_repo = get_intake_repo(request)
    intake = intake_repo.get_by_id(candidate_id)

    if not intake:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No intake record found for '{candidate_id}'. Run Step 1 first.",
        )
    if intake["status"] == "evaluated":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Candidate '{candidate_id}' has already been evaluated.",
        )

    folder_path = os.path.join("fixtures", "candidates", candidate_id)
    os.makedirs(folder_path, exist_ok=True)

    patch_fields: Dict[str, Any] = {}
    saved_files: Dict[str, str] = {}

    # ── CV ────────────────────────────────────────────────────────────
    if cv_file and cv_file.filename:
        if not cv_file.filename.lower().endswith(".pdf") \
                and cv_file.content_type not in ("application/pdf", "application/octet-stream"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"CV must be a PDF. Received: '{cv_file.filename}'.",
            )
        cv_bytes = await cv_file.read()
        cv_path = os.path.join(folder_path, "cv.pdf")
        with open(cv_path, "wb") as f:
            f.write(cv_bytes)
        patch_fields["cv_path"] = cv_path
        saved_files["cv"] = cv_path

    # ── Session 1 ─────────────────────────────────────────────────────
    if session1_file and session1_file.filename:
        s1_bytes = await session1_file.read()
        try:
            s1_text = file_extractor.extract(s1_bytes, session1_file.filename, session1_file.content_type)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Session 1: {e}")
        s1_path = os.path.join(folder_path, "session1_transcript.txt")
        with open(s1_path, "w", encoding="utf-8") as f:
            f.write(s1_text)
        patch_fields["session1_path"] = s1_path
        saved_files["session1_transcript"] = s1_path

    # ── Session 2 ─────────────────────────────────────────────────────
    if session2_file and session2_file.filename:
        s2_bytes = await session2_file.read()
        try:
            s2_text = file_extractor.extract(s2_bytes, session2_file.filename, session2_file.content_type)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Session 2: {e}")
        s2_path = os.path.join(folder_path, "session2_transcript.txt")
        with open(s2_path, "w", encoding="utf-8") as f:
            f.write(s2_text)
        patch_fields["session2_path"] = s2_path
        saved_files["session2_transcript"] = s2_path

    # ── MCQ file ──────────────────────────────────────────────────────
    if mcq_file and mcq_file.filename:
        mcq_bytes = await mcq_file.read()
        mcq_ext = mcq_file.filename.rsplit(".", 1)[-1] if "." in mcq_file.filename else "bin"
        mcq_path = os.path.join(folder_path, f"mcq_answers.{mcq_ext}")
        with open(mcq_path, "wb") as f:
            f.write(mcq_bytes)
        patch_fields["mcq_path"] = mcq_path
        saved_files["mcq_answers"] = mcq_path

    # ── Programming answers ───────────────────────────────────────────
    if prog_file_1 and prog_file_1.filename:
        p1_bytes = await prog_file_1.read()
        p1_ext = prog_file_1.filename.rsplit(".", 1)[-1] if "." in prog_file_1.filename else "bin"
        p1_path = os.path.join(folder_path, f"programming_answers.{p1_ext}")
        with open(p1_path, "wb") as f:
            f.write(p1_bytes)
        patch_fields["programming_path"] = p1_path
        saved_files["programming_answers"] = p1_path

    if not patch_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files were provided. Include at least one file per call.",
        )

    # Repository update: patches DB fields and recalculates status
    intake_repo.update(candidate_id, patch_fields)
    updated = intake_repo.get_by_id(candidate_id)

    _write_candidate_info_json(folder_path, {
        "candidate_id":     candidate_id,
        "candidate_name":   updated["candidate_name"],
        "role_type":        updated["role_type"],
        "mcq_path":         updated.get("mcq_path"),
        "programming_path": updated.get("programming_path"),
        "cv_path":          updated.get("cv_path"),
        "session1_path":    updated.get("session1_path"),
        "session2_path":    updated.get("session2_path"),
        "status":           updated["status"],
    })

    return {
        "candidate_id": candidate_id,
        "status": updated["status"],
        "message": (
            "All documents received. Candidate is ready for evaluation."
            if updated["status"] == "ready"
            else f"Saved {list(saved_files.keys())}. Upload remaining documents to complete intake."
        ),
        "saved_files": saved_files,
    }


@app.post("/intake/{candidate_id}/evaluate", status_code=status.HTTP_200_OK)
def intake_run_evaluation(
    request: Request,
    candidate_id: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, str]:
    """
    Step 3: Triggers background evaluation.

    BEFORE: called get_intake_candidate() from services/database.py
    AFTER:  calls intake_repo.get_by_id()

    The background task receives repository instances directly so it
    doesn't need to re-access app.state from a different thread context.
    """
    intake_repo = get_intake_repo(request)
    candidate_repo = get_candidate_repo(request)

    intake = intake_repo.get_by_id(candidate_id)
    if not intake:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No intake record found for '{candidate_id}'.",
        )
    if intake["status"] != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Candidate '{candidate_id}' is not ready. "
                f"Current status: '{intake['status']}'. "
                "Complete file upload (Step 2) first."
            ),
        )

    # Extract CV text
    try:
        with open(intake["cv_path"], "rb") as f:
            pdf_bytes = f.read()
        raw_cv_text = pdf_extractor.extract_text(pdf_bytes)
    except Exception as cv_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CV PDF extraction failed: {cv_err}",
        )

    # Read transcripts
    try:
        with open(intake["session1_path"], "r", encoding="utf-8") as f:
            session1_transcript = f.read()
        with open(intake["session2_path"], "r", encoding="utf-8") as f:
            session2_transcript = f.read()
    except Exception as file_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to read transcript files: {file_err}",
        )

    # Guard: all required paths present
    missing = [
        field for field, val in [
            ("Programming Answers", intake.get("programming_path")),
            ("MCQ Answers",          intake.get("mcq_path")),
            ("CV",                   intake.get("cv_path")),
            ("Session 1 Transcript", intake.get("session1_path")),
            ("Session 2 Transcript", intake.get("session2_path")),
        ] if not val
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required files: {', '.join(missing)}.",
        )

    # Read programming answers
    try:
        with open(intake["programming_path"], "rb") as f:
            prog_bytes = f.read()
        programming_text = file_extractor.extract(
            prog_bytes,
            os.path.basename(intake["programming_path"]),
            None,
        )
    except Exception as prog_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to read programming answers: {prog_err}",
        )

    try:
        candidate_bundle = CandidateBundle(
            candidate_name=intake["candidate_name"],
            role_type=RoleType(intake["role_type"]),
            raw_cv=raw_cv_text,
            mcq_score=0.0,
            programming_answers=[programming_text, programming_text],
            session1_transcript=session1_transcript,
            session2_transcript=session2_transcript,
        )
    except Exception as validation_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Bundle validation failed: {validation_err}",
        )

    initial_inputs = {
        "candidate_name":      candidate_bundle.candidate_name,
        "role_type":           candidate_bundle.role_type,
        "raw_cv":              candidate_bundle.raw_cv,
        "mcq_score":           candidate_bundle.mcq_score,
        "mcq_path":            intake["mcq_path"],
        "programming_path":    intake["programming_path"],
        "programming_answers": candidate_bundle.programming_answers,
        "session1_transcript": candidate_bundle.session1_transcript,
        "session2_transcript": candidate_bundle.session2_transcript,
        "raw_payload":         candidate_bundle.model_dump(),
        "mcq_responses":       {},
    }

    # Pass repository instances into the background task — avoids
    # re-accessing app.state from a background thread
    background_tasks.add_task(
        run_evaluation_background,
        candidate_id,
        initial_inputs,
        candidate_repo,
        intake_repo,
    )

    logger.info(f"Evaluation background task dispatched for: {candidate_id}")
    return {
        "candidate_id": candidate_id,
        "status": "running",
        "message": "Evaluation started in the background.",
    }


def run_evaluation_background(
    candidate_id: str,
    initial_inputs: dict,
    candidate_repo: CandidateRepository,
    intake_repo: IntakeRepository,
) -> None:
    """
    Executes the LangGraph pipeline in a background thread.

    BEFORE: called save_candidate() + mark_intake_evaluated()
            from services/database.py
    AFTER:  calls candidate_repo.save() + intake_repo.mark_evaluated()

    Repositories are injected as parameters — the function has no
    hidden dependency on module-level globals or app.state.
    """
    logger.info(f"Background evaluation started: {candidate_id}")
    PROGRESS_STORE[candidate_id] = {"status": "running", "events": []}

    try:
        final_output_state = dict(initial_inputs)

        for update in interview_graph.stream(initial_inputs, stream_mode="updates"):
            for node_name, state_update in update.items():
                logger.info(f"Completed node: {node_name}")
                PROGRESS_STORE[candidate_id]["events"].append(node_name)
                final_output_state.update(state_update)

        if final_output_state.get("error"):
            logger.error(f"Pipeline error: {final_output_state['error']}")
            PROGRESS_STORE[candidate_id]["status"] = "failed"
            PROGRESS_STORE[candidate_id]["error"] = final_output_state["error"]
            return

        final_output_state["candidate_id"] = candidate_id

        # Repository calls — no SQL in this file
        candidate_repo.save(candidate_id, final_output_state)
        intake_repo.mark_evaluated(candidate_id)

        logger.info(f"Background evaluation completed: {candidate_id}")
        PROGRESS_STORE[candidate_id]["status"] = "completed"

    except Exception as pipeline_err:
        logger.error(f"Background evaluation error: {pipeline_err}")
        PROGRESS_STORE[candidate_id]["status"] = "failed"
        PROGRESS_STORE[candidate_id]["error"] = f"Pipeline execution error: {pipeline_err}"


@app.get("/intake/{candidate_id}/progress", status_code=status.HTTP_200_OK)
def get_evaluation_progress(
    request: Request,
    candidate_id: str,
) -> Dict[str, Any]:
    """Returns live streaming progress. Falls back to DB check on server restart."""
    if candidate_id not in PROGRESS_STORE:
        intake = get_intake_repo(request).get_by_id(candidate_id)
        if intake and intake.get("status") == "evaluated":
            return {"status": "completed", "events": ["Evaluation already complete"]}
        return {"status": "not_started", "events": []}
    return PROGRESS_STORE[candidate_id]


# ==============================================================================
# Candidate / Report Routes
# ==============================================================================

@app.get("/candidates", status_code=status.HTTP_200_OK)
def list_candidates(request: Request) -> List[Dict[str, Any]]:
    """
    BEFORE: called get_all_candidates() from services/database.py
    AFTER:  calls candidate_repo.get_all()
    """
    return get_candidate_repo(request).get_all()


@app.get("/candidates/{candidate_id}/report", status_code=status.HTTP_200_OK)
def get_report(request: Request, candidate_id: str) -> Any:
    """
    BEFORE: called get_candidate_report() from services/database.py
    AFTER:  calls candidate_repo.get_by_id()
    """
    report = get_candidate_repo(request).get_by_id(candidate_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found.",
        )
    return report


@app.get("/candidates/{candidate_id}/audit", status_code=status.HTTP_200_OK)
def get_audit_trail(
    request: Request,
    candidate_id: str,
) -> List[Dict[str, Any]]:
    """
    BEFORE: called get_decision_audit() from services/database.py
    AFTER:  calls candidate_repo.get_decision_audit()
    """
    audit = get_candidate_repo(request).get_decision_audit(candidate_id)
    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit records found for '{candidate_id}'.",
        )
    return audit


@app.patch("/candidates/{candidate_id}/decision", status_code=status.HTTP_200_OK)
def patch_decision(
    request: Request,
    candidate_id: str,
    payload: DecisionPatchPayload,
) -> Dict[str, str]:
    """
    Updates the hiring decision and writes an audit trail entry.

    BEFORE: called update_hiring_decision() from services/database.py
    AFTER:  calls candidate_repo.update_decision()

    The audit trail logic lives inside update_decision() — it is a
    domain rule, not a route concern. This route only validates the
    HTTP input and delegates.
    """
    updated = get_candidate_repo(request).update_decision(
        candidate_id=candidate_id,
        new_decision=payload.decision,
        changed_by="hiring_manager",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found.",
        )
    return {
        "candidate_id": candidate_id,
        "decision_status": payload.decision,
        "message": "Hiring decision recorded and audit trail updated.",
    }