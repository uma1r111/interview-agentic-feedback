import logging
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END

# Import unified state definition and specialized agents
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
    
    # Extract raw parameters passed during API graph execution
    raw_payload = state.get("raw_payload", {})
    mcq_responses = state.get("mcq_responses", {})
    
    # If initial_inputs passed them flat, fallback to compiling them from the root state
    if not raw_payload:
        raw_payload = {
            "candidate_name": state.get("candidate_name"),
            "role_type": state.get("role_type"),
            "raw_cv": state.get("raw_cv"),
            "mcq_score": state.get("mcq_score"),
            "programming_answers": state.get("programming_answers"),
            "session1_transcript": state.get("session1_transcript"),
            "session2_transcript": state.get("session2_transcript")
        }

    # Defensive patch: if raw_payload arrived from model_dump() but raw_cv
    # wasn't included (e.g. server cached an old schema), pull it from flat state.
    if "raw_cv" not in raw_payload and state.get("raw_cv"):
        raw_payload["raw_cv"] = state.get("raw_cv")

    agent = IngestionAgent()
    updated_state, success = agent.process_intake(raw_payload, mcq_responses)
    
    if not success:
        logger.error(f"Ingestion processing failure: {updated_state.get('error')}")
        return {"error": updated_state.get("error")}
        
    # FIX: Return a clean state update dictionary back to LangGraph.
    # This guarantees all tracking keys are flattened out and safely committed
    # directly into LangGraph's global root-level state dictionary space.
    return {
        "candidate_id": updated_state.get("candidate_id"),
        "candidate_name": updated_state.get("candidate_name"),
        "role_type": updated_state.get("role_type"),
        "raw_cv": updated_state.get("raw_cv"),
        "mcq_score": updated_state.get("mcq_score"),
        "programming_answers": updated_state.get("programming_answers"),
        "session1_transcript": updated_state.get("session1_transcript"),
        "session2_transcript": updated_state.get("session2_transcript"),
        "error": None
    }

