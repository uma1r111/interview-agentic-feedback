import logging
from typing import Dict, Any, List, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("TestProcessorService")

# ==============================================================================
# MCQ Answer Key Registry (Configured for the AI Trainee Track)
# ==============================================================================
AI_TRAINEE_ANSWER_KEY = {
    "q1_decision_trees": "A",
    "q2_regularization": "C",
    "q3_quantization": "B",
    "q4_rag_context": "D",
    "q5_activation_functions": "A"
}

class TestAssessmentResult(BaseModel):
    """Robust, strongly-typed domain model output for processed tests."""
    mcq_percentage: float = Field(..., description="Calculated percentage grade for MCQ section")
    mcq_score_out_of_five: float = Field(..., description="Normalized score mapped to a 5-point evaluation scale")
    processed_programming_submissions: List[str] = Field(..., description="Cleaned and prepared coding answers")

class TestProcessorService:
    """
    Enterprise-grade test intake processing engine. Programmatically grades structured 
    MCQs against registries and extracts raw code segments for downstream DAG node consumption.
    """
    def __init__(self):
        # In a production layout, answer keys could be loaded via an internal DB session.
        self.answer_key_registry = {
            "AI": AI_TRAINEE_ANSWER_KEY
        }
        logger.info("TestProcessorService initialized with active answer key registries.")

    def score_test_intake(
        self, 
        role_type: str, 
        candidate_mcq_responses: Dict[str, str], 
        raw_programming_answers: List[str]
    ) -> TestAssessmentResult:
        """
        Validates, scores, and transforms a candidate's digital testing intake bundle.
        
        Args:
            role_type: Target role string (e.g., 'AI', 'SWE') to fetch correct answer key.
            candidate_mcq_responses: Key-value map of question IDs to candidate selections.
            raw_programming_answers: List of raw string answers submitted for coding questions.
            
        Returns:
            TestAssessmentResult: Validated object containing grades and clean string blocks.
        """
        logger.info(f"Beginning automatic test processing slice for role type: {role_type}")

        # 1. Fetch appropriate answer key from the registry
        active_key = self.answer_key_registry.get(role_type)
        if not active_key:
            logger.warning(f"No specific answer key found for role '{role_type}'. Defaulting to standard baseline.")
            active_key = AI_TRAINEE_ANSWER_KEY

        # 2. Programmatic grading loop
        total_questions = len(active_key)
        correct_matches = 0

        for q_id, correct_answer in active_key.items():
            candidate_selection = candidate_mcq_responses.get(q_id)
            if candidate_selection and candidate_selection.strip().upper() == correct_answer.upper():
                correct_matches += 1
            else:
                logger.debug(f"Incorrect or missing response caught for field {q_id}.")

        # 3. Calculate metrics and normalize scores to a 5-point scale
        mcq_percentage = (correct_matches / total_questions) * 100.0 if total_questions > 0 else 0.0
        normalized_score = (correct_matches / total_questions) * 5.0 if total_questions > 0 else 0.0
        
        logger.info(f"MCQ auto-grading complete. Score: {correct_matches}/{total_questions} ({mcq_percentage}%).")

        # 4. Clean and prepare code answers
        # Strips out malicious or broken leading/trailing spaces while preserving interior structural indentation.
        sanitized_code_submissions = [code.strip() for code in raw_programming_answers]

        return TestAssessmentResult(
            mcq_percentage=mcq_percentage,
            mcq_score_out_of_five=normalized_score,
            processed_programming_submissions=sanitized_code_submissions
        )