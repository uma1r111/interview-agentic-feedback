import re
import logging
from typing import List, Tuple
from models.evaluation import InterviewerBiasFlag

logger = logging.getLogger("TranscriptScreener")

# ==============================================================================
# Bias Pattern Registry
# Each entry: (regex_pattern, bias_category, severity, rationale)
# Patterns target interviewer turns only — candidate responses are never scanned.
# ==============================================================================

BIAS_PATTERNS: List[Tuple[str, str, str, str]] = [

    # --- Family & Marital Status ---
    (
        r"\b(married|single|divorced|spouse|husband|wife|partner|relationship status)\b",
        "marital_status",
        "high",
        "Questions about marital status are not relevant to job performance and may disadvantage certain candidates."
    ),
    (
        r"\b(children|kids|child|family planning|pregnant|pregnancy|maternity|paternity|childcare|babysitter)\b",
        "family_status",
        "high",
        "Questions about children or family planning are not relevant to job performance and disproportionately affect women."
    ),
    (
        r"\b(family commitments|family responsibilities|family obligations|domestic responsibilities)\b",
        "family_status",
        "high",
        "Asking about family commitments implies assumptions about availability that should not factor into hiring."
    ),

    # --- Age ---
    (
        r"\b(how old are you|what is your age|your age|date of birth|born in|graduation year implies age)\b",
        "age",
        "high",
        "Age-related questions are not relevant to job performance and may constitute age discrimination."
    ),
    (
        r"\b(how many years (until|till|before) (you )?retire|retirement plans|nearing retirement)\b",
        "age",
        "high",
        "Questions implying retirement proximity are age-discriminatory."
    ),
    (
        r"\b(young|older|too experienced|overqualified for your age)\b",
        "age",
        "medium",
        "Language referencing age relative to experience may signal age bias."
    ),

    # --- Religion ---
    (
        r"\b(religion|religious|church|mosque|temple|synagogue|pray|prayer|sabbath|ramadan|fasting|religious holidays|faith|beliefs)\b",
        "religion",
        "high",
        "Questions about religious practice or affiliation are not relevant to job performance."
    ),
    (
        r"\b(work on (sundays|saturdays|fridays)|weekend availability due to|religious day off)\b",
        "religion",
        "medium",
        "Questions about specific-day availability without business justification may indirectly target religious observance."
    ),

    # --- Nationality & Ethnicity ---
    (
        r"\b(where are you (originally )?from|where were you born|country of origin|native country|hometown country|ethnic background|ethnicity|race|racial)\b",
        "nationality_ethnicity",
        "high",
        "Questions about national origin or ethnicity are not relevant to job performance and may constitute discrimination."
    ),
    (
        r"\b(accent|english as (a )?second language|first language|mother tongue|native speaker)\b",
        "nationality_ethnicity",
        "medium",
        "Questions about accent or language origin may indirectly target national or ethnic background unless directly relevant to the role."
    ),
    (
        r"\b(visa|work permit|right to work|citizenship|permanent resident|immigration status|are you a citizen)\b",
        "immigration_status",
        "medium",
        "While right-to-work verification is legitimate, phrasing matters — questions should confirm authorization, not probe immigration history."
    ),

    # --- Gender ---
    (
        r"\b(as a woman|as a man|being female|being male|gender|are you (a )?(female|male|woman|man|lady|gentleman))\b",
        "gender",
        "high",
        "Questions referencing gender are not relevant to job performance evaluation."
    ),
    (
        r"\b(maternity leave|paternity leave|are you planning (to have|on having) (a baby|children|kids))\b",
        "gender",
        "high",
        "Questions about parental leave plans are gender-discriminatory and not relevant to hiring decisions."
    ),

    # --- Disability & Health ---
    (
        r"\b(disability|disabled|medical condition|health condition|mental health|illness|chronic|handicap|wheelchair|special needs|are you healthy)\b",
        "disability_health",
        "high",
        "Questions about health or disability status are not relevant to job performance unless directly related to essential job functions."
    ),
    (
        r"\b(sick days|how often (do you|are you) sick|medical history|doctor|medication)\b",
        "disability_health",
        "medium",
        "Questions probing health history or sick day frequency may discriminate against candidates with medical conditions."
    ),

    # --- Financial Status ---
    (
        r"\b(debt|bankrupt|bankruptcy|credit (score|history|check)|financial (problems|difficulties|trouble)|loan|mortgage)\b",
        "financial_status",
        "medium",
        "Questions about personal financial history are not relevant to most roles and may disadvantage economically vulnerable candidates."
    ),
]


