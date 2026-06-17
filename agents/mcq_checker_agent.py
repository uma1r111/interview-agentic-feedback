import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from services.file_extractor import FileExtractorService

logger = logging.getLogger("MCQCheckerAgent")


# ==============================================================================
# Pydantic schema for structured LLM output — one entry per MCQ question
# ==============================================================================

class MCQQuestionResult(BaseModel):
    """Structured evaluation result for a single MCQ question."""
    question_number: int = Field(..., description="1-based index of the question in the test")
    question_text: str = Field(..., description="Full question text as it appeared in the document")
    candidate_answer: str = Field(..., description="The answer option the candidate selected (e.g. 'A', 'B', or the full option text)")
    correct_answer: str = Field(..., description="The correct answer option according to the answer key embedded in the document")
    is_correct: bool = Field(..., description="True if the candidate's answer matches the correct answer")
    topic_tag: str = Field(..., description="Short topic label for this question (e.g. 'Python', 'RAG', 'SQL', 'ML Fundamentals')")
    explanation: str = Field(..., description="One concise sentence explaining why the answer is correct or incorrect")


class MCQEvaluationOutput(BaseModel):
    """Full structured output from the MCQ grading LLM call."""
    question_results: List[MCQQuestionResult] = Field(
        ...,
        description="One entry per MCQ question found in the document"
    )
    insight_paragraph: str = Field(
        ...,
        description=(
            "A single paragraph (4–6 sentences) that summarises the candidate's MCQ performance. "
            "Must include: overall impression, topic areas where the candidate succeeded, "
            "topic areas where the candidate struggled, and a specific pattern observation."
        )
    )


# ==============================================================================
# MCQ Checker Agent
# ==============================================================================

class MCQCheckerAgent(BaseAgent):
    """
    Reads the candidate's raw MCQ file, extracts all text, sends it to the
    LLM to grade each question, and returns:

      - mcq_score   : float in the 0–5 range (proportional to % correct)
      - insight     : one-paragraph natural-language evaluation
      - details     : per-question breakdown (List[MCQQuestionResult])
    """

    def __init__(self):
        super().__init__()
        self._extractor = FileExtractorService()
        logger.info("MCQCheckerAgent initialised.")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def evaluate(
        self,
        mcq_file_path: str,
    ) -> Tuple[float, str, List[MCQQuestionResult]]:
        """
        Evaluates a candidate's MCQ test from a saved file.

        Args:
            mcq_file_path: Absolute or relative path to the MCQ file
                           (any format supported by FileExtractorService:
                            .txt, .pdf, .docx).

        Returns:
            Tuple of:
              - mcq_score (float, 0–5)
              - insight_paragraph (str)
              - question_results (List[MCQQuestionResult])

        Raises:
            ValueError  : if the file cannot be read or no questions are found.
            RuntimeError: if the LLM fails to produce a structured response.
        """
        logger.info(f"MCQCheckerAgent: evaluating file — {mcq_file_path}")

        # 1️⃣ Extract raw text from the file
        raw_text = self._read_file(mcq_file_path)

        # 2️⃣ Build prompts and call the LLM
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(raw_text)

        evaluation_output, token_meta = self.call_llm_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=MCQEvaluationOutput,
        )

        if not evaluation_output:
            logger.error("MCQCheckerAgent: LLM returned no structured output — using fallback.")
            return 0.0, "MCQ evaluation could not be completed due to a processing error.", []

        # 3️⃣ Compute score: proportion correct → scaled to 0–5
        results = evaluation_output.question_results
        if not results:
            raise ValueError("LLM returned zero question results — document may not contain valid MCQs.")

        correct_count = sum(1 for r in results if r.is_correct)
        total_count = len(results)
        proportion = correct_count / total_count
        mcq_score = round(proportion * 5, 2)   # Scale to 0–5 to match other dimension scores

        logger.info(
            f"MCQCheckerAgent: {correct_count}/{total_count} correct → score={mcq_score}/5 "
            f"| tokens={token_meta.get('total_tokens', 0)}"
        )

        return mcq_score, evaluation_output.insight_paragraph, results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_file(self, file_path: str) -> str:
        """Reads the MCQ file using FileExtractorService and returns plain text."""
        path = Path(file_path)
        if not path.exists():
            raise ValueError(f"MCQ file not found: {file_path}")

        with open(path, "rb") as fh:
            file_bytes = fh.read()

        filename = path.name
        # Infer content_type from extension for the extractor
        ext = path.suffix.lower().lstrip(".")
        content_type_map = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "doc": "application/msword",
            "txt": "text/plain",
            "json": "application/json",
        }
        content_type = content_type_map.get(ext, "application/octet-stream")

        raw_text = self._extractor.extract(file_bytes, filename, content_type)
        if not raw_text or not raw_text.strip():
            raise ValueError(f"No text could be extracted from MCQ file: {file_path}")

        logger.info(f"MCQCheckerAgent: extracted {len(raw_text)} chars from {filename}")
        return raw_text

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "You are an expert MCQ test evaluator.\n\n"
            "You will receive the full text of a candidate's MCQ test document. "
            "The document contains questions, answer options (A/B/C/D or similar), "
            "and the candidate's selected answer for each question. "
            "The document may also contain an answer key at the end or inline.\n\n"
            "Your tasks:\n"
            "1. Parse every MCQ question from the document.\n"
            "2. Identify the candidate's selected answer for each question.\n"
            "3. Identify the correct answer (from the answer key in the document, "
            "   or from your own knowledge if it is a factual question without an explicit key).\n"
            "4. Determine whether the candidate's answer is correct.\n"
            "5. Assign a short topic_tag to each question (e.g. 'Python', 'OOP', 'SQL', 'Networking', "
            "   'ML Fundamentals', 'Data Structures', etc.).\n"
            "6. Write a concise one-sentence explanation for each question.\n"
            "7. Write a single insight paragraph (4–6 sentences) that:\n"
            "   - States the overall result (e.g. X out of Y correct).\n"
            "   - Names the topic areas where the candidate performed strongly.\n"
            "   - Names the topic areas where the candidate made mistakes.\n"
            "   - Identifies at least one specific pattern (e.g. 'consistently struggled with "
            "     recursion-based questions' or 'answered all ML fundamentals correctly but "
            "     missed practical Python questions').\n\n"
            "CRITICAL RULES:\n"
            "- Do NOT fabricate questions. Only grade questions that appear in the document.\n"
            "- If no answer key is present, use your domain knowledge to determine correctness.\n"
            "- If a question is ambiguous, mark is_correct=false and note it in the explanation.\n"
            "- Return valid structured output matching the MCQEvaluationOutput schema exactly.\n"
        )

    @staticmethod
    def _build_user_prompt(raw_text: str) -> str:
        return (
            "Here is the full text of the candidate's MCQ test document:\n\n"
            "```\n"
            f"{raw_text}\n"
            "```\n\n"
            "Please evaluate every question in the document and return the structured output."
        )
