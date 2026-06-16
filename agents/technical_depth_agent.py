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
        Injects calibrated 1/3/5 scoring anchors into the system prompt so the LLM produces
        consistent, comparable scores across all candidates.

        Returns:
            Tuple[TechnicalDimensionReport, token_metadata]
        """
        if not programming_answers or len(programming_answers) < 2:
            logger.error("Programming submissions trace arrays are missing or malformed. Filling failure parameters.")
            programming_answers = ["# Missing Submission Text File", "# Missing Submission Text File"]

        compiled_rubric = self._load_and_compile_rubric(role_type)
        dimensions = compiled_rubric.get("dimensions", {})
        grading_note = compiled_rubric.get("grading_note", "")

        logger.info(f"Executing analytical technical depth evaluation for role payload tracker: {role_type}")

        # Build dimension instructions — inject anchors if present, otherwise fall back to plain description
        dimension_blocks = []
        for dim_name, dim_value in dimensions.items():
            if isinstance(dim_value, dict):
                # Structured format: has description + anchors
                description = dim_value.get("description", "")
                anchors = dim_value.get("anchors", {})
                anchor_text = ""
                if anchors:
                    anchor_text = (
                        f"\n    Scoring anchors:"
                        f"\n      Score 1: {anchors.get('1', 'No anchor defined.')}"
                        f"\n      Score 3: {anchors.get('3', 'No anchor defined.')}"
                        f"\n      Score 5: {anchors.get('5', 'No anchor defined.')}"
                    )
                dimension_blocks.append(f"[{dim_name}]\n  Definition: {description}{anchor_text}")
            else:
                # Legacy flat string format — plain description, no anchors
                dimension_blocks.append(f"[{dim_name}]\n  Definition: {dim_value}")

        dimension_instructions = "\n\n".join(dimension_blocks)

        system_prompt = (
            "You are an elite Principal Systems Architect and Lead Machine Learning Engineer.\n"
            "Your mandate is to evaluate the candidate's core domain competence against a specific "
            "set of rubric dimensions, based ONLY on explicit evidence found in the transcript and "
            "code submissions provided below.\n\n"
            "=== SCORING STANDARD ===\n"
            "Each dimension includes calibrated scoring anchors that define what observable "
            "candidate behaviour constitutes a 1 (poor), 3 (meets bar), and 5 (exceptional). "
            "Use these anchors as your primary reference when assigning scores. "
            "Interpolate for 2 and 4 — a 2 is below bar but not completely absent, "
            "a 4 is above bar but not exemplary.\n\n"
            + (f"=== ROLE-SPECIFIC GRADING NOTE ===\n{grading_note}\n\n" if grading_note else "")
            + "=== RUBRIC DIMENSIONS ===\n"
            f"{dimension_instructions}\n\n"
            "=== EVALUATION RULES ===\n"
            "1. Include EVERY dimension listed above in your response — do not skip any.\n"
            "2. For each dimension, check for explicit evidence across ALL THREE sources:\n"
            "   a) The candidate's spoken responses in the transcript\n"
            "   b) The interviewer's questions or framing in the transcript\n"
            "   c) The candidate's submitted code (for code-related dimensions)\n"
            "   IMPORTANT: If the interviewer references MCQ performance on a topic "
            "(e.g. 'you scored 5/5 covering quantization, RAG, activation math'), that is "
            "valid evidence — assess those dimensions based on the MCQ reference.\n"
            "3. When evidence EXISTS:\n"
            "   - Set not_assessed=false\n"
            "   - Assign a score (1–5) using the anchors as your calibration standard\n"
            "   - Write a single-sentence justification tied to specific observed behaviour\n"
            "   - Include a direct verbatim quote from the transcript or code as evidence\n"
            "4. When NO evidence exists across any source:\n"
            "   - Set not_assessed=true\n"
            "   - Set score=null\n"
            "   - Write a single-sentence justification stating the dimension was not covered\n"
            "   - Set evidence=null\n"
            "5. CRITICAL: Never penalise a candidate for a dimension that was not covered. "
            "Absence of evidence means the interview did not surface it — not that the "
            "candidate lacks the skill.\n"
            "6a. ADJACENT CONCEPT RULE: If a candidate demonstrates a concept that is related "
            "to a rubric dimension but does not directly match its definition, the maximum "
            "score for that dimension is 3/5. Full marks (4 or 5) require direct, explicit "
            "evidence matching the rubric definition exactly. Examples of adjacent concepts "
            "that must NOT score above 3:\n"
            "   - Error routing or conditional edges in a pipeline → hallucination_handling "
            "(rubric requires guardrail patterns, output validators, safety system prompts)\n"
            "   - Mentioning an LLM framework → langgraph_familiarity "
            "(rubric requires StateGraph nodes, conditional edges, fan-out/fan-in reasoning)\n"
            "   - General ML experience → quantization "
            "(rubric requires specific precision schemes: FP16, INT8, GPTQ, bitsandbytes)\n"
            "   When in doubt: if the candidate did not use the rubric's exact vocabulary or "
            "demonstrate the rubric's exact behaviour, cap the score at 3.\n"
            "6. Compute overall_score from assessed dimensions only. "
            "Unassessed dimensions must not pull the score down.\n"
            "7. Write overall_justification in exactly 2 sentences: "
            "sentence 1 states the candidate's strongest demonstrated area, "
            "sentence 2 identifies the most significant gap or the primary reason for the score.\n\n"
            "=== OUTPUT SCHEMA ===\n"
            "Return a structured response with:\n"
            "- overall_score: Integer 1–5 holistic score across assessed dimensions only\n"
            "- overall_justification: Exactly 2 sentences as described above\n"
            "- dimensions: One object per rubric dimension, each with:\n"
            "  * dimension_name: Exact dimension key (e.g. 'langgraph_familiarity')\n"
            "  * score: Integer 1–5 if assessed, null if not_assessed=true\n"
            "  * justification: Single sentence tied to specific observed behaviour\n"
            "  * evidence: Direct verbatim quote from transcript or code, or null\n"
            "  * not_assessed: true if dimension had no coverage, false otherwise"
        )

        user_prompt = (
            f"--- START CANDIDATE CODE SUBMISSIONS ---\n"
            f"[CODE SUBMISSION Q1]:\n{programming_answers[0]}\n\n"
            f"[CODE SUBMISSION Q2]:\n{programming_answers[1]}\n"
            f"--- END CANDIDATE CODE SUBMISSIONS ---\n\n"
            f"--- START PREPROCESSED Q&A TECHNICAL INTERVIEW TRANSCRIPT ---\n"
            f"{session1_transcript}\n"
            f"--- END PREPROCESSED Q&A TECHNICAL INTERVIEW TRANSCRIPT ---\n\n"
            "Now evaluate the candidate against every rubric dimension listed in the system prompt. "
            "Use the scoring anchors to calibrate your scores. "
            "Only reference evidence explicitly present in the transcript or code above."
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
                    "evidence": None,
                    "not_assessed": False
                }
                for dim_name in dimensions.keys()
            ] or [{"dimension_name": "technical_depth", "score": 1, "justification": "Evaluation failed.", "evidence": None, "not_assessed": False}]

            eval_output = TechnicalDimensionReport(
                overall_score=1,
                overall_justification="Technical depth evaluation failed at runtime. All dimension scores require manual auditing.",
                dimensions=fallback_dimensions
            )

        return eval_output, token_meta