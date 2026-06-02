from enum import Enum

class RoleType(str, Enum):
    SWE = "SWE"
    AI_ENGINEER = "AI"
    BUSINESS_ANALYST = "BA"
    TRAINEE = "Trainee"

class Recommendation(str, Enum):
    STRONG_YES = "Strong Yes"
    YES = "Yes"
    MAYBE = "Maybe"
    NO = "No"

class Decision(str, Enum):
    HIRED = "Hired"
    REJECTED = "Rejected"
    HOLD = "Hold"
