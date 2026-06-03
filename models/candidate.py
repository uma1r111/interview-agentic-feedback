from pydantic import BaseModel, Field
from typing import Optional, List, TypedDict
from models.enums import RoleType
from models.evaluation import EvalScore, FeedbackReport
from models.bias import BiasLog

class CandidateBundle(BaseModel):
    candidate_name: str
    role_type: RoleType
    mcq_score: float
    programming_answers: List[str] = Field(..., min_length=2, max_length=2)
    session1_transcript: str
    session2_transcript: str

class InterviewState(TypedDict, total=False):
    candidate_id: str
    candidate_name: str
    role_type: RoleType
    mcq_score: float
    programming_answers: List[str]
    session1_transcript: str
    session2_transcript: str
    communication_score: Optional[EvalScore]
    technical_score: Optional[EvalScore]
    problem_solving_score: Optional[EvalScore]
    cultural_score: Optional[EvalScore]
    bias_log: Optional[BiasLog]
    bias_clear: Optional[bool]
    feedback_report: Optional[FeedbackReport]
    error: Optional[str]