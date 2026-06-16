import uuid
import logging
from typing import Dict, Any, Tuple
from models.candidate import CandidateBundle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IngestionAgent")


class IngestionAgent:
    """
    Validates the candidate payload bundle and instantiates the global pipeline state.

    In the new file-based intake system, MCQ and programming answers are uploaded as raw
    documents and evaluated by dedicated checker agents later in the pipeline.
    This agent no longer performs any scoring — it only validates the bundle structure
    and builds the initial state dict.
    """
    def __init__(self):
        logger.info("Ingestion Agent initialized.")

    def process_intake(self, raw_payload: Dict[str, Any], mcq_responses: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        logger.info("Initiating structural intake validation for candidate payload...")
        try:
            data_to_validate = raw_payload.get("candidate_data", raw_payload) if "candidate_data" in raw_payload else raw_payload

            validated_bundle = CandidateBundle(**data_to_validate)

            # Generate a unique candidate ID (collision-safe UUID suffix)
            name_slug = validated_bundle.candidate_name.lower().replace(" ", "_")
            unique_suffix = str(uuid.uuid4())[:8]
            candidate_id = f"cand_{name_slug}_{unique_suffix}"

            output_state = {
                "candidate_id":        candidate_id,
                "candidate_name":      validated_bundle.candidate_name,
                "role_type":           validated_bundle.role_type,
                "raw_cv":              validated_bundle.raw_cv,
                "mcq_score":           validated_bundle.mcq_score,   # 0.0 placeholder — MCQ Agent will score
                "programming_answers": validated_bundle.programming_answers,
                "session1_transcript": validated_bundle.session1_transcript,
                "session2_transcript": validated_bundle.session2_transcript,
            }
            logger.info(f"Intake validated. candidate_id={candidate_id} | role={validated_bundle.role_type}")
            return output_state, True

        except Exception as validation_err:
            error_msg = f"Intake payload structural mismatch or validation error: {str(validation_err)}"
            logger.error(error_msg)
            return {"error": error_msg}, False