import json
import logging
import os
import shutil
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, status

from api.schemas import DecisionPatchPayload
from models.candidate import CandidateBundle
from models.enums import RoleType, Decision
from config.settings import get_settings
from graph.pipeline import create_interview_graph
from services.database import (
    get_all_candidates,
    get_candidate_report,
    get_decision_audit,
    init_database,
    save_candidate,
    update_hiring_decision,
    create_candidate_intake,
    patch_intake_candidate,
    mark_intake_evaluated,
    delete_intake_candidate,
    get_all_intake_candidates,
    get_intake_candidate,
    find_intake_by_name,
)
from services.pdf_extractor import PDFExtractorService
from services.file_extractor import FileExtractorService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API_Server")

settings = get_settings()

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description="Backend microservice serving multi-agent evaluation DAG pipelines via LangGraph."
)

interview_graph = create_interview_graph()
pdf_extractor = PDFExtractorService()
file_extractor = FileExtractorService()


# ==============================================================================
# Application Startup
# ==============================================================================

@app.on_event("startup")
def on_startup():
    init_database()


# ==============================================================================
# Routes
# ==============================================================================

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, str]:
    return {"status": "healthy", "service": "interview-agentic-feedback"}


# ==============================================================================
# Intake Routes — Two-Step Structured Candidate Registration
# ==============================================================================

# ---------------------------------------------------------------------------
# Helper: write candidate_info.json to the candidate's fixtures folder
# ---------------------------------------------------------------------------
def _write_candidate_info_json(folder_path: str, data: dict) -> None:
    """Serialises candidate metadata to disk so the folder is self-contained."""
    info_path = os.path.join(folder_path, "candidate_info.json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@app.post("/intake/create", status_code=status.HTTP_201_CREATED)
def intake_create_candidate(
    candidate_name: str = Form(..., description="Full name of the candidate"),
    role_type: str = Form(..., description="Role enum value: SWE | AI | BA | Trainee"),
) -> Dict[str, str]:
    """
    Step 1: Registers a new candidate in the intake system.
    Creates a unique candidate_id, makes their fixtures folder,
    writes candidate_info.json, and inserts a DB row with status='awaiting_files'.
    Returns the candidate_id for use in subsequent Step 2 upload calls.
    """
    # Validate role_type
    try:
        RoleType(role_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role_type '{role_type}'. Valid values: SWE, AI, BA, Trainee"
        )

    name_slug = candidate_name.lower().replace(" ", "_")
    unique_suffix = str(uuid.uuid4())[:8]
    candidate_id = f"cand_{name_slug}_{unique_suffix}"

    folder_path = os.path.join("fixtures", "candidates", candidate_id)

    create_candidate_intake(
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        role_type=role_type,
    )

    _write_candidate_info_json(folder_path, {
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "role_type": role_type,
        "status": "awaiting_files",
    })

    logger.info(f"Intake Step 1 complete — candidate registered: {candidate_id}")
    return {
        "candidate_id": candidate_id,
        "status": "awaiting_files",
        "message": f"Candidate '{candidate_name}' registered. Upload files to complete intake."
    }


@app.get("/intake/check-duplicate", status_code=status.HTTP_200_OK)
def check_duplicate_name(
    name: str = Query(..., description="Candidate name to check for duplicates")
) -> Dict[str, Any]:
    """
    Checks whether any existing intake record has the same candidate name.
    Returns a list of matching records so the dashboard can warn HR before creating.
    """
    matches = find_intake_by_name(name)
    return {
        "name": name,
        "has_duplicates": len(matches) > 0,
        "existing_records": matches,
    }


@app.get("/intake/candidates", status_code=status.HTTP_200_OK)
def list_intake_candidates() -> List[Dict[str, Any]]:
    """Returns all intake candidate rows (all statuses) for the intake queue dashboard."""
    return get_all_intake_candidates()


@app.delete("/intake/{candidate_id}", status_code=status.HTTP_200_OK)
def delete_intake_record(candidate_id: str) -> Dict[str, str]:
    """
    Deletes an intake candidate record that is still in 'awaiting_files' status.
    Removes:
      - The DB row from candidate_intake
      - The entire fixtures/candidates/{candidate_id}/ folder and its contents

    Raises 409 if the candidate is 'ready' or 'evaluated' — those records are
    protected and must not be silently discarded.
    """
    intake = get_intake_candidate(candidate_id)
    if not intake:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No intake record found for '{candidate_id}'."
        )
    if intake["status"] != "awaiting_files":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete candidate '{candidate_id}' with status '{intake['status']}'. "
                "Only 'awaiting_files' candidates can be deleted."
            )
        )

    # Delete DB row
    delete_intake_candidate(candidate_id)

    # Remove fixtures folder (best-effort — don't fail if already gone)
    folder_path = os.path.join("fixtures", "candidates", candidate_id)
    if os.path.isdir(folder_path):
        shutil.rmtree(folder_path)
        logger.info(f"Deleted fixtures folder: {folder_path}")
    else:
        logger.warning(f"Fixtures folder not found (already removed?): {folder_path}")

    logger.info(f"Intake candidate deleted: {candidate_id} ({intake['candidate_name']})")
    return {
        "candidate_id": candidate_id,
        "message": f"Candidate '{intake['candidate_name']}' deleted from DB and file system."
    }


