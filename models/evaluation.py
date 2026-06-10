from pydantic import BaseModel, Field
from typing import List, Optional, Literal
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


# ==============================================================================
# CV Parsing Agent — Output Models
# ==============================================================================
# These two models represent the two things the CV Parsing Agent produces.
# They are defined HERE (in models/) rather than in the agent file because they
# are data contracts — other parts of the system (pipeline state, FeedbackReport)
# need to reference them without importing from agents/.

class CandidateSkillsSummary(BaseModel):
    """
    The anonymised, PII-free representation of the candidate's CV.

    This is what the CV Parsing Agent produces in Pass 1.
    No names, employers, institutions, dates, or locations appear here.
    Only skills, durations, domains, education level, and achievement metrics.

    Safe to pass to any downstream agent or log — contains zero identifying info.
    """
    technical_skills: List[str] = Field(
        ...,
        description="List of specific technical skills found in the CV. e.g. ['Python', 'Kubernetes', 'React']"
    )
    experience_duration: str = Field(
        ...,
        description="Total years of professional experience as a duration string. e.g. '5 years'. No dates or employer names."
    )
    domain_areas: List[str] = Field(
        ...,
        description="High-level domain areas the candidate has worked in. e.g. ['Backend Systems', 'Cloud Infrastructure']. No company names."
    )
    education_level: str = Field(
        ...,
        description="Highest qualification with field of study only — no institution name. e.g. 'MSc Computer Science', 'BSc Electrical Engineering'"
    )
    notable_achievements: List[str] = Field(
        default_factory=list,
        description="Quantified accomplishments with no proper nouns. e.g. ['Reduced API latency by 40%', 'Serving 10M requests/day']"
    )


class ExperienceMatchSummary(BaseModel):
    """
    The result of comparing the anonymised CandidateSkillsSummary against
    the role rubric's required_skills list and min_experience_years.

    This is what the CV Parsing Agent produces in Pass 2.
    Appears in FeedbackReport as cv_experience_match — informational only,
    does NOT feed into any dimension scores.
    """
    required_skills_present: List[str] = Field(
        ...,
        description="Required skills from the role rubric that are present in the candidate's CV"
    )
    required_skills_missing: List[str] = Field(
        ...,
        description="Required skills from the role rubric that are absent from the candidate's CV"
    )
    years_of_experience: str = Field(
        ...,
        description="Candidate's experience duration extracted from CandidateSkillsSummary. e.g. '5 years'"
    )
    role_min_experience: str = Field(
        ...,
        description="Minimum experience required by the role rubric. e.g. '2 years'"
    )
    domain_match: Literal["strong", "moderate", "weak"] = Field(
        ...,
        description="How well the candidate's domain areas align with the target role"
    )
    overall_match_rating: Literal["strong", "moderate", "weak"] = Field(
        ...,
        description="Overall CV-to-role fit rating combining skills and experience"
    )


# ==============================================================================
# Final Report — includes cv_experience_match as an optional informational field
# ==============================================================================

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

    # CV Experience Match — informational only, not used in scoring
    # Optional because reports generated before CV parsing existed are still valid
    cv_experience_match: Optional[ExperienceMatchSummary] = Field(
        default=None,
        description="CV vs role rubric comparison. Informational only — does not affect dimension scores."
    )

    # Final Flags
    ai_recommendation: Recommendation
    ai_justification: str = Field(..., description="A descriptive single-sentence justification backing the recommendation")
    hiring_manager_decision: Decision = Field(default=Decision.HOLD, description="Submission slot restricted to the manager")