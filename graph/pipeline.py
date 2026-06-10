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
        "error": None
    }


def communication_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates text-based dialogue dynamics inside Session 1."""
    logger.info("--- START NODE: COMMUNICATION EVALUATOR ---")
    agent = CommunicationAgent()
    score, _ = agent.evaluate_communication(state.get("session1_transcript", ""))
    return {"communication_score": score}


def technical_depth_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates code optimization alongside systems architecture notes."""
    logger.info("--- START NODE: TECHNICAL DEPTH EVALUATOR ---")
    agent = TechnicalDepthAgent()
    score, _ = agent.evaluate_technical_depth(
        role_type=state.get("role_type"),
        session1_transcript=state.get("session1_transcript", ""),
        programming_answers=state.get("programming_answers", ["", ""])
    )
    return {"technical_score": score}


def problem_solving_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates conceptual mapping and structural breakdown behaviors."""
    logger.info("--- START NODE: PROBLEM SOLVING EVALUATOR ---")
    agent = ProblemSolvingAgent()
    score, _ = agent.evaluate_problem_solving(state.get("session1_transcript", ""))
    return {"problem_solving_score": score}


def cultural_alignment_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates team motivation and values markers strictly from Session 2."""
    logger.info("--- START NODE: CULTURAL ALIGNMENT EVALUATOR ---")
    agent = CulturalAlignmentAgent()
    score, _ = agent.evaluate_cultural_alignment(state.get("session2_transcript", ""))
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
        cv_experience_match=cv_match
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
    builder.add_node("evaluate_communication",   communication_node)
    builder.add_node("evaluate_technical",       technical_depth_node)
    builder.add_node("evaluate_problem_solving", problem_solving_node)
    builder.add_node("evaluate_cultural",        cultural_alignment_node)
    builder.add_node("parse_cv",                 cv_parsing_node)
    builder.add_node("verify_bias_gate",         bias_detection_node)
    builder.add_node("compile_report",           feedback_compiler_node)

    # Entry point
    builder.add_edge(START, "ingest")

    # Conditional edge: abort on ingestion error, otherwise route to communication
    # (communication is the trigger node — remaining parallel nodes use direct edges below)
    builder.add_conditional_edges(
        "ingest",
        route_after_ingestion,
        {
            "abort_pipeline": END,
            "continue":       "evaluate_communication"
        }
    )

    # Parallel fan-out via direct edges — LangGraph executes all concurrently
    builder.add_edge("ingest", "evaluate_technical")
    builder.add_edge("ingest", "evaluate_problem_solving")
    builder.add_edge("ingest", "evaluate_cultural")
    builder.add_edge("ingest", "parse_cv")

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