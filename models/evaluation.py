from pydantic import BaseModel, Field
from typing import List, Optional
from models.enums import Recommendation, Decision

class EvalScore(BaseModel):
    """Structured dimensional evaluation output produced by individual agents."""
    score: int = Field(..., ge=1, le=5, description="Evaluation score strictly between 1 and 5")
    justification: str = Field(..., description="A crisp, 2-sentence rationale outlining the score assignment")
    evidence: Optional[str] = Field(None, description="Direct word-for-word quotes or raw logic extracted from transcripts or test answers")

class DimensionScore(BaseModel):
    """Per-rubric-dimension evaluation score produced by the Technical Depth Agent."""
    dimension_name: str = Field(..., description="The rubric dimension being evaluated (e.g. 'langgraph_familiarity')")
    score: Optional[int] = Field(None, ge=1, le=5, description="Dimension-level score 1-5, or null if dimension was not assessed")
    justification: str = Field(..., description="Single-sentence rationale for the score, or reason why dimension was not assessed")
    evidence: Optional[str] = Field(None, description="Direct verbatim quote or code snippet supporting this dimension score")
    not_assessed: bool = Field(default=False, description="True if no evidence exists for this dimension in the transcript or code — candidate did not mention it and interviewer did not ask")

class TechnicalDimensionReport(BaseModel):
    """
    Full role-aware technical evaluation report produced by the Technical Depth Agent.
    Contains an overall score plus per-rubric-dimension breakdown.
    """
    overall_score: int = Field(..., ge=1, le=5, description="Holistic technical score across all evaluated dimensions")
    overall_justification: str = Field(..., description="A crisp 2-sentence summary rationale for the overall score")
    dimensions: List[DimensionScore] = Field(..., min_length=1, description="Per-dimension breakdown scores aligned to the loaded rubric")


class FeedbackReport(BaseModel):
    """The final compiled, multi-agent unified report schema ready for review."""
    candidate_name: str
    role_applied: str
    mcq_score: float = Field(..., description="Auto-marked test score out of 5")
    programming_q1_score: int = Field(..., ge=1, le=5)
    programming_q2_score: int = Field(..., ge=1, le=5)

    # Editable Evaluation Sections
    communication: EvalScore
    technical_depth: TechnicalDimensionReport      # CHANGED from EvalScore
    problem_solving: EvalScore
    cultural_alignment: EvalScore

    # Synthesis Blocks
    strengths: List[str] = Field(..., min_length=2, max_length=3, description="2 to 3 distinct bullet points highlighting strengths")
    concerns: List[str] = Field(..., min_length=2, max_length=3, description="2 to 3 distinct bullet points highlighting risks or gaps")

    # Final Flags
    ai_recommendation: Recommendation
    ai_justification: str = Field(..., description="A descriptive single-sentence justification backing the recommendation")
    hiring_manager_decision: Decision = Field(default=Decision.HOLD, description="Submission slot restricted to the manager")