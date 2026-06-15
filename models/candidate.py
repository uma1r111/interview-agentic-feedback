from pydantic import BaseModel, Field
from typing import Optional, List, Dict, TypedDict
from models.enums import RoleType
from models.evaluation import EvalScore, FeedbackReport, TechnicalDimensionReport, CandidateSkillsSummary, ExperienceMatchSummary
from models.bias import BiasLog

class CandidateBundle(BaseModel):
    candidate_name: str
    role_type: RoleType
    raw_cv: str = Field(..., description="Plain-text CV content extracted from the uploaded PDF before any LLM sees it")
    mcq_score: float
    programming_answers: List[str] = Field(..., min_length=2, max_length=2)
    session1_transcript: str
    session2_transcript: str

class InterviewState(TypedDict, total=False):
    candidate_id: str
    candidate_name: str
    role_type: RoleType
    raw_cv: str                          # Written by Ingestion Agent; passed to CV Parsing Agent
    mcq_score: float
    programming_answers: List[str]
    session1_transcript: str
    session2_transcript: str
    clean_session1: str
    clean_session2: str
    mcq_responses: Optional[Dict[str, str]]
    interviewer_bias_flags: Optional[List]
    communication_score: Optional[EvalScore]
    technical_score: Optional[TechnicalDimensionReport]      # CHANGED from Optional[EvalScore]
    problem_solving_score: Optional[EvalScore]
    cultural_score: Optional[EvalScore]
    candidate_skills_summary: Optional[CandidateSkillsSummary]
    cv_experience_match: Optional[ExperienceMatchSummary]
    bias_log: Optional[BiasLog]
    bias_clear: Optional[bool]
    feedback_report: Optional[FeedbackReport]
    error: Optional[str]