# ==============================================================================
# Speaker Isolation Utilities
# ==============================================================================

def extract_interviewer_turns(transcript: str) -> List[Tuple[str, str]]:
    """
    Parses a diarized transcript and returns only interviewer speech turns.
    Each turn is returned as a tuple: (speaker_label, spoken_text).

    Supports diarized format:
        [00:01:15] Interviewer_Technical_Senior: Question text here.
    """
    interviewer_turns = []

    # Match lines with a speaker label containing "Interviewer" (case-insensitive)
    pattern = re.compile(
        r"\[\d{2}:\d{2}:\d{2}\]\s+(Interviewer[^:]*?):\s+(.+)",
        re.IGNORECASE
    )

    for line in transcript.splitlines():
        match = pattern.match(line.strip())
        if match:
            speaker = match.group(1).strip()
            text = match.group(2).strip()
            interviewer_turns.append((speaker, text))

    return interviewer_turns


# ==============================================================================
# Core Screening Function
# ==============================================================================

class TranscriptScreener:
    """
    Lightweight rule-based transcript pre-screener.
    Scans interviewer turns for protected-characteristic question patterns
    before any evaluation agent runs.
    Does not make LLM calls — purely pattern-based for speed and reliability.
    """

    def __init__(self):
        # Compile all patterns once at init for performance
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), category, severity, rationale)
            for pattern, category, severity, rationale in BIAS_PATTERNS
        ]
        logger.info("TranscriptScreener initialized with compiled bias pattern registry.")

    def screen(self, session1_transcript: str, session2_transcript: str) -> List[InterviewerBiasFlag]:
        """
        Screens both session transcripts for biased interviewer questions.
        Returns a list of InterviewerBiasFlag objects — empty list means clean.

        Args:
            session1_transcript: Full diarized text of Session 1 (technical panel)
            session2_transcript: Full diarized text of Session 2 (HR behavioural)

        Returns:
            List[InterviewerBiasFlag]: All detected flags across both sessions.
        """
        flags: List[InterviewerBiasFlag] = []
        seen_questions: set = set()  # Deduplicate identical questions flagged by multiple patterns

        combined_sessions = [
            ("Session 1", session1_transcript),
            ("Session 2", session2_transcript)
        ]

        for session_label, transcript in combined_sessions:
            if not transcript or not transcript.strip():
                logger.warning(f"TranscriptScreener: {session_label} transcript is empty — skipping.")
                continue

            interviewer_turns = extract_interviewer_turns(transcript)

            if not interviewer_turns:
                logger.warning(
                    f"TranscriptScreener: No interviewer turns detected in {session_label}. "
                    "Check transcript format — expected '[HH:MM:SS] Interviewer_X: text'"
                )
                continue

            logger.info(f"TranscriptScreener: Scanning {len(interviewer_turns)} interviewer turns in {session_label}.")

            for speaker, question_text in interviewer_turns:
                for compiled_pattern, category, severity, rationale in self.compiled_patterns:
                    if compiled_pattern.search(question_text):

                        # Deduplicate — same question text flagged by multiple patterns
                        dedup_key = f"{question_text.lower().strip()}::{category}"
                        if dedup_key in seen_questions:
                            continue
                        seen_questions.add(dedup_key)

                        flag = InterviewerBiasFlag(
                            question_text=f"[{session_label} — {speaker}]: {question_text}",
                            bias_category=category,
                            severity=severity,
                            rationale=rationale
                        )
                        flags.append(flag)
                        logger.warning(
                            f"TranscriptScreener: Bias flag raised — "
                            f"Category: {category} | Severity: {severity} | "
                            f"Question: '{question_text[:80]}...'"
                        )

        if not flags:
            logger.info("TranscriptScreener: No biased interviewer questions detected. Transcripts cleared.")
        else:
            logger.warning(
                f"TranscriptScreener: Screening complete. "
                f"{len(flags)} flag(s) raised across both sessions."
            )

        return flags