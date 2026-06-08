import os
import json
import logging
from typing import Dict, Any, Tuple
from agents.base_agent import BaseAgent
from models.evaluation import TechnicalDimensionReport
from models.enums import RoleType

# Setup robust system logger tracking channel
logger = logging.getLogger("TechnicalDepthAgent")

class TechnicalDepthAgent(BaseAgent):
    """
    Role-aware evaluation engine responsible for dynamically synthesizing custom tracking
    rubrics, isolating code blocks, and grading deep backend and systems engineering logic.
    Now produces a full TechnicalDimensionReport with per-rubric-dimension scoring.
    """
    def __init__(self):
        super().__init__()
        logger.info("Production-tier Technical Depth Agent initialized successfully.")

    def _load_and_compile_rubric(self, role_type: Any) -> Dict[str, Any]:
        """
        Dynamically loads the appropriate evaluation rubric file from disk.
        Features polymorphic inheritance resolution to cleanly merge base SWE characteristics 
        if an 'extends' directive is encountered inside a target track.
        """
        role_str = role_type.value if hasattr(role_type, 'value') else str(role_type)
        role_str = role_str.strip().upper()

        if role_str == "AI":
            filename = "ai_engineer.json"
        elif role_str == "SWE":
            filename = "swe.json"
        elif role_str == "BA":
            filename = "ba.json"
        elif role_str == "TRAINEE":
            filename = "trainee.json"
        else:
            filename = f"{role_str.lower()}.json"

        rubric_path = os.path.join("rubrics", filename)

        try:
            if not os.path.exists(rubric_path):
                raise FileNotFoundError(f"Target metric dictionary not found at location: {rubric_path}")

            with open(rubric_path, "r", encoding="utf-8") as file:
                rubric_data = json.load(file)

            if "extends" in rubric_data and rubric_data["extends"] == "SWE":
                logger.info(f"Rubric expansion detected. Merging base SWE metrics into specialization: {role_str}")
                swe_path = os.path.join("rubrics", "swe.json")

                with open(swe_path, "r", encoding="utf-8") as swe_file:
                    swe_base = json.load(swe_file)

                compiled_dimensions = {**swe_base.get("dimensions", {}), **rubric_data.get("dimensions", {})}
                rubric_data["dimensions"] = compiled_dimensions

            logger.info(f"Successfully loaded and compiled technical rubric mapping for track: {role_str}")
            return rubric_data

        except Exception as e:
            logger.error(f"Failed to compile rubric layout tree at {rubric_path}: {str(e)}. Falling back to pure SWE baseline.")
            try:
                with open(os.path.join("rubrics", "swe.json"), "r", encoding="utf-8") as file:
                    return json.load(file)
            except Exception as crash_loop_panic:
                logger.critical(f"FATAL: Structural configuration corruption detected inside core rubrics mapping. {str(crash_loop_panic)}")
                return {"role_type": "FALLBACK", "dimensions": {"technical_depth": "Evaluate structural logic baseline."}}

    def evaluate_technical_depth(
        self,
        role_type: Any,
        session1_transcript: str,
        programming_answers: list[str]
    ) -> Tuple[TechnicalDimensionReport, Dict[str, int]]:
        """
        Analyzes specialized engineering capabilities using custom compiled rubric files.
        Returns a full TechnicalDimensionReport with overall score and per-dimension breakdown.

        Returns:
            Tuple[TechnicalDimensionReport, token_metadata]
        """
        if not programming_answers or len(programming_answers) < 2:
            logger.error("Programming submissions trace arrays are missing or malformed. Filling failure parameters.")
            programming_answers = ["# Missing Submission Text File", "# Missing Submission Text File"]

        compiled_rubric = self._load_and_compile_rubric(role_type)
        dimensions = compiled_rubric.get("dimensions", {})

        logger.info(f"Executing analytical technical depth evaluation for role payload tracker: {role_type}")

        # Build explicit dimension instructions so the LLM knows exactly what to produce
        dimension_instructions = "\n".join([
            f"- {dim_name}: {dim_definition}"
            for dim_name, dim_definition in dimensions.items()
        ])

        system_prompt = (
            "You are an elite Principal Systems Architect and Lead Machine Learning Engineer.\n"
            "Your mandate is to strictly evaluate the candidate's core domain competence against "
            "a specific set of rubric dimensions based ONLY on explicit evidence in the provided "
            "transcript and code submissions.\n\n"
            f"RUBRIC DIMENSIONS TO EVALUATE:\n"
            f"{dimension_instructions}\n\n"
            "Evaluation Rules:\n"
            "1. Include every single dimension listed above in your response — do not skip any.\n"
            "2. For each dimension, check for explicit evidence across ALL THREE sources:\n"
            "   a) The candidate's spoken responses in the transcript\n"
            "   b) The interviewer's questions or statements in the transcript\n"
            "   c) The candidate's submitted code (for code-related dimensions)\n"
            "   NOTE: If the interviewer explicitly references MCQ performance covering a topic "
            "(e.g. 'you scored 5/5 covering quantization, RAG, activation math'), that counts "
            "as evidence for those dimensions — assess them based on MCQ context.\n"
            "3. If explicit evidence EXISTS across any of the three sources:\n"
            "   - Set not_assessed=false\n"
            "   - Assign a score (1-5)\n"
            "   - Write a single-sentence justification based on that evidence\n"
            "   - Include a direct verbatim quote as evidence where possible\n"
            "4. If NO evidence exists across any of the three sources:\n"
            "   - Set not_assessed=true\n"
            "   - Set score=null\n"
            "   - Write a single-sentence justification stating the dimension was not covered\n"
            "   - Set evidence=null\n"
            "5. CRITICAL: Never penalize a candidate for a dimension that was not assessed. "
            "Absence of evidence is not evidence of weakness — it means the interview did not cover it.\n"
            "6. After assessing all dimensions, provide an overall_score (1-5) based ONLY on the "
            "dimensions that were actually assessed. Unassessed dimensions must not drag the score down.\n"
            "7. Provide an overall_justification of exactly 2 sentences summarizing assessed performance.\n\n"
            "You must return a structured response matching this exact schema:\n"
            "- overall_score: Integer 1-5 holistic score across assessed dimensions only\n"
            "- overall_justification: Exactly 2 sentences summarizing the technical assessment\n"
            "- dimensions: A list of objects, one per rubric dimension, each containing:\n"
            "  * dimension_name: The exact dimension key (e.g. 'langgraph_familiarity')\n"
            "  * score: Integer 1-5 if assessed, null if not_assessed=true\n"
            "  * justification: Single sentence rationale or reason for not assessing\n"
            "  * evidence: Direct verbatim quote from transcript or code, or null\n"
            "  * not_assessed: Boolean — true if dimension had no coverage in transcript or code"
        )

        user_prompt = (
            f"--- START CANDIDATE CODE REPOSITORY TRACKS ---\n"
            f"[SUBMISSION CODE Q1]:\n{programming_answers[0]}\n\n"
            f"[SUBMISSION CODE Q2]:\n{programming_answers[1]}\n"
            f"--- END CANDIDATE CODE REPOSITORY TRACKS ---\n\n"
            f"--- START CONVERSATIONAL TECHNICAL PANEL DIALOGUE BLOCK ---\n"
            f"{session1_transcript}\n"
            f"--- END CONVERSATIONAL TECHNICAL PANEL DIALOGUE BLOCK ---"
        )

        eval_output, token_meta = self.call_llm_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=TechnicalDimensionReport
        )

        if not eval_output:
            logger.error("Generative payload transaction error trace encountered during runtime assessment loop.")
            # Build fallback with one dimension per rubric entry so schema is still valid
            fallback_dimensions = [
                {
                    "dimension_name": dim_name,
                    "score": 1,
                    "justification": "Evaluation failed — requires manual review.",
                    "evidence": None
                }
                for dim_name in dimensions.keys()
            ] or [{"dimension_name": "technical_depth", "score": 1, "justification": "Evaluation failed.", "evidence": None}]

            eval_output = TechnicalDimensionReport(
                overall_score=1,
                overall_justification="Technical depth evaluation was forced into baseline mitigation due to generation runtime failures. All dimension scores require manual auditing.",
                dimensions=fallback_dimensions
            )

        return eval_output, token_meta