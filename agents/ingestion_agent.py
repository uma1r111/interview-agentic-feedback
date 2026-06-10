import uuid
import logging
from typing import Dict, Any, Tuple
from models.candidate import CandidateBundle
from services.test_processor import TestProcessorService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IngestionAgent")


class IngestionAgent:
    """
    Validates unstructured application payload entries, utilizes the programmatic
    test processor to evaluate metrics, and instantiates the graph state dictionary.
    """
    def __init__(self):
        self.test_processor = TestProcessorService()
        logger.info("Ingestion Agent successfully initialized with TestProcessorService dependency.")

    def process_intake(self, raw_payload: Dict[str, Any], mcq_responses: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        logger.info("Initiating structural intake validation for candidate payload...")
        try:
            data_to_validate = raw_payload.get("candidate_data", raw_payload) if "candidate_data" in raw_payload else raw_payload

            validated_bundle = CandidateBundle(**data_to_validate)

            # Direct call to TestProcessorService using the correct method signature.
            # role_type.value converts the RoleType enum to its string form so the
            # answer key registry lookup resolves correctly.
            test_result = self.test_processor.score_test_intake(
                role_type=validated_bundle.role_type.value,
                candidate_mcq_responses=mcq_responses,
                raw_programming_answers=validated_bundle.programming_answers
            )
            scored_mcq = test_result.mcq_score_out_of_five
            logger.info(f"MCQ programmatic scoring complete. Normalized score: {scored_mcq}/5.0")

            # P0-01 FIX: Append a UUID suffix to prevent candidate ID collisions.
            # Two candidates with the same name now get distinct IDs instead of
            # silently overwriting each other in the database.
            name_slug = validated_bundle.candidate_name.lower().replace(" ", "_")
            unique_suffix = str(uuid.uuid4())[:8]
            candidate_id = f"cand_{name_slug}_{unique_suffix}"

            output_state = {
                "candidate_id":        candidate_id,
                "candidate_name":      validated_bundle.candidate_name,
                "role_type":           validated_bundle.role_type,
                "raw_cv":              validated_bundle.raw_cv,
                "mcq_score":           scored_mcq,
                "programming_answers": validated_bundle.programming_answers,
                "session1_transcript": validated_bundle.session1_transcript,
                "session2_transcript": validated_bundle.session2_transcript
            }
            return output_state, True

        except Exception as validation_err:
            error_msg = f"Intake payload structural mismatch or validation error: {str(validation_err)}"
            logger.error(error_msg)
            return {"error": error_msg}, False