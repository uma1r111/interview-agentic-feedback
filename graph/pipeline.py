import logging
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END

from models.candidate import InterviewState
from agents.ingestion_agent import IngestionAgent
from agents.communication_agent import CommunicationAgent
from agents.technical_depth_agent import TechnicalDepthAgent
from agents.problem_solving_agent import ProblemSolvingAgent
from agents.cultural_alignment_agent import CulturalAlignmentAgent
from agents.bias_detection_agent import BiasDetectionAgent
from agents.feedback_compiler_agent import FeedbackCompilerAgent
from agents.cv_parsing_agent import CVParsingAgent
from services.transcript_preprocessor import TranscriptPreprocessor

logger = logging.getLogger("InterviewPipeline")


# ==============================================================================
# Graph Node Execution Wrappers
# ==============================================================================

def ingestion_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Validates payload bundles and instantiates global pipeline state."""
    logger.info("--- START NODE: INGESTION ---")

    raw_payload = state.get("raw_payload", {})
    mcq_responses = state.get("mcq_responses", {})

    if not raw_payload:
        raw_payload = {
            "candidate_name":      state.get("candidate_name"),
            "role_type":           state.get("role_type"),
            "raw_cv":              state.get("raw_cv"),
            "mcq_score":           state.get("mcq_score"),
            "programming_answers": state.get("programming_answers"),
            "session1_transcript": state.get("session1_transcript"),
            "session2_transcript": state.get("session2_transcript")
        }

    # Defensive patch: if raw_cv wasn't in raw_payload, pull from flat state
    if "raw_cv" not in raw_payload and state.get("raw_cv"):
        raw_payload["raw_cv"] = state.get("raw_cv")

    agent = IngestionAgent()
    updated_state, success = agent.process_intake(raw_payload, mcq_responses)

    if not success:
        logger.error(f"Ingestion processing failure: {updated_state.get('error')}")
        return {"error": updated_state.get("error")}

    return {
        "candidate_id":        updated_state.get("candidate_id"),
        "candidate_name":      updated_state.get("candidate_name"),
        "role_type":           updated_state.get("role_type"),
        "raw_cv":              updated_state.get("raw_cv"),
        "mcq_score":           updated_state.get("mcq_score"),
        "programming_answers": updated_state.get("programming_answers"),
        "session1_transcript": updated_state.get("session1_transcript"),
        "session2_transcript": updated_state.get("session2_transcript"),
        "mcq_responses":       None,   # P1-05: drop raw MCQ selections after ingestion consumes them
        "error": None
    }

def preprocess_transcript_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Cleans raw diarized transcripts into structured Q&A pairs to reduce noise."""
    logger.info("--- START NODE: TRANSCRIPT PREPROCESSOR ---")
    preprocessor = TranscriptPreprocessor()
    clean_s1 = preprocessor.process(state.get("session1_transcript", ""))
    clean_s2 = preprocessor.process(state.get("session2_transcript", ""))
    return {
        "clean_session1": clean_s1,
        "clean_session2": clean_s2
    }

def transcript_bias_screen_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Lightweight rule-based pre-screen of interviewer turns in both session transcripts.
    Runs after ingestion and before parallel evaluation agents.
    Does not make LLM calls — purely pattern-based.
    Flags are soft warnings — pipeline continues regardless of findings.
    """
    logger.info("--- START NODE: TRANSCRIPT BIAS SCREENER ---")

    from services.transcript_screener import TranscriptScreener

    screener = TranscriptScreener()
    flags = screener.screen(
        session1_transcript=state.get("session1_transcript", ""),
        session2_transcript=state.get("session2_transcript", "")
    )

    if flags:
        logger.warning(
            f"TranscriptBiasScreener: {len(flags)} interviewer bias flag(s) detected. "
            f"Pipeline continues — flags will be surfaced in FeedbackReport."
        )
    else:
        logger.info("TranscriptBiasScreener: Transcripts cleared. No interviewer bias detected.")

    return {"interviewer_bias_flags": flags if flags else []}

def communication_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates text-based dialogue dynamics inside Session 1."""
    logger.info("--- START NODE: COMMUNICATION EVALUATOR ---")
    agent = CommunicationAgent()
    score, _ = agent.evaluate_communication(state.get("clean_session1", ""))
    return {"communication_score": score}


def technical_depth_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates code optimization alongside systems architecture notes."""
    logger.info("--- START NODE: TECHNICAL DEPTH EVALUATOR ---")
    agent = TechnicalDepthAgent()
    score, _ = agent.evaluate_technical_depth(
        role_type=state.get("role_type"),
        session1_transcript=state.get("clean_session1", ""),
        programming_answers=state.get("programming_answers", ["", ""])
    )
    return {"technical_score": score}


def problem_solving_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates conceptual mapping and structural breakdown behaviors."""
    logger.info("--- START NODE: PROBLEM SOLVING EVALUATOR ---")
    agent = ProblemSolvingAgent()
    score, _ = agent.evaluate_problem_solving(state.get("clean_session1", ""))
    return {"problem_solving_score": score}


def cultural_alignment_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates team motivation and values markers strictly from Session 2."""
    logger.info("--- START NODE: CULTURAL ALIGNMENT EVALUATOR ---")
    agent = CulturalAlignmentAgent()
    score, _ = agent.evaluate_cultural_alignment(state.get("clean_session2", ""))
    return {"cultural_score": score}


def cv_parsing_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs the two-pass CV Parsing Agent in parallel with the four evaluation agents.
    Pass 1 anonymises the raw CV. Pass 2 matches against the role rubric.
    The raw CV never reaches any evaluation agent — only the anonymised summary does.
    """
    logger.info("--- START NODE: CV PARSING AGENT ---")

    raw_cv = state.get("raw_cv", "")
    role_type = state.get("role_type")

    if not raw_cv:
        logger.warning("cv_parsing_node: raw_cv is empty — skipping CV parsing.")
        return {
            "candidate_skills_summary": None,
            "cv_experience_match": None
        }

    agent = CVParsingAgent()
    skills_summary, experience_match = agent.parse(
        raw_cv=raw_cv,
        role_type=role_type
    )

    return {
        "candidate_skills_summary": skills_summary,
        "cv_experience_match":      experience_match
    }


