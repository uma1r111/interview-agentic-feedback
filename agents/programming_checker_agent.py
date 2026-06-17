import logging
from pathlib import Path
from typing import List, Tuple

from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from services.file_extractor import FileExtractorService

logger = logging.getLogger("ProgrammingCheckerAgent")


# ==============================================================================
# Pydantic schema for structured LLM output
# ==============================================================================

class ProgrammingQuestionResult(BaseModel):
    """Structured evaluation result for a single programming question."""
    question_number: int = Field(..., description="1-based index of the question in the document")
    question_text: str = Field(..., description="A short summary of the question asked")
    extracted_logic_steps: str = Field(..., description="A plain English summary of the algorithm/approach the candidate used, ignoring all syntax.")
    is_pass: bool = Field(..., description="True if the candidate's logic and approach are generally correct or close enough to pass")
    feedback: str = Field(..., description="One or two sentences commenting purely on the candidate's logic, approach, and how close they were to the solution. Ignore syntax errors.")


class ProgrammingEvaluationOutput(BaseModel):
    """Full structured output from the Programming Grading LLM call."""
    overall_pass: bool = Field(..., description="True if the candidate passed the programming section overall")
    insight_paragraph: str = Field(
        ...,
        description=(
            "A single paragraph (4–6 sentences) summarizing the candidate's overall programming logic, "
            "problem-solving approach, and proximity to correct solutions across all questions."
        )
    )
    did_i_penalize_for_syntax: bool = Field(
        ..., 
        description="MUST be False. If you penalized the candidate for missing colons, bad indentation, typos, or any syntax errors, set this to True. Then reconsider your output."
    )
    question_results: List[ProgrammingQuestionResult] = Field(
        ...,
        description="One entry per programming question found in the document"
    )


# ==============================================================================
# Programming Checker Agent
# ==============================================================================

class ProgrammingCheckerAgent(BaseAgent):
    """
    Reads the candidate's raw programming answers file, extracts all text, 
    sends it to the LLM to evaluate the *logic and approach* (ignoring syntax),
    and returns:
      - programming_passed : bool
      - insight_paragraph  : str
      - details            : List[ProgrammingQuestionResult]
    """

    def __init__(self):
        super().__init__()
        self._extractor = FileExtractorService()
        logger.info("ProgrammingCheckerAgent initialised.")

    def evaluate(self, programming_file_path: str) -> Tuple[bool, str, List[ProgrammingQuestionResult]]:
        """
        Evaluates a candidate's programming answers from a saved file.

        Args:
            programming_file_path: Absolute or relative path to the programming answers file.

        Returns:
            Tuple of:
              - programming_passed (bool)
              - insight_paragraph (str)
              - question_results (List[ProgrammingQuestionResult])

        Raises:
            ValueError: if the file cannot be read.
        """
        logger.info(f"ProgrammingCheckerAgent: evaluating file — {programming_file_path}")

        # 1️⃣ Extract raw text
        raw_text = self._read_file(programming_file_path)

        # 2️⃣ Build prompts and call the LLM
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(raw_text)

        evaluation_output, token_meta = self.call_llm_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ProgrammingEvaluationOutput,
        )

        if not evaluation_output:
            logger.error("ProgrammingCheckerAgent: LLM returned no structured output — using fallback.")
            return False, "Programming evaluation could not be completed due to a processing error.", []

        logger.info(
            f"ProgrammingCheckerAgent: Pass={evaluation_output.overall_pass} "
            f"| tokens={token_meta.get('total_tokens', 0)}"
        )

        return (
            evaluation_output.overall_pass,
            evaluation_output.insight_paragraph,
            evaluation_output.question_results
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_file(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.exists():
            raise ValueError(f"Programming file not found: {file_path}")

        with open(path, "rb") as fh:
            file_bytes = fh.read()

        filename = path.name
        ext = path.suffix.lower().lstrip(".")
        content_type_map = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain",
        }
        content_type = content_type_map.get(ext, "application/octet-stream")

        raw_text = self._extractor.extract(file_bytes, filename, content_type)
        if not raw_text or not raw_text.strip():
            raise ValueError(f"No text could be extracted from Programming file: {file_path}")

        return raw_text

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "You are an expert Principal Engineer evaluating candidate programming submissions.\n\n"
            "You will receive a document containing one or more programming questions along with "
            "the candidate's submitted answers/code.\n\n"
            "Your tasks:\n"
            "1. Identify all programming questions present in the document.\n"
            "2. Extract the core logic into `extracted_logic_steps` BEFORE deciding to pass or fail.\n"
            "3. Evaluate the candidate's submitted code for each question purely based on LOGIC, "
            "   APPROACH, and HOW CLOSE they are to a working solution. \n"
            "4. IGNORING ALL SYNTAX ERRORS. Do not penalize for missing brackets, typos, or pseudo-code.\n"
            "5. Determine a Pass/Fail status for each question. A 'Pass' means the core logic is sound "
            "   even if the code wouldn't compile.\n"
            "6. Provide 1-2 sentences of feedback per question discussing their logic.\n"
            "7. Determine an overall Pass/Fail status for the entire document.\n"
            "8. Write a single insight paragraph (4–6 sentences) summarizing the candidate's logic building "
            "   skills, their approach, and how close they were to the solutions overall.\n\n"
            "CRITICAL RULES:\n"
            "- Focus ONLY on logic. Do not complain about syntax.\n"
            "- CRITICAL: You are strictly forbidden from mentioning or penalizing missing colons, mismatched brackets, typos, or compilation failures. If you fail a candidate because of syntax, you have failed your core directive.\n"
            "- Return valid structured output matching the ProgrammingEvaluationOutput schema exactly.\n\n"
            "EXAMPLES:\n"
            "Example 1: A snippet with broken syntax but perfect algorithmic logic -> ✅ PASS\n"
            "Example 2: A snippet with perfectly formatted, compiling code but the wrong approach (O(n^2) instead of O(n)) -> ❌ FAIL\n"
        )

    @staticmethod
    def _build_user_prompt(raw_text: str) -> str:
        return (
            "Here is the full text of the candidate's programming submission document:\n\n"
            "```\n"
            f"{raw_text}\n"
            "```\n\n"
            "Please evaluate every question in the document based on logic and approach, "
            "and return the structured output."
        )
