from pydantic import BaseModel, Field
from typing import Dict
from models.candidate import CandidateBundle
from models.enums import Decision


class IntakeRequestPayload(BaseModel):
    """Unified POST body bundle wrapping candidate profiles and digital test inputs."""
    candidate_data: CandidateBundle
    mcq_selections: Dict[str, str] = Field(
        ...,
        description="Dictionary mapping question IDs to the candidate's exact raw answer selections"
    )


class DecisionPatchPayload(BaseModel):
    """Strict data payload covering human-override hiring actions."""
    decision: Decision