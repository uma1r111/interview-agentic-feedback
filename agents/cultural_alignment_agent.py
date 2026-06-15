import logging
from typing import Dict, Any, Tuple
from agents.base_agent import BaseAgent
from models.evaluation import EvalScore

# Setup robust system logger tracking channel
logger = logging.getLogger("CulturalAlignmentAgent")

class CulturalAlignmentAgent(BaseAgent):
    """
    Evaluation agent specialized in parsing behavioral transcripts to assess values,
    collaboration paradigms, handling of deadlines, and long-term professional motivation.
    """
    def __init__(self):
        super().__init__()
        logger.info("Production-tier Cultural Alignment Agent initialized successfully.")

    def evaluate_cultural_alignment(self, session2_transcript: str) -> Tuple[EvalScore, Dict[str, int]]:
        """
        Extracts and analyzes candidate cultural alignment metrics strictly from the 
        Session 2 HR transcript dialogue boundaries.
        
        Args:
            session2_transcript: The diarized dialogue data stream from the HR interview panel.
            
        Returns:
            Tuple[EvalScore, token_metadata]: Strongly typed score payload and token audit telemetry.
        """
        logger.info("Executing behavioral cultural alignment assessment on Session 2 transcript...")

        system_prompt = (
            "You are an expert HR Director, Organizational Culture Consultant, and Talent Evaluator.\n"
            "Your objective is to thoroughly analyze the candidate's core behavioral attributes, values alignment, "
            "and professional operational style based ONLY on the provided Session 2 transcript.\n\n"
            "CRITICAL: Do not read, cross-reference, or assume anything regarding the candidate's technical skills, "
            "coding capabilities, or Session 1 performance. Focus solely on Session 2.\n\n"
            "Assess the candidate across these explicit cultural dimensions:\n"
            "1. Self-Awareness & Growth Mindset: Can the candidate accurately identify professional weaknesses "
            "and articulate clear, actionable mitigation strategies they are executing?\n"
            "2. Delivery Under Pressure & Deadlines: Does the candidate showcase structural prioritization tactics "
            "and emotional composure when handling aggressive timelines versus long-term projects?\n"
            "3. Core Motivation & Vision: Does the candidate show definitive long-term career ambition "
            "that aligns with high-performance team engineering standards?\n\n"
            "Enforce strict compliance with this exact structured payload schema configuration response:\n"
            "- score: An integer value between 1 (Severe cultural mismatch or lack of maturity) and 5 (Exceptional alignment, professional agility, and strong values framing).\n"
            "- justification: Exactly a crisp, 2-sentence rationale outlining the core reasons for the score assignment.\n"
            "- evidence: Extract a direct verbatim quote from the candidate's dialogue that explicitly showcases their behavioral positioning or handling of professional situations."
        )

        user_prompt = f"Here is the preprocessed Q&A Session 2 HR panel interview transcript dialogue stream to evaluate:\n\n{session2_transcript}"

        # Execute structured LLM transaction forced to populate the EvalScore schema model
        eval_output, token_meta = self.call_llm_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=EvalScore
        )

        # Defensive Processing Post-Invocation Guardrail
        if not eval_output:
            logger.error("Generative transaction trace error encountered during cultural assessment loop.")
            eval_output = EvalScore(
                score=1,
                justification="Cultural alignment evaluation pipeline was forced into baseline mitigation due to generation runtime failures.",
                evidence="N/A"
            )

        return eval_output, token_meta