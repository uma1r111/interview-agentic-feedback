import os
import logging
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Any, List

# Core system schema and graph imports
from models.enums import RoleType, Decision
from models.candidate import CandidateBundle
from graph.pipeline import create_interview_graph

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

# ==============================================================================
# In-Memory Database / Cache Mock Ledger
# ==============================================================================
CANDIDATE_DB: Dict[str, Dict[str, Any]] = {}

# ==============================================================================
# API Ingestion Validation Models
# ==============================================================================

class IntakeRequestPayload(BaseModel):
    """Unified POST body bundle wrapping candidate profiles and digital test inputs."""
    candidate_data: CandidateBundle
    mcq_selections: Dict[str, str] = Field(
        ..., 
        description="Dictionary mapping question IDs to the candidate's exact raw answer selections"
    )

class DecisionPatchPayload(BaseModel):
    """Strict data payload covering human-override hiring actions."""
    decision: Decision

# ==============================================================================
# Functional Route Handlers
# ==============================================================================

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, str]:
    """Basic diagnostic heartbeat verifying system availability."""
    return {"status": "healthy", "service": "interview-agentic-feedback"}

@app.post("/candidates", status_code=status.HTTP_201_CREATED)
def submit_candidate_intake(payload: IntakeRequestPayload) -> Dict[str, str]:
    """
    Submits candidate payload, scores MCQs, and runs the multi-agent graph evaluation pipeline.
    """
    try:
        logger.info(f"API: Received pipeline evaluation request for candidate: {payload.candidate_data.candidate_name}")
        
        # FIX: Explicitly break out and pass the individual attributes at the root level 
        # so LangGraph's shared state maps them correctly right at invocation boot-up
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
        
        # Invoke the stateful LangGraph pipeline synchronously
        final_output_state = interview_graph.invoke(initial_inputs)

        logger.info(f"Final state keys: {list(final_output_state.keys())}")
        logger.info(f"feedback_report: {final_output_state.get('feedback_report')}")
        logger.info(f"bias_clear: {final_output_state.get('bias_clear')}")
        logger.info(f"bias_log: {final_output_state.get('bias_log')}")
        logger.info(f"error: {final_output_state.get('error')}")
        
        # Check if the ingestion node or downstream processing threw a fatal exception
        if final_output_state.get("error"):
            logger.error(f"API Ingestion Loop abort caught: {final_output_state['error']}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Graph processing halted: {final_output_state['error']}"
            )
            
        candidate_id = final_output_state["candidate_id"]
        CANDIDATE_DB[candidate_id] = final_output_state
        logger.info(f"API: Evaluation cycle completed. Candidate saved with ID: {candidate_id}")
        
        return {
            "candidate_id": candidate_id,
            "status": "compiled",
            "message": "Multi-agent evaluation and compliance bias checks completed successfully."
        }
        
    except HTTPException:
        raise
    except Exception as general_error:
        logger.error(f"API Fatal Exception: Failed to run applicant intake transaction: {str(general_error)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal graph runtime execution error: {str(general_error)}"
        )

@app.get("/candidates/{candidate_id}/report", status_code=status.HTTP_200_OK)
def get_compiled_feedback_report(candidate_id: str) -> Any:
    """Fetches the final structured, sanitized evaluation feedback report for a candidate."""
    candidate_record = CANDIDATE_DB.get(candidate_id)
    
    if not candidate_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate profile record for ID '{candidate_id}' not found in active data indices."
        )
        
    feedback_report = candidate_record.get("feedback_report")
    if not feedback_report:
        raise HTTPException(
            status_code=status.HTTP_204_NO_CONTENT,
            detail="State profile active but synthesized feedback report is not present or failed generation."
        )
        
    return feedback_report

@app.patch("/candidates/{candidate_id}/decision", status_code=status.HTTP_200_OK)
def patch_hiring_decision(candidate_id: str, payload: DecisionPatchPayload) -> Dict[str, str]:
    """Updates a candidate's file with the hiring manager's human-in-the-loop decision."""
    candidate_record = CANDIDATE_DB.get(candidate_id)
    
    if not candidate_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cannot append decision parameters. Candidate ID '{candidate_id}' not found."
        )
        
    # Programmatically apply the hiring decision to the nested compiled Pydantic FeedbackReport object
    feedback_report = candidate_record.get("feedback_report")
    if not feedback_report:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot update decision status because a valid feedback report has not been compiled."
        )
        
    # Modify the default HOLD attribute to the incoming manager state directive
    feedback_report.hiring_manager_decision = payload.decision
    logger.info(f"API: Human decision recorded cleanly for {candidate_id}. Status changed to: {payload.decision}")
    
    return {
        "candidate_id": candidate_id,
        "decision_status": payload.decision,
        "message": "Hiring decision successfully recorded and committed to candidate profile."
    }