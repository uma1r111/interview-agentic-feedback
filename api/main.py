import logging
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, status

from api.schemas import DecisionPatchPayload, IntakeRequestPayload
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API_Server")

settings = get_settings()

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description="Backend microservice serving multi-agent evaluation DAG pipelines via LangGraph."
)

interview_graph = create_interview_graph()


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
def submit_candidate_intake(payload: IntakeRequestPayload) -> Dict[str, str]:
    try:
        logger.info(f"API: Received evaluation request for candidate: {payload.candidate_data.candidate_name}")

        initial_inputs = {
            "candidate_name": payload.candidate_data.candidate_name,
            "role_type": payload.candidate_data.role_type,
            "mcq_score": payload.candidate_data.mcq_score,
            "programming_answers": payload.candidate_data.programming_answers,
            "session1_transcript": payload.candidate_data.session1_transcript,
            "session2_transcript": payload.candidate_data.session2_transcript,
            "raw_payload": payload.candidate_data.model_dump(),
            "mcq_responses": payload.mcq_selections
        }

        final_output_state = interview_graph.invoke(initial_inputs)

        logger.info(f"Final state keys: {list(final_output_state.keys())}")
        logger.info(f"feedback_report: {final_output_state.get('feedback_report')}")
        logger.info(f"bias_clear: {final_output_state.get('bias_clear')}")
        logger.info(f"error: {final_output_state.get('error')}")

        if final_output_state.get("error"):
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
    except Exception as e:
        logger.error(f"API Fatal Exception: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal graph runtime execution error: {str(e)}"
        )


@app.get("/candidates", status_code=status.HTTP_200_OK)
def list_candidates() -> List[Dict[str, Any]]:
    return get_all_candidates()


@app.get("/candidates/{candidate_id}/report", status_code=status.HTTP_200_OK)
def get_report(candidate_id: str) -> Any:
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