def bias_detection_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Subjective language sweep over all dimensional observations."""
    logger.info("--- START NODE: BIAS DETECTION GUARDRAIL GATE ---")
    agent = BiasDetectionAgent()
    log, clean_comm, clean_tech, clean_prob, clean_cult, clear_flag, _ = agent.analyze_and_sanitize_scores(
        communication=state.get("communication_score"),
        technical=state.get("technical_score"),
        problem_solving=state.get("problem_solving_score"),
        cultural=state.get("cultural_score")
    )
    return {
        "bias_log":            log,
        "communication_score": clean_comm,
        "technical_score":     clean_tech,
        "problem_solving_score": clean_prob,
        "cultural_score":      clean_cult,
        "bias_clear":          clear_flag
    }


def feedback_compiler_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Synthesizes all individual dimension evaluations into an executive summary."""
    logger.info("--- START NODE: FEEDBACK COMPILER ---")
    agent = FeedbackCompilerAgent()

    cv_match = state.get("cv_experience_match")

    report, _ = agent.compile_final_report(
        candidate_name=state.get("candidate_name", ""),
        role_type=state.get("role_type"),
        mcq_score=state.get("mcq_score", 0.0),
        programming_answers=state.get("programming_answers", ["", ""]),
        communication=state.get("communication_score"),
        technical=state.get("technical_score"),
        problem_solving=state.get("problem_solving_score"),
        cultural=state.get("cultural_score"),
        bias_clear=state.get("bias_clear", False),
        cv_experience_match=cv_match,
        interviewer_bias_flags=state.get("interviewer_bias_flags", [])    # ADD THIS
    )

    # Attach cv_experience_match to the report for persistence and dashboard rendering
    if cv_match and report:
        report.cv_experience_match = cv_match
        logger.info("CV experience match attached to FeedbackReport.")

    return {"feedback_report": report}


# ==============================================================================
# Conditional Edge Routing
# ==============================================================================

def route_after_ingestion(state: Dict[str, Any]) -> Literal["abort_pipeline", "continue"]:
    """Aborts if ingestion failed, otherwise allows parallel fan-out via direct edges."""
    if state.get("error"):
        logger.error("Ingestion validation failure. Blocking downstream agents.")
        return "abort_pipeline"
    return "continue"


def route_after_bias_gate(state: Dict[str, Any]) -> Literal["compile_report", "abort_pipeline"]:
    """Inspects compliance lock flags to authorize or block final compilation."""
    if state.get("error") or not state.get("bias_clear"):
        logger.error("Conditional Edge: Verification conditions breached. Aborting pipeline.")
        return "abort_pipeline"

    logger.info("Conditional Edge: Security parameters verified. Authorizing feedback report assembly.")
    return "compile_report"


# ==============================================================================
# Pipeline Topology
# ==============================================================================

def create_interview_graph():
    """Builds, connects, and compiles the stateful LangGraph pipeline execution engine."""
    builder = StateGraph(InterviewState)

    # Register all nodes
    builder.add_node("ingest",                   ingestion_node)
    builder.add_node("preprocess_transcripts",   preprocess_transcript_node)
    builder.add_node("screen_transcript_bias",      transcript_bias_screen_node)
    builder.add_node("evaluate_communication",   communication_node)
    builder.add_node("evaluate_technical",       technical_depth_node)
    builder.add_node("evaluate_problem_solving", problem_solving_node)
    builder.add_node("evaluate_cultural",        cultural_alignment_node)
    builder.add_node("parse_cv",                 cv_parsing_node)
    builder.add_node("verify_bias_gate",         bias_detection_node)
    builder.add_node("compile_report",           feedback_compiler_node)

    # Entry point
    builder.add_edge(START, "ingest")

    # Conditional edge: abort on ingestion error, otherwise go to preprocessor
    builder.add_conditional_edges(
        "ingest",
        route_after_ingestion,
        {
            "abort_pipeline": END,
            "continue":       "preprocess_transcripts"
        }
    )

    builder.add_edge("preprocess_transcripts", "screen_transcript_bias")

    # Transcript screener runs synchronously before parallel fan-out
    # Soft warning only — pipeline always continues from here
    builder.add_edge("screen_transcript_bias", "evaluate_communication")
    builder.add_edge("screen_transcript_bias", "evaluate_technical")
    builder.add_edge("screen_transcript_bias", "evaluate_problem_solving")
    builder.add_edge("screen_transcript_bias", "evaluate_cultural")
    builder.add_edge("screen_transcript_bias", "parse_cv")

    # Fan-in — all 5 parallel nodes must complete before bias gate fires
    builder.add_edge(
        [
            "evaluate_communication",
            "evaluate_technical",
            "evaluate_problem_solving",
            "evaluate_cultural",
            "parse_cv"
        ],
        "verify_bias_gate"
    )

    # Conditional edge after bias gate
    builder.add_conditional_edges(
        "verify_bias_gate",
        route_after_bias_gate,
        {
            "compile_report": "compile_report",
            "abort_pipeline": END
        }
    )

    builder.add_edge("compile_report", END)

    compiled_pipeline = builder.compile()
    logger.info("LangGraph Agentic DAG compilation process completed successfully.")
    return compiled_pipeline