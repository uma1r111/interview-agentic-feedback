from pydantic import BaseModel, Field
from typing import Optional, List
from models.enums import RoleType
from models.evaluation import EvalScore, FeedbackReport
from models.bias import BiasLog

class CandidateBundle(BaseModel):
    candidate_name: str
    role_type: RoleType
    mcq_score: float
    programming_answers: List[str] = Field(..., min_items=2, max_items=2)
    session1_transcript: str
    session2_transcript: str

class InterviewState(dict):
    candidate_id: str
    candidate_name: str
    role_type: RoleType
    mcq_score: float
    programming_answers: List[str]
    session1_transcript: str
    session2_transcript: str

    # Fully Resolved Strongly Typed Fields
    communication_score: Optional[EvalScore] = None
    technical_score: Optional[EvalScore] = None
    problem_solving_score: Optional[EvalScore] = None
    cultural_score: Optional[EvalScore] = None

    bias_log: Optional[BiasLog] = None
    bias_clear: Optional[bool] = None
    feedback_report: Optional[FeedbackReport] = None
    error: Optional[str] = None