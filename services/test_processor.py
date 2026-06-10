import logging
from typing import Dict, List
from pydantic import BaseModel, Field

logger = logging.getLogger("TestProcessorService")

# ==============================================================================
# MCQ Answer Key Registry
# ==============================================================================

AI_ANSWER_KEY = {
    "q1_decision_trees":       "A",
    "q2_regularization":       "C",
    "q3_quantization":         "B",
    "q4_rag_context":          "D",
    "q5_activation_functions": "A"
}

# P0-02 FIX: Placeholder answer keys for SWE, BA, and Trainee role types.
# Previously only "AI" was registered — all other roles silently fell back
# to the AI key and scored against entirely wrong questions.
# Replace these placeholder dicts with real question/answer mappings when
# SWE, BA, and Trainee pre-interview tests are defined.
SWE_ANSWER_KEY: Dict[str, str] = {}    # TODO: populate when SWE test is defined
BA_ANSWER_KEY: Dict[str, str] = {}     # TODO: populate when BA test is defined
TRAINEE_ANSWER_KEY: Dict[str, str] = {} # TODO: populate when Trainee test is defined


class TestAssessmentResult(BaseModel):
    """Strongly-typed output model for processed pre-interview test results."""
    mcq_percentage: float = Field(..., description="Calculated percentage grade for MCQ section")
    mcq_score_out_of_five: float = Field(..., description="Normalized score mapped to a 5-point evaluation scale")
    processed_programming_submissions: List[str] = Field(..., description="Cleaned and prepared coding answers")


class TestProcessorService:
    """
    Programmatically grades MCQ responses against role-specific answer key registries
    and sanitizes programming submissions for downstream agent consumption.
    """
    def __init__(self):
        self.answer_key_registry = {
            "AI":      AI_ANSWER_KEY,
            "SWE":     SWE_ANSWER_KEY,
            "BA":      BA_ANSWER_KEY,
            "Trainee": TRAINEE_ANSWER_KEY,
        }
        logger.info("TestProcessorService initialized with active answer key registries.")

    def score_test_intake(
        self,
        role_type: str,
        candidate_mcq_responses: Dict[str, str],
        raw_programming_answers: List[str]
    ) -> TestAssessmentResult:
        """
        Validates, scores, and transforms a candidate's pre-interview test bundle.

        Args:
            role_type: Target role string (e.g., 'AI', 'SWE') to fetch correct answer key.
            candidate_mcq_responses: Key-value map of question IDs to candidate selections.
            raw_programming_answers: List of raw string answers submitted for coding questions.

        Returns:
            TestAssessmentResult: Validated object containing grades and clean code submissions.
        """
        logger.info(f"Beginning automatic test processing for role type: {role_type}")

        # Fetch the correct answer key for this role type
        active_key = self.answer_key_registry.get(role_type)

        if active_key is None:
            # Unknown role type entirely — log a clear error, do not silently fallback
            logger.error(
                f"Unknown role type '{role_type}' — no answer key registered. "
                f"MCQ score will be 0. Add this role to the answer_key_registry."
            )
            active_key = {}
        elif len(active_key) == 0:
            # Known role but answer key is a placeholder (not yet populated)
            logger.warning(
                f"Answer key for role '{role_type}' is empty (placeholder not yet populated). "
                f"MCQ score will be 0. Populate the answer key in test_processor.py."
            )

        # Programmatic grading loop
        total_questions = len(active_key)
        correct_matches = 0

        for q_id, correct_answer in active_key.items():
            candidate_selection = candidate_mcq_responses.get(q_id)
            if candidate_selection and candidate_selection.strip().upper() == correct_answer.upper():
                correct_matches += 1
            else:
                logger.debug(f"Incorrect or missing response for question: {q_id}.")

        # Normalize to 5-point scale
        if total_questions > 0:
            mcq_percentage = (correct_matches / total_questions) * 100.0
            normalized_score = (correct_matches / total_questions) * 5.0
        else:
            mcq_percentage = 0.0
            normalized_score = 0.0

        logger.info(f"MCQ auto-grading complete. Score: {correct_matches}/{total_questions} ({mcq_percentage:.1f}%).")

        # Sanitize code submissions — strip leading/trailing whitespace while
        # preserving interior indentation for accurate code quality evaluation
        sanitized_submissions = [code.strip() for code in raw_programming_answers]

        return TestAssessmentResult(
            mcq_percentage=mcq_percentage,
            mcq_score_out_of_five=normalized_score,
            processed_programming_submissions=sanitized_submissions
        )