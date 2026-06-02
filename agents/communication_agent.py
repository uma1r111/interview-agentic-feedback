import logging
from typing import Dict, Any, Tuple
from agents.base_agent import BaseAgent
from models.evaluation import EvalScore

logger = logging.getLogger("CommunicationAgent")

class CommunicationAgent(BaseAgent):
    """
    Evaluates candidate communication clarity, articulation, and confidence.
    Restricted entirely to analyzing the Session 1 interview transcript.
    """
    def __init__(self):
        super().__init__()
        logger.info("Communication Analysis Agent initialized.")

    def evaluate_communication(self, session1_transcript: str) -> Tuple[EvalScore, Dict[str, int]]:
        """
        Analyzes the conversational properties of the candidate within Session 1.
        
        Returns:
            Tuple[EvalScore, token_metadata]: The structured evaluation model and usage diagnostics.
        """
        logger.info("Executing communication assessment on Session 1 transcript...")

        system_prompt = (
            "You are an expert technical interviewer and communication coach evaluating an applicant.\n"
            "Your objective is to analyze the candidate's conversational behavior based ONLY on the provided "
            "Session 1 transcript. Do not assume or extrapolate details outside this text.\n\n"
            "Assess the candidate across these criteria:\n"
            "1. Clarity & Articulation: Does the candidate explain complex ideas simply and structuredly?\n"
            "2. Confidence & Tone: Does the candidate use clear, professional, and definitive terminology?\n"
            "3. Engagement: Does the candidate address the interviewers' questions directly without rambling?\n\n"
            "You must return a structured response matching the required schema properties:\n"
            "- score: An integer value between 1 (poor) and 5 (exceptional).\n"
            "- justification: Exactly a crisp, 2-sentence rationale explaining the score.\n"
            "- evidence: A direct word-for-word quote from the candidate's dialogue that supports your scoring."
        )

        user_prompt = f"Here is the Session 1 interview transcript to analyze:\n\n{session1_transcript}"

        # Execute structured LLM call forced to populate the EvalScore schema model
        eval_output, token_meta = self.call_llm_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=EvalScore
        )

        if not eval_output:
            logger.error("Communication evaluation failed to generate output. Falling back to default baseline.")
            eval_output = EvalScore(
                score=1,
                justification="Failed to evaluate communication due to an internal generative engine failure. Requires manual auditing.",
                evidence="N/A"
            )

        return eval_output, token_meta