@app.get("/intake/{candidate_id}", status_code=status.HTTP_200_OK)
def get_intake_record(candidate_id: str) -> Dict[str, Any]:
    """Returns the full intake record for a single candidate (all fields)."""
    record = get_intake_candidate(candidate_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No intake record found for '{candidate_id}'."
        )
    return record


@app.post("/intake/{candidate_id}/upload", status_code=status.HTTP_200_OK)
async def intake_upload_files(
    candidate_id: str,
    cv_file:       Optional[UploadFile] = File(None, description="CV — PDF only"),
    session1_file: Optional[UploadFile] = File(None, description="Session 1 transcript — PDF, TXT, or DOCX"),
    session2_file: Optional[UploadFile] = File(None, description="Session 2 transcript — PDF, TXT, or DOCX"),
    mcq_file:      Optional[UploadFile] = File(None, description="MCQ results document — PDF, TXT, or DOCX"),
    prog_file_1:   Optional[UploadFile] = File(None, description="Programming Answers document (both Q1 & Q2) — PDF, TXT, or DOCX"),
) -> Dict[str, Any]:
    """
    Partial/incremental upload endpoint — all files are optional.
    Each call saves only the files provided and patches those fields in the DB.
    Status auto-recalculates: 'ready' when all 7 fields are present,
    'awaiting_files' otherwise.

    HR can call this any number of times to upload documents incrementally
    or replace a previously saved file.
    """
    intake = get_intake_candidate(candidate_id)
    if not intake:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No intake record found for '{candidate_id}'. Run Step 1 first."
        )
    if intake["status"] == "evaluated":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Candidate '{candidate_id}' has already been evaluated and cannot be modified."
        )

    folder_path = os.path.join("fixtures", "candidates", candidate_id)
    os.makedirs(folder_path, exist_ok=True)

    patch_fields: Dict[str, Any] = {}
    saved_files: Dict[str, str] = {}

    # ── CV ────────────────────────────────────────────────────────────────────
    if cv_file and cv_file.filename:
        if not cv_file.filename.lower().endswith(".pdf") \
                and cv_file.content_type not in ("application/pdf", "application/octet-stream"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"CV must be a PDF. Received: '{cv_file.filename}'."
            )
        cv_bytes = await cv_file.read()
        cv_path = os.path.join(folder_path, "cv.pdf")
        with open(cv_path, "wb") as f:
            f.write(cv_bytes)
        patch_fields["cv_path"] = cv_path
        saved_files["cv"] = cv_path
        logger.info(f"CV saved: {cv_path}")

    # ── Session 1 ─────────────────────────────────────────────────────────────
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
        logger.info(f"Session 1 saved: {s1_path}")

    # ── Session 2 ─────────────────────────────────────────────────────────────
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
        logger.info(f"Session 2 saved: {s2_path}")

    # ── MCQ (raw file save — no parsing at intake stage) ─────────────────────
    if mcq_file and mcq_file.filename:
        mcq_bytes = await mcq_file.read()
        mcq_ext = mcq_file.filename.rsplit(".", 1)[-1] if "." in mcq_file.filename else "bin"
        mcq_path = os.path.join(folder_path, f"mcq_answers.{mcq_ext}")
        with open(mcq_path, "wb") as f:
            f.write(mcq_bytes)
        patch_fields["mcq_path"] = mcq_path
        saved_files["mcq_answers"] = mcq_path
        logger.info(f"MCQ file saved: {mcq_path} ({len(mcq_bytes)} bytes) — will be scored during evaluation")

    # ── Programming Answers (single combined document — save file, store path) ─────
    if prog_file_1 and prog_file_1.filename:
        p1_bytes = await prog_file_1.read()
        p1_ext = prog_file_1.filename.rsplit(".", 1)[-1] if "." in prog_file_1.filename else "bin"
        p1_path = os.path.join(folder_path, f"programming_answers.{p1_ext}")
        with open(p1_path, "wb") as f:
            f.write(p1_bytes)
        patch_fields["programming_path"] = p1_path
        saved_files["programming_answers"] = p1_path
        logger.info(f"Programming answers saved: {p1_path} ({len(p1_bytes)} bytes) — will be evaluated by agent")

    if not patch_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files were provided. Include at least one file per call."
        )

    # ── Patch DB + refresh candidate_info.json ────────────────────────────────
    patch_intake_candidate(candidate_id, **patch_fields)
    updated = get_intake_candidate(candidate_id)

    _write_candidate_info_json(folder_path, {
        "candidate_id":       candidate_id,
        "candidate_name":     updated["candidate_name"],
        "role_type":          updated["role_type"],
        "mcq_path":           updated.get("mcq_path"),
        "programming_path":   updated.get("programming_path"),
        "cv_path":            updated.get("cv_path"),
        "session1_path":      updated.get("session1_path"),
        "session2_path":      updated.get("session2_path"),
        "status":             updated["status"],
    })

    logger.info(f"Upload complete for {candidate_id}: {list(saved_files.keys())} | status={updated['status']}")
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
def intake_run_evaluation(candidate_id: str) -> Dict[str, str]:
    """
    Step 3: Triggers the full LangGraph multi-agent evaluation pipeline
    for a candidate whose status is 'ready'. Reads all data from the
    candidate's fixtures folder and DB record. Saves result to the
    candidates table and marks intake status as 'evaluated'.
    """
    intake = get_intake_candidate(candidate_id)
    if not intake:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No intake record found for candidate_id '{candidate_id}'."
        )
    if intake["status"] != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Candidate '{candidate_id}' is not ready for evaluation. "
                f"Current status: '{intake['status']}'. "
                f"Complete file upload (Step 2) first."
            )
        )

    # -- Extract CV text from saved PDF --
    try:
        with open(intake["cv_path"], "rb") as f:
            pdf_bytes = f.read()
        raw_cv_text = pdf_extractor.extract_text(pdf_bytes)
    except Exception as cv_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CV PDF extraction failed: {str(cv_err)}"
        )

    # -- Read saved transcripts --
    try:
        with open(intake["session1_path"], "r", encoding="utf-8") as f:
            session1_transcript = f.read()
        with open(intake["session2_path"], "r", encoding="utf-8") as f:
            session2_transcript = f.read()
    except Exception as file_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to read transcript files: {str(file_err)}"
        )

    # -- Guard: verify all required file paths are present --
    missing = [
        field for field, val in [
            ("Programming Answers", intake.get("programming_path")),
            ("MCQ Answers",         intake.get("mcq_path")),
            ("CV",                  intake.get("cv_path")),
            ("Session 1 Transcript",intake.get("session1_path")),
            ("Session 2 Transcript",intake.get("session2_path")),
        ] if not val
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Candidate record is missing required files: {', '.join(missing)}. "
                "Please re-upload the missing documents in Step 2 and try again."
            )
        )

    # -- Read programming answers from saved file --
    try:
        with open(intake["programming_path"], "rb") as f:
            prog_bytes = f.read()
        programming_text = file_extractor.extract(
            prog_bytes,
            os.path.basename(intake["programming_path"]),
            None
        )
    except Exception as prog_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to read programming answers file: {str(prog_err)}"
        )

    try:
        candidate_bundle = CandidateBundle(
            candidate_name=intake["candidate_name"],
            role_type=RoleType(intake["role_type"]),
            raw_cv=raw_cv_text,
            mcq_score=0.0,              # placeholder — MCQ Agent will score during pipeline
            programming_answers=[
                programming_text,       # full answers doc text for Programming Agent
                programming_text,       # duplicate so downstream list access is safe
            ],
            session1_transcript=session1_transcript,
            session2_transcript=session2_transcript,
        )
    except Exception as validation_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Candidate bundle validation failed: {str(validation_err)}"
        )

    # -- Run the LangGraph pipeline --
    try:
        initial_inputs = {
            "candidate_name":      candidate_bundle.candidate_name,
            "role_type":           candidate_bundle.role_type,
            "raw_cv":              candidate_bundle.raw_cv,
            "mcq_score":           candidate_bundle.mcq_score,
            "mcq_path":            intake["mcq_path"],            # MCQ Agent reads the raw file
            "programming_path":    intake["programming_path"],   # Programming Agent reads the raw file
            "programming_answers": candidate_bundle.programming_answers,
            "session1_transcript": candidate_bundle.session1_transcript,
            "session2_transcript": candidate_bundle.session2_transcript,
            "raw_payload":         candidate_bundle.model_dump(),
            "mcq_responses":       {},                           # MCQ Agent will populate this
        }
        final_output_state = interview_graph.invoke(initial_inputs)
    except Exception as pipeline_err:
        logger.error(f"Intake evaluation pipeline error: {str(pipeline_err)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline execution error: {str(pipeline_err)}"
        )

    if final_output_state.get("error"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Pipeline aborted: {final_output_state['error']}"
        )

    # Use the same candidate_id so the intake and evaluation records are linked
    final_output_state["candidate_id"] = candidate_id
    save_candidate(candidate_id, final_output_state)
    mark_intake_evaluated(candidate_id)

    logger.info(f"Intake evaluation complete for: {candidate_id}")
    return {
        "candidate_id": candidate_id,
        "status": "evaluated",
        "message": "Multi-agent evaluation completed. Report is available in the dashboard."
    }


