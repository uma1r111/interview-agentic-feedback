import json
import logging
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, status

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
)
from services.pdf_extractor import PDFExtractorService

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
    """
    logger.info(f"API: Received pipeline evaluation request for candidate: {candidate_name}")

    # 1. Validate CV file type
    if cv_file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{cv_file.content_type}'. Only PDF files are accepted."
        )

    # 2. Extract text from the uploaded CV PDF
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

    # 3. Parse the MCQ selections JSON string sent as a form field
    try:
        mcq_selections_dict = json.loads(mcq_selections)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='mcq_selections must be a valid JSON string. Example: {"q1": "A", "q2": "C"}'
        )

    # 4. Validate the full candidate bundle with Pydantic
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

    # 5. Build initial state and invoke the LangGraph pipeline
    try:
        initial_inputs = {
            "candidate_name":      candidate_bundle.candidate_name,
            "role_type":           candidate_bundle.role_type,
            "raw_cv":              candidate_bundle.raw_cv,
            "mcq_score":           candidate_bundle.mcq_score,
            "programming_answers": candidate_bundle.programming_answers,
            "session1_transcript": candidate_bundle.session1_transcript,
            "session2_transcript": candidate_bundle.session2_transcript,
            "raw_payload":         candidate_bundle.model_dump(),
            "mcq_responses":       mcq_selections_dict
        }

        final_output_state = interview_graph.invoke(initial_inputs)

        logger.info(f"Final state keys: {list(final_output_state.keys())}")
        logger.info(f"feedback_report: {final_output_state.get('feedback_report')}")
        logger.info(f"bias_clear: {final_output_state.get('bias_clear')}")
        logger.info(f"error: {final_output_state.get('error')}")

        if final_output_state.get("error"):
            logger.error(f"API: Graph pipeline aborted: {final_output_state['error']}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Graph processing halted: {final_output_state['error']}"
            )

        candidate_id = final_output_state["candidate_id"]
        save_candidate(candidate_id, final_output_state)
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