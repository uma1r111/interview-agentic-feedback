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

    def process_intake(self, raw_payload: Dict[str, Any], mcq_responses: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        logger.info("Initiating structural intake validation for candidate payload...")
        try:
            # If the payload arrives nested under a candidate_data dictionary wrapper, isolate it
            data_to_validate = raw_payload.get("candidate_data", raw_payload) if "candidate_data" in raw_payload else raw_payload
            
            # Structurally validate inputs against our CandidateBundle constraints
            from models.candidate import CandidateBundle
            validated_bundle = CandidateBundle(**data_to_validate)
            
            # Direct call to TestProcessorService using the correct method signature.
            # role_type.value converts the RoleType enum to its string form ("AI", "SWE", etc.)
            # so the answer key registry lookup inside score_test_intake resolves correctly.
            test_result = self.test_processor.score_test_intake(
                role_type=validated_bundle.role_type.value,
                candidate_mcq_responses=mcq_responses,
                raw_programming_answers=validated_bundle.programming_answers
            )
            scored_mcq = test_result.mcq_score_out_of_five
            logger.info(f"MCQ programmatic scoring complete. Normalized score: {scored_mcq}/5.0")
            # Compile the clean flat state output dict object mapping cleanly to global channels
            output_state = {
                "candidate_id": f"cand_{validated_bundle.candidate_name.lower().replace(' ', '_')}",
                "candidate_name": validated_bundle.candidate_name,
                "role_type": validated_bundle.role_type,
                "mcq_score": scored_mcq,
                "programming_answers": validated_bundle.programming_answers,
                "session1_transcript": validated_bundle.session1_transcript,
                "session2_transcript": validated_bundle.session2_transcript
            }
            return output_state, True
            
        except Exception as validation_err:
            error_msg = f"Intake payload structural mismatch or validation error: {str(validation_err)}"
            logger.error(error_msg)
            return {"error": error_msg}, False