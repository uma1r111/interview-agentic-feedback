import uuid
import logging
from typing import Dict, Any, Tuple
from models.candidate import CandidateBundle
from services.test_processor import TestProcessorService

# Setup modular logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IngestionAgent")

class IngestionAgent:
    """
    Validates unstructured application payload entries, utilizes the programmatic 
    test processor to evaluate metrics, and instantiates the graph state dictionary.
    """
    def __init__(self):
        # Instantiate the robust test parsing engine cleanly upon setup
        self.test_processor = TestProcessorService()
        logger.info("Ingestion Agent successfully initialized with TestProcessorService dependency.")

    def process_intake(self, raw_payload: Dict[str, Any], mcq_responses: Dict[str, str]) -> Tuple[Dict[str, Any], bool]:
        """
        Parses, programmatically evaluates, and validates candidate payload data.
        
        Args:
            raw_payload: The base metadata, text transcripts, and raw programming answers.
            mcq_responses: The exact key-value multiple choice selections submitted.
            
        Returns:
            Tuple[DictState, success_boolean]:
                If success is True, returns a populated InterviewState dict tree with evaluated metrics.
                If success is False, returns a dictionary containing a descriptive error payload.
        """
        try:
            logger.info("Initiating structural intake validation for candidate payload...")
            
            # 1. Enforce strict Pydantic model structural validation for base fields
            # This cleanly handles missing fields, incorrect types, and invalid enums automatically.
            validated_bundle = CandidateBundle(**raw_payload)
            logger.info(f"Intake schema successfully validated for candidate: {validated_bundle.candidate_name}")

            # 2. Run robust programmatic scoring for MCQs and sanitize raw source code answers
            test_assessment = self.test_processor.score_test_intake(
                role_type=validated_bundle.role_type,
                candidate_mcq_responses=mcq_responses,
                raw_programming_answers=validated_bundle.programming_answers
            )

            # 3. Assemble and initialize the state dictionary
            # Instantiating as a dict to natively fit LangGraph state channels while maintaining schema compliance.
            state = {
                "candidate_id": f"cand_{uuid.uuid4().hex[:8]}",
                "candidate_name": validated_bundle.candidate_name,
                "role_type": validated_bundle.role_type,
                "session1_transcript": validated_bundle.session1_transcript,
                "session2_transcript": validated_bundle.session2_transcript,
                
                # Injected programmatic evaluation scores from the TestProcessorService
                "mcq_score": test_assessment.mcq_score_out_of_five,
                "programming_answers": test_assessment.processed_programming_submissions,
                
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