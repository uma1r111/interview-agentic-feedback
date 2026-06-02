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

logger = logging.getLogger("InterviewPipeline")

# ==============================================================================
# Graph Node Execution Wrappers
# ==============================================================================

def ingestion_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Validates payload bundles and instantiates global pipeline state."""
    logger.info("--- START NODE: INGESTION ---")
    # Extract raw data payload and mcq dictionary passed inside initial graph invocation
    raw_payload = state.get("raw_payload", {})
    mcq_responses = state.get("mcq_responses", {})
    
    agent = IngestionAgent()
    updated_state, success = agent.process_intake(raw_payload, mcq_responses)
    
    if not success:
        return {"error": updated_state.get("error")}
    return updated_state

def communication_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates text-based dialogue dynamics inside Session 1."""
    logger.info("--- START NODE: COMMUNICATION EVALUATOR ---")
    agent = CommunicationAgent()
    score, _ = agent.evaluate_communication(state["session1_transcript"])
    return {"communication_score": score}

def technical_depth_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates code optimization alongside systems architecture notes."""
    logger.info("--- START NODE: TECHNICAL DEPTH EVALUATOR ---")
    agent = TechnicalDepthAgent()
    score, _ = agent.evaluate_technical_depth(
        role_type=state["role_type"],
        session1_transcript=state["session1_transcript"],
        programming_answers=state["programming_answers"]
    )
    return {"technical_score": score}

def problem_solving_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates conceptual mapping and structural breakdown behaviors."""
    logger.info("--- START NODE: PROBLEM SOLVING EVALUATOR ---")
    agent = ProblemSolvingAgent()
    score, _ = agent.evaluate_problem_solving(state["session1_transcript"])
    return {"problem_solving_score": score}

def cultural_alignment_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates team motivation and values markers strictly from Session 2."""
    logger.info("--- START NODE: CULTURAL ALIGNMENT EVALUATOR ---")
    agent = CulturalAlignmentAgent()
    score, _ = agent.evaluate_cultural_alignment(state["session2_transcript"])
    return {"cultural_score": score}

def bias_detection_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Sweeps narrative observations for subjective or loaded expressions."""
    logger.info("--- START NODE: BIAS DETECTION GUARDRAIL GATE ---")
    agent = BiasDetectionAgent()
    log, sanitized_scores, clear_flag, _ = agent.analyze_and_sanitize_scores(
        communication=state["communication_score"],
        technical=state["technical_score"],
        problem_solving=state["problem_solving_score"],
        cultural=state["cultural_score"]
    )
    return {
        "bias_log": log,
        "communication_score": sanitized_scores[0],
        "technical_score": sanitized_scores[1],
        "problem_solving_score": sanitized_scores[2],
        "cultural_score": sanitized_scores[3],
        "bias_clear": clear_flag
    }

def feedback_compiler_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Synthesizes all individual dimension evaluations into an executive summary."""
    logger.info("--- START NODE: FEEDBACK COMPILER ---")
    agent = FeedbackCompilerAgent()
    report, _ = agent.compile_final_report(
        candidate_name=state["candidate_name"],
        role_type=state["role_type"],
        mcq_score=state["mcq_score"],
        programming_answers=state["programming_answers"],
        communication=state["communication_score"],
        technical=state["technical_score"],
        problem_solving=state["problem_solving_score"],
        cultural=state["cultural_score"],
        bias_clear=state["bias_clear"]
    )
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

# ==============================================================================
# Pipeline Topology Assembler Builder
# ==============================================================================

def create_interview_graph():
    """Builds, connects, and compiles the stateful LangGraph pipeline execution engine."""
    # 1. Instantiate state workflow template schema mapping
    builder = StateGraph(InterviewState)
    
    # 2. Register functional execution processing vertices
    builder.add_node("ingest", ingestion_node)
    builder.add_node("evaluate_communication", communication_node)
    builder.add_node("evaluate_technical", technical_depth_node)
    builder.add_node("evaluate_problem_solving", problem_solving_node)
    builder.add_node("evaluate_cultural", cultural_alignment_node)
    builder.add_node("verify_bias_gate", bias_detection_node)
    builder.add_node("compile_report", feedback_compiler_node)
    
    # 3. Establish flow boundaries and map conditional branches
    builder.add_edge(START, "ingest")
    
    # Parallel Branch Fan-Out: Trigger downstream analytics concurrently
    builder.add_edge("ingest", "evaluate_communication")
    builder.add_edge("ingest", "evaluate_technical")
    builder.add_edge("ingest", "evaluate_problem_solving")
    builder.add_edge("ingest", "evaluate_cultural")
    
    # Parallel Branch Fan-In: Synchronize all parallel analytical operations into the validation gate
    builder.add_edge("evaluate_communication", "verify_bias_gate")
    builder.add_edge("evaluate_technical", "verify_bias_gate")
    builder.add_edge("evaluate_problem_solving", "verify_bias_gate")
    builder.add_edge("evaluate_cultural", "verify_bias_gate")
    
    # 4. Integrate strict conditional gating constraints
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