def communication_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates text-based dialogue dynamics inside Session 1."""
    logger.info("--- START NODE: COMMUNICATION EVALUATOR ---")
    agent = CommunicationAgent()
    transcript = state.get("session1_transcript", "")
    score, _ = agent.evaluate_communication(transcript)
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
    transcript = state.get("session2_transcript", "")
    score, _ = agent.evaluate_cultural_alignment(transcript)
    return {"cultural_score": score}

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
        "bias_log": log,
        "communication_score": clean_comm,
        "technical_score": clean_tech,
        "problem_solving_score": clean_prob,
        "cultural_score": clean_cult,
        "bias_clear": clear_flag
    }

def cv_parsing_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs the two-pass CV Parsing Agent.

    WHAT THIS NODE DOES IN THE GRAPH
    ----------------------------------
    This node runs IN PARALLEL with the 4 evaluation nodes (fan-out from ingest).
    It reads raw_cv from state, calls CVParsingAgent.parse(), and writes two
    new keys into the state:
      - candidate_skills_summary  →  the anonymised CV (CandidateSkillsSummary)
      - cv_experience_match       →  the rubric comparison (ExperienceMatchSummary)

    WHY IT DOESN'T WRITE TO bias_log OR bias_clear
    ------------------------------------------------
    The CV Parsing Agent does NOT run through the bias gate. Its output
    (CandidateSkillsSummary) is already PII-free by design. The Bias Detection
    Agent only scans evaluation agent text (justifications and evidence quotes).
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
        "candidate_skills_summary": skills_summary,  # CandidateSkillsSummary
        "cv_experience_match": experience_match       # ExperienceMatchSummary
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

    # Attach cv_experience_match directly to the report object for database persistence and UI.
    if cv_match and report:
        report.cv_experience_match = cv_match
        logger.info("CV experience match attached to FeedbackReport.")

    return {"feedback_report": report}


# ==============================================================================
# LangGraph Conditional Edge Routing Criteria
# ==============================================================================

def route_after_bias_gate(state: Dict[str, Any]) -> Literal["compile_report", "abort_pipeline"]:
    """Inspects compliance lock flags to authorize or block final compilation."""
    if state.get("error") or not state.get("bias_clear"):
        logger.error("Conditional Edge: Verification conditions breached or ingestion crashed. Aborting processing loops.")
        return "abort_pipeline"
    
    logger.info("Conditional Edge: Security parameters verified. Authorizing feedback report assembly.")
    return "compile_report"

def route_after_ingestion(state: Dict[str, Any]) -> Literal["abort_pipeline", "continue"]:
    if state.get("error"):
        logger.error("Ingestion validation failure. Blocking downstream agents.")
        return "abort_pipeline"
    
    # LangGraph conditional router functions can return an array of keys 
    # indicating multiple downstream vertices should be triggered concurrently!
    return [
        "evaluate_communication",
        "evaluate_technical",
        "evaluate_problem_solving",
        "evaluate_cultural",
        "parse_cv"       # ← CV Parsing Agent runs in parallel with the 4 evaluators
    ]

# ==============================================================================
# Pipeline Topology Assembler Builder
# ==============================================================================

def create_interview_graph():
    """Builds, connects, and compiles the stateful LangGraph pipeline execution engine."""
    # 1. Instantiate state workflow template schema mapping
    builder = StateGraph(InterviewState)
    
    # 2. Register functional execution processing vertices
    builder.add_node("ingest",                    ingestion_node)
    builder.add_node("evaluate_communication",    communication_node)
    builder.add_node("evaluate_technical",        technical_depth_node)
    builder.add_node("evaluate_problem_solving",  problem_solving_node)
    builder.add_node("evaluate_cultural",         cultural_alignment_node)
    builder.add_node("parse_cv",                  cv_parsing_node)   # ← new node
    builder.add_node("verify_bias_gate",          bias_detection_node)
    builder.add_node("compile_report",            feedback_compiler_node)
    # 3. Establish flow boundaries
    builder.add_edge(START, "ingest")
    
    # FIX: Clean, hashable 1:1 key-value map layout.
    # The dictionary keys tell LangGraph what the function *might* return, 
    # matching the exact identity string of the destination nodes perfectly.
    # Error-only conditional — abort if ingestion failed, otherwise fan out
    builder.add_conditional_edges(
        "ingest",
        route_after_ingestion,
        {
            "evaluate_communication":   "evaluate_communication",
            "evaluate_technical":       "evaluate_technical",
            "evaluate_problem_solving": "evaluate_problem_solving",
            "evaluate_cultural":        "evaluate_cultural",
            "parse_cv":                 "parse_cv",   # ← added to allow-list
            "abort_pipeline":           END
        }
    )
    
    # Parallel Branch Fan-In:
    # All 5 parallel nodes (4 evaluators + CV parser) must complete before
    # verify_bias_gate fires. LangGraph counts incoming edges automatically —
    # adding this 5th edge extends the synchronization barrier from 4 to 5.
    builder.add_edge("evaluate_communication",   "verify_bias_gate")
    builder.add_edge("evaluate_technical",       "verify_bias_gate")
    builder.add_edge("evaluate_problem_solving", "verify_bias_gate")
    builder.add_edge("evaluate_cultural",        "verify_bias_gate")
    builder.add_edge("parse_cv",                 "verify_bias_gate")  # ← new fan-in edge
    # 4. Integrate strict conditional gating constraints after the bias check
    builder.add_conditional_edges(
        "verify_bias_gate",
        route_after_bias_gate,
        {
            "compile_report": "compile_report",
            "abort_pipeline": END
        }
    )
    
    builder.add_edge("compile_report", END)
    
    # 5. Compile the active state graph asset
    compiled_pipeline = builder.compile()
    logger.info("LangGraph Agentic DAG compilation process completed successfully.")
    return compiled_pipeline