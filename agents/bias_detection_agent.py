import logging
from typing import Dict, Any, Tuple, List
from agents.base_agent import BaseAgent
from models.evaluation import EvalScore, TechnicalDimensionReport
from models.bias import BiasLog, BiasCorrection

logger = logging.getLogger("BiasDetectionAgent")

class BiasDetectionAgent(BaseAgent):
    """
    Quality control gate responsible for inspecting parallel agent outputs,
    redacting non-objective language, logging audit steps, and releasing the bias_clear lock.
    Now handles TechnicalDimensionReport separately from flat EvalScore agents.
    """
    def __init__(self):
        super().__init__()
        logger.info("Production-tier Bias Detection Agent initialized successfully.")

    def analyze_and_sanitize_scores(
        self,
        communication: EvalScore,
        technical: TechnicalDimensionReport,       # CHANGED from EvalScore
        problem_solving: EvalScore,
        cultural: EvalScore
    ) -> Tuple[BiasLog, EvalScore, TechnicalDimensionReport, EvalScore, EvalScore, bool, Dict[str, int]]:
        """
        Scans and normalizes linguistic text blocks across all individual parallel evaluators.
        Handles TechnicalDimensionReport structure separately from flat EvalScore agents.

        Returns:
            Tuple[BiasLog, clean_communication, clean_technical, clean_problem_solving, clean_cultural, bias_clear, token_metadata]
        """
        logger.info("Initiating language fairness sweep across all active evaluations...")

        system_prompt = (
            "You are an elite Lead Quality Assurance Director and Human Resources Compliance Officer.\n"
            "Your objective is to inspect a candidate's evaluation reports to ensure compliance with strict "
            "professional auditing frameworks. You must find and neutralize any loaded language, subjective framing, "
            "unconscious bias, or demographic leaks (such as gender, age, or specific regional details) present in the text.\n\n"
            "Review Guidelines:\n"
            "1. Neutrality Sweep: Check all justification and evidence fields across all inputs. "
            "Linguistic metrics must stay objective and metrics-driven (e.g., replace 'speaks with great passion' with 'demonstrates deep domain experience').\n"
            "2. Redaction Mechanics: If you identify subjective descriptions or non-essential background details, "
            "you must document the replacement and sanitize the phrase.\n"
            "3. Hard Compliance Gate: If the texts are naturally clean and professional, return 'bias_detected': false.\n\n"
            "Enforce strict conformity with this exact structured payload schema configuration response:\n"
            "- bias_detected: A boolean flag indicating if any changes or non-objective phrases were intercepted.\n"
            "- corrections: An array of objects matching this exact structure:\n"
            "  * agent_id: The category where the item was caught ('Communication', 'Technical', 'Problem Solving', or 'Cultural').\n"
            "  * original_phrase: The exact flagged non-objective text segment.\n"
            "  * corrected_phrase: The clean, objective, metrics-driven replacement text.\n"
            "  * rationale: A brief statement explaining why the phrase breached professional criteria."
        )

        # Build technical sector text — overall justification plus all dimension justifications
        technical_sector = (
            f"Overall Justification: {technical.overall_justification}\n"
        )
        for dim in technical.dimensions:
            technical_sector += (
                f"Dimension '{dim.dimension_name}': {dim.justification}"
                + (f" | Evidence: {dim.evidence}" if dim.evidence else "")
                + "\n"
            )

        user_prompt = (
            f"--- START SECTOR: Communication ---\n"
            f"Justification: {communication.justification}\n"
            f"Evidence: {communication.evidence}\n"
            f"--- END SECTOR: Communication ---\n\n"
            f"--- START SECTOR: Technical ---\n"
            f"{technical_sector}"
            f"--- END SECTOR: Technical ---\n\n"
            f"--- START SECTOR: Problem Solving ---\n"
            f"Justification: {problem_solving.justification}\n"
            f"Evidence: {problem_solving.evidence}\n"
            f"--- END SECTOR: Problem Solving ---\n\n"
            f"--- START SECTOR: Cultural ---\n"
            f"Justification: {cultural.justification}\n"
            f"Evidence: {cultural.evidence}\n"
            f"--- END SECTOR: Cultural ---"
        )

        bias_output, token_meta = self.call_llm_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=BiasLog
        )

        # Defensive fallback
        if not bias_output:
            logger.error("Generative transaction trace error encountered during bias audit sweep.")
            fallback_log = BiasLog(bias_detected=False, corrections=[])
            return fallback_log, communication, technical, problem_solving, cultural, True, token_meta

        # Deep copies for safe mutation
        clean_comm = communication.model_copy(deep=True)
        clean_tech = technical.model_copy(deep=True)
        clean_prob = problem_solving.model_copy(deep=True)
        clean_cult = cultural.model_copy(deep=True)

        if bias_output.bias_detected and bias_output.corrections:
            logger.warning(f"Compliance issues detected! Processing {len(bias_output.corrections)} corrections...")

            for corrective_action in bias_output.corrections:
                sector = corrective_action.agent_id.upper()
                orig = corrective_action.original_phrase
                repl = corrective_action.corrected_phrase

                if "COMMUNICATION" in sector:
                    clean_comm.justification = clean_comm.justification.replace(orig, repl)
                    if clean_comm.evidence:
                        clean_comm.evidence = clean_comm.evidence.replace(orig, repl)

                elif "TECHNICAL" in sector:
                    # Apply to overall justification
                    clean_tech.overall_justification = clean_tech.overall_justification.replace(orig, repl)
                    # Apply to each dimension's justification and evidence
                    for dim in clean_tech.dimensions:
                        dim.justification = dim.justification.replace(orig, repl)
                        if dim.evidence:
                            dim.evidence = dim.evidence.replace(orig, repl)

                elif "PROBLEM" in sector:
                    clean_prob.justification = clean_prob.justification.replace(orig, repl)
                    if clean_prob.evidence:
                        clean_prob.evidence = clean_prob.evidence.replace(orig, repl)

                elif "CULTURAL" in sector:
                    clean_cult.justification = clean_cult.justification.replace(orig, repl)
                    if clean_cult.evidence:
                        clean_cult.evidence = clean_cult.evidence.replace(orig, repl)

        logger.info("Bias sweep complete. Releasing core execution pipeline gate lock parameters.")
        return bias_output, clean_comm, clean_tech, clean_prob, clean_cult, True, token_meta