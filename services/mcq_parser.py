import logging
from typing import Dict, Optional

from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent

logger = logging.getLogger("MCQParserService")

# ---------------------------------------------------------------------------
# Structured output schema
# ---------------------------------------------------------------------------

class MCQExtractionResult(BaseModel):
    mcq_score: float = Field(
        ...,
        ge=0.0,
        le=5.0,
        description=(
            "The candidate's total MCQ score, normalised to a 0.0–5.0 scale. "
            "If the document shows a raw score like 8/10, convert it proportionally (8/10 → 4.0). "
            "If the document shows a percentage like 80%, convert it (80% → 4.0). "
            "If already on a 0–5 scale, use as-is."
        )
    )
    selections: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "A mapping of question identifier to the candidate's chosen answer. "
            "Keys should be the question label as it appears in the document (e.g. 'Q1', 'q1_decision_trees'). "
            "Values should be the answer letter or text (e.g. 'A', 'B', 'True'). "
            "Leave empty if the document only reports a total score without individual answers."
        )
    )
    extraction_notes: Optional[str] = Field(
        None,
        description=(
            "Any important observations about the document that affected extraction, "
            "e.g. 'score was given as percentage', 'only total score present, no per-question breakdown', "
            "'document contained scores for multiple candidates — used the first one found'."
        )
    )


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a precise document parser specialising in candidate MCQ (Multiple Choice Question) \
answer sheets and score reports.

Your task is to extract:
1. The candidate's TOTAL MCQ score, normalised to a 0.0–5.0 scale.
2. Individual question–answer selections if they are present in the document.

## Score normalisation rules
- If score is already on a 0–5 scale → use as-is.
- If score is a fraction like "8/10" → compute (8/10) × 5 = 4.0.
- If score is a percentage like "80%" → compute 80/100 × 5 = 4.0.
- If score is a fraction like "4/5" → use numerator as-is = 4.0.
- Round to one decimal place.

## Selections extraction rules
- Extract ONLY the candidate's chosen answers, NOT the correct answers.
- Use the question label exactly as shown in the document as the key (e.g. "Q1", "Question 1", "q1_decision_trees").
- Use the answer as-is (e.g. "A", "B", "True", "False").
- If no per-question breakdown is present, return an empty dict for selections.

## Important
- If multiple candidates appear in the document, use the FIRST one found.
- Do NOT hallucinate scores or answers that are not clearly present in the document.
- If you cannot find a score at all, set mcq_score to 0.0 and note this in extraction_notes.
"""

_USER_PROMPT_TEMPLATE = """\
Parse the following MCQ document and extract the candidate's score and answer selections.

--- DOCUMENT CONTENT BEGIN ---
{document_text}
--- DOCUMENT CONTENT END ---
"""


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------

class MCQParserService(BaseAgent):
    """
    Uses Azure OpenAI structured output to extract MCQ score and selections
    from a free-form document (PDF, TXT, or DOCX converted to plain text).

    Inherits BaseAgent for the LLM client and call_llm_structured wrapper.
    """

    def parse(self, document_text: str) -> MCQExtractionResult:
        """
        Parses a plain-text MCQ document and returns structured extraction.

        Args:
            document_text: Raw text content extracted from the uploaded MCQ file.

        Returns:
            MCQExtractionResult with mcq_score (0–5), selections dict, and notes.

        Raises:
            ValueError: If the LLM call fails or returns None.
        """
        # Truncate to first 3000 chars to save tokens — MCQ docs are usually short
        snippet = document_text[:3000]

        user_prompt = _USER_PROMPT_TEMPLATE.format(document_text=snippet)

        result, token_meta = self.call_llm_structured(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=MCQExtractionResult,
        )

        if result is None:
            raise ValueError(
                "MCQ document parsing failed — the LLM could not extract structured data. "
                "Check that the uploaded file contains readable MCQ content."
            )

        logger.info(
            f"MCQ parsed: score={result.mcq_score}/5.0 | "
            f"selections={len(result.selections)} question(s) | "
            f"tokens={token_meta.get('total_tokens', 0)} | "
            f"notes={result.extraction_notes}"
        )
        return result
