import os
import json
import logging
from typing import Tuple, Dict, Any

from agents.base_agent import BaseAgent
from models.evaluation import CandidateSkillsSummary, ExperienceMatchSummary

logger = logging.getLogger("CVParsingAgent")


class CVParsingAgent(BaseAgent):
    """
    Two-pass CV processing agent.

    Pass 1 — Anonymise:
        Takes raw CV text and produces a CandidateSkillsSummary with
        all PII stripped. The LLM sees the raw CV only in this pass.

    Pass 2 — Match:
        Takes the anonymised CandidateSkillsSummary and the role rubric's
        required_skills list. The raw CV never enters this pass. Produces
        an ExperienceMatchSummary comparing candidate skills to role needs.

    WHY THIS INHERITS FROM BaseAgent
    ---------------------------------
    BaseAgent gives us:
      - self.llm  →  the AzureChatOpenAI client, already configured from .env
      - self.call_llm_structured(system, user, response_model)
            → makes the LLM call AND forces the output to match a Pydantic model
            → handles retries (max_retries=3 on the client)
            → returns (PydanticInstance | None, token_metadata_dict)

    We don't call self.llm.invoke() directly. We always go through
    call_llm_structured() because it handles structured output enforcement,
    token tracking, and error isolation for us.
    """

    def __init__(self):
        super().__init__()
        logger.info("CV Parsing Agent initialized.")

    # ==========================================================================
    # PRIVATE HELPER — Load rubric to get required_skills + min_experience_years
    # ==========================================================================

    def _load_rubric(self, role_type: Any) -> Dict[str, Any]:
        """
        Loads the role rubric JSON from disk.
        Returns the parsed dict, or an empty dict with defaults on failure.

        Uses an absolute path resolved from this file's location so the rubric
        loads correctly regardless of which directory the script is run from.
        """
        role_str = role_type.value if hasattr(role_type, "value") else str(role_type)
        role_str = role_str.strip().upper()

        filename_map = {
            "AI":      "ai_engineer.json",
            "SWE":     "swe.json",
            "BA":      "ba.json",
            "TRAINEE": "trainee.json"
        }
        filename = filename_map.get(role_str, f"{role_str.lower()}.json")

        # __file__ = agents/cv_parsing_agent.py
        # Go up one directory to project root, then into rubrics/
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        rubric_path = os.path.join(project_root, "rubrics", filename)

        logger.debug(f"Loading rubric from: {rubric_path}")

        try:
            with open(rubric_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load rubric at {rubric_path}: {e}. Returning empty defaults.")
            return {"required_skills": [], "min_experience_years": 0}


    # ==========================================================================
    # PASS 1 — Anonymise the raw CV into a CandidateSkillsSummary
    # ==========================================================================

    def _anonymise_cv(self, raw_cv: str) -> CandidateSkillsSummary:
        """
        LLM Call #1: Strip all PII from the raw CV text.

        INPUT:  raw CV text (may contain names, employers, universities, dates)
        OUTPUT: CandidateSkillsSummary — zero PII, structured, safe for any agent

        HOW call_llm_structured WORKS HERE
        ------------------------------------
        We pass response_model=CandidateSkillsSummary. Internally, BaseAgent does:

            structured_llm = self.llm.with_structured_output(CandidateSkillsSummary)
            response = structured_llm.invoke([system_msg, user_msg])

        .with_structured_output() tells the LLM to respond in a format that matches
        the Pydantic schema. LangChain serialises the schema, sends it as a JSON
        schema constraint to the API, and parses the response back into a
        CandidateSkillsSummary instance automatically.

        If the LLM output doesn't match the schema (e.g. returns wrong field name),
        .with_structured_output() will raise and call_llm_structured() catches it,
        logs the error, and returns (None, token_metadata).

        We check for None below and return a safe fallback if pass 1 fails.
        """
        logger.info("CV Parsing — Pass 1: Anonymising raw CV text...")

        system_prompt = (
            "You are a senior data anonymisation specialist. Your task is to process "
            "a candidate's raw CV and extract structured information while strictly removing "
            "all personally identifiable information (PII).\n\n"

            "ANONYMISATION RULES — apply every one of these without exception:\n"
            "1. Personal names → Remove entirely\n"
            "2. Employer / company names → Remove entirely\n"
            "3. University / institution names → Remove entirely "
            "   (keep the degree title and field of study only, e.g. 'MSc Computer Science')\n"
            "4. Specific project or product names → Genericise "
            "   (e.g. 'Contributed to TensorFlow' → 'Open-source ML framework contributor')\n"
            "5. Specific dates and years → Convert to durations "
            "   (e.g. '2018–2023' → '5 years'; 'June 2021' → irrelevant, derive duration)\n"
            "6. City / country / region names → Remove entirely\n"
            "7. GPA, class rank, honours designations → Remove entirely\n"
            "8. Hobbies and personal activities → Remove entirely\n"
            "9. Technical skills → KEEP exactly as listed\n"
            "10. Achievement metrics without proper nouns → KEEP "
            "    (e.g. 'Reduced latency by 40%', 'Serving 10M requests/day')\n\n"

            "SKILL EXTRACTION RULES — this is critical:\n"
            "Extract technical_skills from ALL sections of the CV, not just a 'Skills' heading.\n"
            "Specifically look in:\n"
            "  • Skills / Technical Skills section (explicit list)\n"
            "  • Projects section — extract every tool, library, framework, language mentioned\n"
            "  • Work Experience / Internship bullets — extract technologies used in each role\n"
            "  • Education / Coursework — extract relevant technical subjects or tools\n"
            "  • Certifications — extract the skill the certification validates\n"
            "For example: if a project description says 'Built a REST API using Spring Boot and JPA', "
            "extract: ['Spring Boot', 'JPA', 'REST APIs']. "
            "If a work experience bullet says 'Trained classification models using scikit-learn', "
            "extract: ['Machine Learning', 'scikit-learn', 'Python']. "
            "Deduplicate the final list — each skill should appear only once.\n\n"

            "Return a structured response with these exact fields:\n"
            "- technical_skills: a deduplicated list of all technical skills found across the entire CV\n"
            "- experience_duration: total years of professional experience as a plain string e.g. '3 years'\n"
            "- domain_areas: list of high-level domains worked in, no company names\n"
            "- education_level: degree title + field only, no institution\n"
            "- notable_achievements: list of quantified accomplishments, no proper nouns"
        )

        user_prompt = (
            f"Process this CV and extract the anonymised structured summary:\n\n"
            f"--- RAW CV START ---\n{raw_cv}\n--- RAW CV END ---"
        )

        # call_llm_structured returns: (CandidateSkillsSummary | None, token_metadata_dict)
        result, token_meta = self.call_llm_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=CandidateSkillsSummary
        )

        if not result:
            logger.error("Pass 1 failed — returning empty fallback CandidateSkillsSummary.")
            # Return a safe, valid empty model so Pass 2 can still run
            return CandidateSkillsSummary(
                technical_skills=[],
                experience_duration="Unknown",
                domain_areas=[],
                education_level="Unknown",
                notable_achievements=[]
            )

        logger.info(f"Pass 1 complete. Skills found: {result.technical_skills}")
        return result

    # ==========================================================================
    # PASS 2 — Match the anonymised summary against the role rubric
    # ==========================================================================

    def _match_skills(
        self,
        skills_summary: CandidateSkillsSummary,
        required_skills: list,
        min_experience_years: int
    ) -> ExperienceMatchSummary:
        """
        LLM Call #2: Compare the anonymised summary to the rubric requirements.

        INPUT:  CandidateSkillsSummary (no raw CV — PII boundary enforced here)
                + required_skills list from rubric
                + min_experience_years from rubric
        OUTPUT: ExperienceMatchSummary

        WHY WE STILL USE AN LLM FOR THIS (not just set intersection)
        ---------------------------------------------------------------
        The required_skills list might say "Python" and the candidate summary
        might say "Python 3.11". A simple set intersection misses this. The LLM
        can reason about semantic equivalence (e.g. "PyTorch" matching "Deep
        Learning Framework") while we keep the comparison rubric-anchored
        rather than free-form.

        The response_model=ExperienceMatchSummary constraint forces:
        - domain_match to be one of: "strong" | "moderate" | "weak"   (Literal type)
        - overall_match_rating to be one of the same three values
        If the LLM tries to return anything else, Pydantic rejects it.
        """
        logger.info("CV Parsing — Pass 2: Matching skills against role rubric...")

        system_prompt = (
            "You are a technical recruiter comparing a candidate's anonymised skill profile "
            "against a role's required skills. You must produce a structured skills match report.\n\n"

            "IMPORTANT: You are working with an ALREADY ANONYMISED profile. "
            "Do not reference any specific names, companies, or institutions.\n\n"

            "Rating definitions:\n"
            "  strong   → Candidate clearly meets or exceeds the role requirements\n"
            "  moderate → Candidate partially meets requirements with some notable gaps\n"
            "  weak     → Candidate has significant gaps relative to the role requirements\n\n"

            "Return a structured response with these exact fields:\n"
            "- required_skills_present: list of skills from the required list that the candidate has\n"
            "- required_skills_missing: list of skills from the required list that the candidate lacks\n"
            "- years_of_experience: the candidate's experience duration string\n"
            "- role_min_experience: the minimum experience required by the role\n"
            "- domain_match: one of 'strong', 'moderate', or 'weak'\n"
            "- overall_match_rating: one of 'strong', 'moderate', or 'weak'"
        )

        # We serialize the skills_summary to a clean dict for the prompt.
        # model_dump() converts the Pydantic model to a plain Python dict.
        summary_dict = skills_summary.model_dump()

        user_prompt = (
            f"CANDIDATE ANONYMISED PROFILE:\n{json.dumps(summary_dict, indent=2)}\n\n"
            f"ROLE REQUIRED SKILLS: {required_skills}\n"
            f"ROLE MINIMUM EXPERIENCE: {min_experience_years} years"
        )

        result, token_meta = self.call_llm_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ExperienceMatchSummary
        )

        if not result:
            logger.error("Pass 2 failed — returning empty fallback ExperienceMatchSummary.")
            return ExperienceMatchSummary(
                required_skills_present=[],
                required_skills_missing=required_skills,
                years_of_experience=skills_summary.experience_duration,
                role_min_experience=f"{min_experience_years} years",
                domain_match="weak",
                overall_match_rating="weak"
            )

        logger.info(f"Pass 2 complete. Overall match: {result.overall_match_rating}")
        return result

    # ==========================================================================
    # PUBLIC METHOD — Called by the pipeline node
    # ==========================================================================

    def parse(
        self,
        raw_cv: str,
        role_type: Any
    ) -> Tuple[CandidateSkillsSummary, ExperienceMatchSummary]:
        """
        Entry point for the pipeline node.

        Orchestrates Pass 1 → Pass 2 in sequence.
        The pipeline node calls this single method and gets both outputs back.

        Returns:
            Tuple[CandidateSkillsSummary, ExperienceMatchSummary]
        """
        # 1. Load the rubric to get required_skills and min_experience_years
        rubric = self._load_rubric(role_type)
        required_skills = rubric.get("required_skills", [])
        min_experience_years = rubric.get("min_experience_years", 0)

        logger.info(
            f"CV Parsing started for role: {role_type} | "
            f"Required skills: {required_skills} | "
            f"Min experience: {min_experience_years} years"
        )

        # 2. Pass 1 — anonymise the raw CV
        skills_summary = self._anonymise_cv(raw_cv)

        # 3. Pass 2 — match against rubric (raw_cv does NOT enter this call)
        experience_match = self._match_skills(skills_summary, required_skills, min_experience_years)

        return skills_summary, experience_match
