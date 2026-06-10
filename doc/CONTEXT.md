# AI Interview Feedback System

An automated multi-agent evaluation pipeline that ingests candidate test results and interview transcripts, evaluates performance across five dimensions, detects bias, and generates structured hiring feedback for manager review.

## Language

### Candidates and Roles

**Candidate**:
A person applying for a role at the firm who has completed the pre-interview test and attended both interview sessions.
_Avoid_: Applicant, interviewee, hire

**RoleType**:
The enum value that determines which evaluation rubric applies to a candidate. One of: SWE, AI, BA, Trainee.
_Avoid_: Job type, position, track

**Trainee**:
A candidate being assessed on a softer grading curve covering learning agility, problem decomposition, and CS fundamentals — not production-level engineering depth.
_Avoid_: Junior, intern, entry-level

### Interviews and Transcripts

**Session 1**:
The technical panel interview conducted by two domain interviewers (one senior, one junior). Produces a diarized transcript with three speakers. Source for Communication, Technical Depth, and Problem Solving evaluation.
_Avoid_: Technical interview, first interview, panel interview

**Session 2**:
The HR behavioural interview conducted by one HR interviewer. Produces a diarized transcript with two speakers. Source for Cultural Alignment evaluation exclusively.
_Avoid_: HR interview, second interview, behavioural interview

**Diarized transcript**:
A timestamped text record of an interview session where each speech turn is labelled by speaker role (e.g. Candidate, Interviewer_Senior, HR_Interviewer).
_Avoid_: Interview notes, transcript, recording

### Tests

**Pre-interview test**:
A digitally administered domain-specific assessment consisting of MCQ questions and two programming questions, completed before the interview sessions.
_Avoid_: Coding test, assessment, exam

**MCQ score**:
The auto-marked result of the multiple-choice section of the pre-interview test, calculated by exact-match comparison against the answer key and normalized to a 5-point scale.
_Avoid_: Quiz score, test result, multiple choice result

**Programming answers**:
The raw code text submitted by the candidate for the two programming questions in the pre-interview test. Fed directly to the Technical Depth Agent for evaluation.
_Avoid_: Code submission, coding answers, solutions

### Pipeline and Agents

**CandidateBundle**:
The validated Pydantic model that aggregates all five required inputs for a candidate evaluation: MCQ score, programming answers, Session 1 transcript, Session 2 transcript, and role type. No agent executes until this model is fully populated.
_Avoid_: Candidate data, input payload, submission

**InterviewState**:
The LangGraph TypedDict that carries the full pipeline state across all nodes — from the initial CandidateBundle fields through to the final FeedbackReport. Each agent reads from and writes back to this shared state.
_Avoid_: Pipeline state, graph state, context

**Ingestion Agent**:
The first node in the pipeline DAG. Validates that all five inputs are present and assembles the CandidateBundle. Blocks all evaluation agents until validation passes.
_Avoid_: Intake agent, input validator, preprocessor

**Evaluation agents**:
The four agents that run in parallel after ingestion: Communication Analysis, Technical Depth, Problem Solving, and Cultural Alignment. Each returns an EvalScore.
_Avoid_: Scoring agents, analysis agents, worker agents

**Bias gate**:
The mandatory pipeline checkpoint enforced by the Bias Detection Agent. The Feedback Compiler cannot execute without a bias_clear=True flag from this agent.
_Avoid_: Safety check, compliance check, bias filter

### Outputs and Models

**EvalScore**:
The Pydantic model returned by each evaluation agent. Contains: score (integer 1–5), justification (2-sentence rationale), and evidence (direct quote from transcript or code).
_Avoid_: Score, rating, assessment result

**BiasLog**:
The Pydantic model returned by the Bias Detection Agent. Contains: bias_detected (boolean), and a list of BiasCorrection objects documenting any flagged phrases and their neutral replacements.
_Avoid_: Bias report, compliance log, audit record

**FeedbackReport**:
The final compiled Pydantic model containing all five dimension scores, strengths bullets, concerns bullets, AI recommendation, and hiring manager decision field. This is what the hiring manager reviews on the dashboard.
_Avoid_: Evaluation report, candidate report, hiring report

**AI recommendation**:
The system-generated hiring signal produced by the Feedback Compiler. One of: Strong Yes, Yes, Maybe, No. Advisory only — the hiring manager retains full decision authority.
_Avoid_: AI decision, system verdict, recommendation score

**Hiring manager decision**:
The final human-submitted outcome for a candidate: Hired, Rejected, or Hold. Recorded with a timestamp. This is the only legally binding output of the system.
_Avoid_: Final decision, outcome, verdict

### Rubrics

**Rubric**:
A role-specific JSON file that defines the evaluation dimensions and their definitions for a given RoleType. Loaded by the Technical Depth Agent at runtime based on the candidate's role type.
_Avoid_: Scoring guide, criteria, evaluation framework

**Softer curve**:
The Trainee-specific grading approach where candidates are assessed on foundational potential rather than production readiness. Reflected in the Trainee rubric file and flagged in the EvalScore output.
_Avoid_: Easier grading, adjusted scoring, entry-level assessment

### Infrastructure

**DAG**:
The directed acyclic graph of agent nodes defined in graph/pipeline.py using LangGraph. Defines execution order, parallel branches, and conditional edges including the bias gate.
_Avoid_: Pipeline, workflow, graph

**Parallel branch**:
The four evaluation agents (Communication, Technical Depth, Problem Solving, Cultural Alignment) that execute concurrently after the Ingestion Agent completes. Fan-in at the Bias Detection Agent.
_Avoid_: Concurrent agents, parallel agents, simultaneous evaluation

## Flagged ambiguities

- "User stories" in the PRD refers to product-level actor stories (Section 4). "Definition of Done" in Section 5 refers to agent-level acceptance criteria. These are distinct — do not conflate them.
- "Session" without a number is ambiguous — always specify Session 1 (technical) or Session 2 (HR).
- "Score" alone is ambiguous — specify MCQ score, programming score, or EvalScore dimension as appropriate.
- "Report" alone is ambiguous — use FeedbackReport when referring to the compiled Pydantic model, and "dashboard report view" when referring to the Streamlit UI rendering.
