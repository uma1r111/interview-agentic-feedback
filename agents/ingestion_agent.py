import uuid
import logging
from typing import Dict, Any, Tuple
from models.candidate import CandidateBundle, InterviewState

# Setup modular logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IngestionAgent")

class IngestionAgent:
    """
    Validates unstructured application payload entries, maps raw bundles 
    into strictly typed schemas, and instantiates the graph state dictionary.
    """
    def __init__(self):
        logger.info("Ingestion Agent successfully initialized.")

    def process_intake(self, raw_payload: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """
        Parses and validates the raw candidate payload data.
        
        Returns:
            Tuple[DictState, success_boolean]:
                If success is True, returns a populated InterviewState dict tree.
                If success is False, returns a dictionary containing a descriptive error payload.
        """
        try:
            logger.info("Initiating structural intake validation for candidate payload...")
            
            # 1. Enforce strict Pydantic model structural validation
            # This handles missing fields, incorrect types, and invalid enums automatically.
            validated_bundle = CandidateBundle(**raw_payload)
            logger.info(f"Intake schema successfully validated for candidate: {validated_bundle.candidate_name}")

            # 2. Assemble and initialize the LangGraph state matrix
            # Instantiating as a dict to natively fit LangGraph state channels while maintaining schema compliance.
            state = {
                "candidate_id": f"cand_{uuid.uuid4().hex[:8]}",
                "candidate_name": validated_bundle.candidate_name,
                "role_type": validated_bundle.role_type,
                "mcq_score": validated_bundle.mcq_score,
                "programming_answers": validated_bundle.programming_answers,
                "session1_transcript": validated_bundle.session1_transcript,
                "session2_transcript": validated_bundle.session2_transcript,
                
                # Downstream tracking slots initialized to default states
                "communication_score": None,
                "technical_score": None,
                "problem_solving_score": None,
                "cultural_score": None,
                
                # Governance gates initialized to default states
                "bias_log": None,
                "bias_clear": False,  # Hard locked until explicitly released by the Bias Detection node
                "feedback_report": None,
                "error": None
            }
            
            return state, True

        except Exception as validation_error:
            error_msg = f"Intake payload structural mismatch or validation error: {str(validation_error)}"
            logger.error(error_msg)
            
            # Return failure state dict tree mapping error diagnostics cleanly back to the orchestrator
            failure_state = {
                "candidate_id": "ERR_INGEST_FAIL",
                "error": error_msg
            }
            return failure_state, False