"""
Isolation test for CVParsingAgent.

Runs ONLY the two-pass CV parsing logic directly — no API server,
no LangGraph pipeline, no other agents involved.

Usage:
    python tests/test_cv_parsing_agent.py <path_to_cv.pdf> <role_type>

Examples:
    python tests/test_cv_parsing_agent.py fixtures/sample_cv.pdf AI
    python tests/test_cv_parsing_agent.py fixtures/sample_cv.pdf SWE
    python tests/test_cv_parsing_agent.py fixtures/sample_cv.pdf BA
    python tests/test_cv_parsing_agent.py fixtures/sample_cv.pdf Trainee

Role types available: AI | SWE | BA | Trainee
"""
import sys
import os
import json

# Add project root to path so imports work when run from any directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env before importing any agent (BaseAgent reads env vars at __init__ time)
from dotenv import load_dotenv
load_dotenv()

from services.pdf_extractor import PDFExtractorService
from agents.cv_parsing_agent import CVParsingAgent
from models.enums import RoleType


def run_cv_parsing_test(pdf_path: str, role_type_str: str):
    print(f"\n{'='*65}")
    print("CV PARSING AGENT — Isolation Test")
    print(f"{'='*65}")
    print(f"PDF path  : {pdf_path}")
    print(f"Role type : {role_type_str}")

    # ------------------------------------------------------------------
    # Step 1: Validate inputs
    # ------------------------------------------------------------------
    if not os.path.exists(pdf_path):
        print(f"\n[Error] PDF not found: {pdf_path}")
        sys.exit(1)

    try:
        role_type = RoleType(role_type_str)
    except ValueError:
        valid = [e.value for e in RoleType]
        print(f"\n[Error] Invalid role type '{role_type_str}'. Choose from: {valid}")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 2: Extract text from PDF (same step the API layer does)
    # ------------------------------------------------------------------
    print("\n[1/3] Extracting text from PDF...")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    extractor = PDFExtractorService()
    try:
        raw_cv_text = extractor.extract_text(pdf_bytes)
        print(f"      [OK] Extracted {len(raw_cv_text):,} characters from {len(pdf_bytes):,} bytes")
    except ValueError as e:
        print(f"      [Error] Extraction failed: {e}")
        sys.exit(1)

    # Optional: print first 200 chars so you can verify it read correctly
    print("\n      --- Raw CV preview (first 200 chars) ---")
    print(f"      {raw_cv_text[:200].replace(chr(10), ' ')}")
    print("      ---")

    # ------------------------------------------------------------------
    # Step 3: Run Pass 1 — Anonymise
    # ------------------------------------------------------------------
    print("\n[2/3] Running Pass 1 — Anonymisation (LLM call #1)...")
    agent = CVParsingAgent()

    # Call _anonymise_cv directly so we can inspect Pass 1 output alone
    skills_summary = agent._anonymise_cv(raw_cv_text)  # pyright: ignore [reportPrivateUsage]

    print("      [OK] Pass 1 complete")
    print("\n      CandidateSkillsSummary:")
    print(f"      Technical skills    : {skills_summary.technical_skills}")
    print(f"      Experience duration : {skills_summary.experience_duration}")
    print(f"      Domain areas        : {skills_summary.domain_areas}")
    print(f"      Education level     : {skills_summary.education_level}")
    print(f"      Notable achievements: {skills_summary.notable_achievements}")

    # ------------------------------------------------------------------
    # Step 4: Run Pass 2 — Match against rubric
    # ------------------------------------------------------------------
    print("\n[3/3] Running Pass 2 — Skills Match (LLM call #2)...")

    # Load rubric to show what required_skills were used
    rubric = agent._load_rubric(role_type)  # pyright: ignore [reportPrivateUsage]
    required_skills = rubric.get("required_skills", [])
    min_exp = rubric.get("min_experience_years", 0)

    print(f"      Rubric required skills : {required_skills}")
    print(f"      Rubric min experience  : {min_exp} years")

    experience_match = agent._match_skills(skills_summary, required_skills, min_exp)  # pyright: ignore [reportPrivateUsage]

    print("      [OK] Pass 2 complete")

    # ------------------------------------------------------------------
    # Step 5: Print final ExperienceMatchSummary
    # ------------------------------------------------------------------
    print(f"\n{'='*65}")
    print("RESULTS — ExperienceMatchSummary")
    print(f"{'='*65}")
    print(f"Skills PRESENT  : {experience_match.required_skills_present}")
    print(f"Skills MISSING  : {experience_match.required_skills_missing}")
    print(f"Years experience: {experience_match.years_of_experience}")
    print(f"Role minimum    : {experience_match.role_min_experience}")
    print(f"Domain match    : {experience_match.domain_match}")
    print(f"Overall rating  : {experience_match.overall_match_rating}")

    # Also dump both outputs as JSON so you can inspect the full structure
    print(f"\n{'='*65}")
    print("FULL JSON OUTPUT")
    print(f"{'='*65}")
    output = {
        "candidate_skills_summary": skills_summary.model_dump(),
        "cv_experience_match": experience_match.model_dump()
    }
    print(json.dumps(output, indent=2))
    print("\n[SUCCESS] Isolation test complete.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    run_cv_parsing_test(
        pdf_path=sys.argv[1],
        role_type_str=sys.argv[2]
    )
