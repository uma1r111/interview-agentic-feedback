import os
import json
import logging
from typing import Dict, Any, Tuple
from agents.base_agent import BaseAgent
from models.evaluation import EvalScore
from models.enums import RoleType

# Setup robust system logger tracking channel
logger = logging.getLogger("TechnicalDepthAgent")

class TechnicalDepthAgent(BaseAgent):
    """
    Role-aware evaluation engine responsible for dynamically synthesizing custom tracking
    rubrics, isolating code blocks, and grading deep backend and systems engineering logic.
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
        # Convert enum or string to a standardized string format
        role_str = role_type.value if hasattr(role_type, 'value') else str(role_type)
        role_str = role_str.strip().upper()

        # Map the shorthand API token to the exact structural filename on disk
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
            
            # Polymorphic Check: Does this specialization inherit from a baseline track?
            if "extends" in rubric_data and rubric_data["extends"] == "SWE":
                logger.info(f"Rubric expansion detected. Merging base SWE metrics into specialization: {role_str}")
                swe_path = os.path.join("rubrics", "swe.json")
                
                with open(swe_path, "r", encoding="utf-8") as swe_file:
                    swe_base = json.load(swe_file)
                
                # Deep-merge the dimensions safely to avoid mutation side-effects
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
    ) -> Tuple[EvalScore, Dict[str, int]]:
        """
        Analyzes specialized engineering capabilities using custom compiled rubric files.
        Evaluates candidate's coding architecture separate from conversational jargon context.
        
        Returns:
            Tuple[EvalScore, token_metadata]
        """
        # Defensive Data Shield Boundary Check
        if not programming_answers or len(programming_answers) < 2:
            logger.error("Programming submissions trace arrays are missing or malformed. Filling failure parameters.")
            programming_answers = ["# Missing Submission Text File", "# Missing Submission Text File"]

        # 1. Fetch and structurally resolve the dynamic rubric architecture tree map
        compiled_rubric = self._load_and_compile_rubric(role_type)
        
        logger.info(f"Executing analytical technical depth evaluation for role payload tracker: {role_type}")

        system_prompt = (
            "You are an elite Principal Systems Architect and Lead Machine Learning Engineer.\n"
            "Your mandate is to strictly evaluate the candidate's core domain competence, structural algorithmic "
            "implementations, and low-level system design tradeoffs.\n\n"
            f"CRITICAL ASSIGNMENT: You must explicitly grade the applicant against these exact dimensions and definitions:\n"
            f"{json.dumps(compiled_rubric, indent=2)}\n\n"
            "Execution Audit Data Rules:\n"
            "1. Core Systems & Projects: Cross-verify any listed architectural experiences "
            "against their conversational logic. Detect depth vs script copying.\n"
            "2. Programming Artifact Analysis: Grade code execution logic, memory optimization, and time complexity parameters "
            "separately from syntax spacing mistakes.\n\n"
            "Enforce strict conformity with this exact structured payload schema configuration response:\n"
            "- score: Integer value between 1 (Critical structural gaps) and 5 (Flawless architectural understanding).\n"
            "- justification: Exactly a crisp, 2-sentence rationale outlining the core reasons for the score.\n"
            "- evidence: Extract direct verbatim quotes or code variables from the raw candidate data streams below."
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

        # 2. Invoke structured model validation routine via our local Azure OpenAI wrapper
        eval_output, token_meta = self.call_llm_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=EvalScore
        )

        # 3. Defensive Processing Post-Invocation Guardrail
        if not eval_output:
            logger.error("Generative payload transaction error trace encountered during runtime assessment loop.")
            eval_output = EvalScore(
                score=1,
                justification="Technical depth evaluation workflow was forced into baseline mitigation due to generation structural failures.",
                evidence="N/A"
            )

        return eval_output, token_meta