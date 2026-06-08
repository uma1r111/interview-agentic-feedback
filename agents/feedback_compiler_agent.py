import logging
from typing import Dict, Any, Tuple, List
from agents.base_agent import BaseAgent
from models.evaluation import EvalScore, TechnicalDimensionReport, FeedbackReport
from models.enums import RoleType, Recommendation, Decision

logger = logging.getLogger("FeedbackCompilerAgent")

class FeedbackCompilerAgent(BaseAgent):
    """
    Final pipeline synthesis engine. Compiles dimensional evaluations and programmatic scores
    into a unified executive summary, strictly enforcing the bias governance lock.
    Now handles full TechnicalDimensionReport with per-dimension breakdown.
    """
    def __init__(self):
        super().__init__()
        logger.info("Production-tier Feedback Compiler Agent initialized successfully.")

    def compile_final_report(
        self,
        candidate_name: str,
        role_type: RoleType,
        mcq_score: float,
        programming_answers: List[str],
        communication: EvalScore,
        technical: TechnicalDimensionReport,        # CHANGED from EvalScore
        problem_solving: EvalScore,
        cultural: EvalScore,
        bias_clear: bool
    ) -> Tuple[FeedbackReport, Dict[str, int]]:
        """
        Synthesizes individual agent scores and text justifications into a consolidated,
        strongly typed FeedbackReport object.

        Returns:
            Tuple[FeedbackReport, token_metadata]
        """
        # 1. Hard Security Gate Enforcement Check
        if not bias_clear:
            logger.critical("SECURITY BREACH ATTEMPT: FeedbackCompiler running without an explicit bias_clear=True release lock.")
            raise PermissionError(
                "Pipeline Execution Blocked: The final summary report cannot be built because the "
                "data safety sweep has not cleared the current evaluation state."
            )

        logger.info(f"Compiling consolidated role-aware evaluation report for candidate: {candidate_name}")

        # Serialize TechnicalDimensionReport into a readable block for the compiler prompt
        technical_block = (
            f"Overall Technical Score: {technical.overall_score}/5\n"
            f"Overall Justification: {technical.overall_justification}\n"
            f"Dimension Breakdown:\n"
        )
        for dim in technical.dimensions:
            technical_block += (
                f"  - {dim.dimension_name}: {dim.score}/5 — {dim.justification}"
                + (f" (Evidence: {dim.evidence})" if dim.evidence else "")
                + "\n"
            )

        system_prompt = (
            "You are an executive hiring board director and chief technical assessment officer.\n"
            "Your objective is to ingest individual dimension scores and transform them into a polished, "
            "cohesive executive-ready hiring summary report.\n\n"
            "Compilation Guidelines:\n"
            "1. Score Mapping: Map the incoming communication, technical depth, problem-solving, and cultural-alignment "
            "objects directly to their respective report tracks.\n"
            "2. Technical Depth Mapping: The technical_depth field must be populated as a full TechnicalDimensionReport. "
            "Use the provided overall score, overall justification, and dimension breakdown exactly as given — "
            "do not modify or re-evaluate them. Carry them through verbatim into the report.\n"
            "3. Coding Question Extrapolations: Infer two standalone integer scores strictly between 1 and 5 specifically "
            "for 'programming_q1_score' and 'programming_q2_score' based entirely on the Technical Agent's analysis "
            "and the provided raw code text answers.\n"
            "4. Strengths & Concerns Syntheses: Generate exactly 2 to 3 distinct, actionable bullet points for strengths "
            "and exactly 2 to 3 for concerns. Draw from technical dimension scores, communication quality, "
            "problem solving indicators, and cultural alignment signals.\n"
            "5. Dynamic Recommendation: Formulate a final holistic 'ai_recommendation' enum value ('Strong Yes', 'Yes', 'Maybe', 'No') "
            "and a single-sentence 'ai_justification'. Factor in all dimensions — a candidate with high overall scores "
            "but weak dimension-level gaps (e.g. low hallucination_handling for an AI role) should be weighted accordingly.\n\n"
            "Enforce strict conformity with this exact structured payload schema:\n"
            "- candidate_name: Full name of candidate\n"
            "- role_applied: String representation of the target career track\n"
            "- mcq_score: Float tracking programmatic score out of 5\n"
            "- programming_q1_score: Integer from 1 to 5\n"
            "- programming_q2_score: Integer from 1 to 5\n"
            "- communication: Complete EvalScore object\n"
            "- technical_depth: Complete TechnicalDimensionReport object with overall_score, overall_justification, and dimensions list\n"
            "- problem_solving: Complete EvalScore object\n"
            "- cultural_alignment: Complete EvalScore object\n"
            "- strengths: List of 2 to 3 string bullets\n"
            "- concerns: List of 2 to 3 string bullets\n"
            "- ai_recommendation: One of 'Strong Yes', 'Yes', 'Maybe', 'No'\n"
            "- ai_justification: Single-sentence executive reasoning\n"
            "- hiring_manager_decision: Default to 'Hold'"
        )

        user_prompt = (
            f"Candidate: {candidate_name}\n"
            f"Target Role: {role_type.value}\n"
            f"Programmatic MCQ Score: {mcq_score}/5.0\n\n"
            f"--- START CODE INPUTS ---\n"
            f"Q1 Code: {programming_answers[0]}\n"
            f"Q2 Code: {programming_answers[1]}\n"
            f"--- END CODE INPUTS ---\n\n"
            f"--- START AGENT METRIC FEEDS ---\n"
            f"[Communication Evaluator]: Score={communication.score} | Justification={communication.justification}\n\n"
            f"[Technical Depth Evaluator]:\n{technical_block}\n"
            f"[Problem Solving Evaluator]: Score={problem_solving.score} | Justification={problem_solving.justification}\n\n"
            f"[Cultural Alignment Evaluator]: Score={cultural.score} | Justification={cultural.justification}\n"
            f"--- END AGENT METRIC FEEDS ---"
        )

        # 2. Invoke structured model compilation
        compiled_report, token_meta = self.call_llm_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=FeedbackReport
        )

        # 3. Defensive fallback
        if not compiled_report:
            logger.error("Generative layout compilation error tracking block encountered.")
            compiled_report = FeedbackReport(
                candidate_name=candidate_name,
                role_applied=role_type.value,
                mcq_score=mcq_score,
                programming_q1_score=1,
                programming_q2_score=1,
                communication=communication,
                technical_depth=technical,
                problem_solving=problem_solving,
                cultural_alignment=cultural,
                strengths=["System compilation anomaly encountered during extraction."],
                concerns=["Report generated using defensive fallback parameters. Technical metrics remain valid."],
                ai_recommendation=Recommendation.MAYBE,
                ai_justification="Summary generation failure encountered. Dimension arrays must be audited manually.",
                hiring_manager_decision=Decision.HOLD
            )

        logger.info(f"Feedback report generation complete for candidate: {candidate_name}. Decision parameters wrapped.")
        return compiled_report, token_meta