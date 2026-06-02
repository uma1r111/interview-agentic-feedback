import logging
from typing import Dict, Any, Tuple
from agents.base_agent import BaseAgent
from models.evaluation import EvalScore

# Setup robust system logger tracking channel
logger = logging.getLogger("ProblemSolvingAgent")

class ProblemSolvingAgent(BaseAgent):
    """
    Evaluation agent specialized in assessing a candidate's cognitive framework,
    problem decomposition skills, edge-case mitigation, and analytical adaptability.
    """
    def __init__(self):
        super().__init__()
        logger.info("Production-tier Problem Solving Analysis Agent initialized successfully.")

    def evaluate_problem_solving(self, session1_transcript: str) -> Tuple[EvalScore, Dict[str, int]]:
        """
        Extracts and analyzes candidate problem-solving metrics strictly from the 
        Session 1 technical transcript dialogue boundaries.
        
        Args:
            session1_transcript: The diarized dialogue data stream from the technical panel.
            
        Returns:
            Tuple[EvalScore, token_metadata]: Strongly typed score payload and token audit telemetry.
        """
        logger.info("Executing analytical problem-solving assessment on Session 1 transcript...")

        system_prompt = (
            "You are an expert Principal AI Researcher and Cognitive Evaluation Specialist.\n"
            "Your objective is to analyze the candidate's core problem-solving framework and structural reasoning "
            "based ONLY on the conversational data provided inside the Session 1 transcript.\n\n"
            "Assess the candidate across these explicit cognitive behaviors:\n"
            "1. Problem Decomposition: Does the candidate break down large, open-ended systems or architectural problems "
            "into clear, modular, and step-by-step components?\n"
            "2. Edge Case & Constraint Awareness: Does the candidate naturally proactively flag bottlenecks, performance limitations, "
            "or edge conditions (e.g., latency spikes, token capacity boundaries, caching overheads)?\n"
            "3. Adaptability: How does the candidate handle design challenges or framework shifts when technical trade-offs are pushed?\n\n"
            "CRITICAL: Base your analysis entirely on explicit facts and conversational exchanges in the text. "
            "Do not infer, over-extrapolate, or assume behaviors not documented.\n\n"
            "Enforce strict conformity with this exact structured payload schema configuration response:\n"
            "- score: An integer value between 1 (weak analytical decomposition) and 5 (exceptional structural engineering thinking).\n"
            "- justification: Exactly a crisp, 2-sentence rationale outlining the core reasons for the score assignment.\n"
            "- evidence: Extract a direct verbatim quote from the candidate's dialogue that explicitly showcases their reasoning or edge-case handling."
        )

        user_prompt = f"Here is the Session 1 interview transcript dialogue stream to evaluate:\n\n{session1_transcript}"

        # Execute structured LLM transaction forced to populate the EvalScore schema model
        eval_output, token_meta = self.call_llm_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=EvalScore
        )

        # Defensive Processing Post-Invocation Guardrail
        if not eval_output:
            logger.error("Generative transaction trace error encountered during problem-solving assessment loop.")
            eval_output = EvalScore(
                score=1,
                justification="Problem solving assessment pipeline was forced into baseline mitigation due to generation runtime failures.",
                evidence="N/A"
            )

        return eval_output, token_meta