@app.get("/candidates", status_code=status.HTTP_200_OK)
def list_candidates() -> List[Dict[str, Any]]:
    """Returns lightweight candidate list for dashboard navigation."""
    return get_all_candidates()


@app.get("/candidates/{candidate_id}/report", status_code=status.HTTP_200_OK)
def get_report(candidate_id: str) -> Any:
    """Fetches the final structured evaluation feedback report for a candidate."""
    report = get_candidate_report(candidate_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found."
        )
    return report


@app.get("/candidates/{candidate_id}/audit", status_code=status.HTTP_200_OK)
def get_audit_trail(candidate_id: str) -> List[Dict[str, Any]]:
    """Returns the full decision audit trail for a candidate."""
    audit = get_decision_audit(candidate_id)
    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit records found for candidate '{candidate_id}'."
        )
    return audit


@app.patch("/candidates/{candidate_id}/decision", status_code=status.HTTP_200_OK)
def patch_decision(candidate_id: str, payload: DecisionPatchPayload) -> Dict[str, str]:
    """Updates a candidate's hiring decision. Only the decision column is updated."""
    updated = update_hiring_decision(candidate_id, payload.decision)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found."
        )
    return {
        "candidate_id": candidate_id,
        "decision_status": payload.decision,
        "message": "Hiring decision recorded and audit trail updated."
    }