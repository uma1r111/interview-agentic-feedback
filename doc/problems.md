# AI Interview Feedback System — Problems Register

**Status:** Post v1-fix audit | Generated: 2026-06-23  
**Scope:** Full codebase review against current running state  
**Format:** Each issue carries `issue_id`, severity, file, description, consequence, fix, and effort estimate.

---

## CRITICAL — Must fix before any real candidate evaluation

---

```json
{
  "issue_id": "P1-01",
  "title": "Bias gate unconditionally returns True — the compliance gate is fake",
  "file": "agents/bias_detection_agent.py",
  "line": 135,
  "description": "The bias_clear return value is hardcoded to True on line 135: `return bias_output, clean_comm, clean_tech, clean_prob, clean_cult, True, token_meta`. The defensive fallback at line 94 also hardcodes True. This means the pipeline will always route to compile_report regardless of what the LLM finds in the evaluation output. A candidate can receive a demonstrably biased evaluation and the gate clears it unconditionally.",
  "consequence": "The audit trail will record bias_detected: true alongside a completed FeedbackReport. This combination is legally indefensible. The system's core ethical claim — that biased evaluations are blocked before reaching the hiring manager — is false. Any regulator, ethics board, or legal review that inspects the code will find a hardcoded bypass.",
  "fix": "Line 135: change the hardcoded True to `not bias_output.bias_detected`. The defensive fallback at line 94 should remain True (if the LLM call itself fails, assume clean rather than blocking). Only the success path should gate on actual LLM output.",
  "effort": "2 minutes"
}
```

---

```json
{
  "issue_id": "P1-02",
  "title": "programming_answers list contains the same document twice — technical evaluation is corrupted",
  "file": "api/main.py",
  "lines": "448–451",
  "description": "When building the CandidateBundle for pipeline submission, programming_answers is populated as [programming_text, programming_text] — the same extracted document text duplicated. The comment reads 'duplicate so downstream list access is safe'. The Technical Depth Agent receives this list and evaluates [CODE SUBMISSION Q1] and [CODE SUBMISSION Q2] as if they are two separate answers when they are identical.",
  "consequence": "If a candidate answered only one programming question, the Technical Depth Agent evaluates that question twice and scores it as if two separate answers were provided. If the document contains both questions, splitting logic is absent — both slots contain the entire unsplit document. The technical score is generated from fabricated or incorrectly framed input in either case.",
  "fix": "Parse the programming document to split Q1 and Q2 answers by section delimiter or heading. If only one answer exists, pass it as a single-element list and update TechnicalDepthAgent to handle variable-length input. Remove the duplication comment and the second copy.",
  "effort": "1–2 hours depending on document format variability"
}
```

---

```json
{
  "issue_id": "P1-03",
  "title": "PROGRESS_STORE is in-memory — fails silently under multi-worker deployment",
  "file": "api/main.py",
  "line": 71,
  "description": "PROGRESS_STORE: Dict[str, Dict[str, Any]] = {} is a module-level in-memory dictionary. In any production deployment running more than one uvicorn worker, the evaluate POST request and the subsequent progress GET request may hit different workers. Each worker has an isolated memory space. The GET worker has an empty PROGRESS_STORE and returns status: not_started while the pipeline is actively running on another worker.",
  "consequence": "The UI shows perpetual 'not started' or immediately jumps to 'evaluation already complete' (via the DB fallback) with no intermediate status. The progress streaming feature — the primary UX feedback mechanism during a 3–7 minute pipeline run — does not work in any multi-worker deployment. Silent failure with no error surfaced to the user.",
  "fix": "Replace PROGRESS_STORE with a Redis-backed store (redis-py, aioredis) or constrain the server to a single worker (`uvicorn --workers 1`) and document this as an explicit architectural constraint until Redis is added. Do not leave multi-worker deployment as an implicit footgun.",
  "effort": "Redis: 2–3 hours setup + integration. Single-worker constraint: 15 minutes + documentation."
}
```

---

## HIGH — Must fix before first external demo or stakeholder review

---

```json
{
  "issue_id": "P1-04",
  "title": "Pipeline has no execution timeout — hung pipelines accumulate silently",
  "file": "api/main.py",
  "function": "run_evaluation_background",
  "description": "The background evaluation function calls interview_graph.stream(...) with no timeout. Each pipeline run makes approximately 8 LLM calls. If Azure OpenAI rate-limits mid-pipeline, max_retries=3 in BaseAgent triggers exponential backoff — potentially blocking the background thread for 5–15 minutes. There is no asyncio.wait_for, no concurrent.futures timeout, no circuit breaker, and no maximum wall-clock time enforced anywhere.",
  "consequence": "A hung pipeline sets PROGRESS_STORE[candidate_id]['status'] = 'running' indefinitely. The candidate record is never saved. The intake status never transitions to 'evaluated'. The hiring manager sees a perpetual spinner. The background thread is leaked. Under load, multiple hung pipelines accumulate threads until the server runs out of thread pool capacity.",
  "fix": "Wrap the graph.stream loop in concurrent.futures.ThreadPoolExecutor with a timeout parameter, or use a threading.Timer to set a maximum execution window (suggested: 600 seconds / 10 minutes). On timeout, set PROGRESS_STORE status to 'timeout' and surface a recoverable error message to the UI.",
  "effort": "1–2 hours"
}
```

---

```json
{
  "issue_id": "P1-05",
  "title": "mcq_responses field is passed through entire pipeline state unnecessarily",
  "file": "models/candidate.py",
  "description": "Raw MCQ answer selections remain in InterviewState and are visible to all downstream agents after ingestion. This is candidate PII that should be consumed and dropped by the ingestion node, not carried through the full pipeline.",
  "consequence": "Data hygiene violation. Evaluation agents have access to raw MCQ answers they should not see. In a regulated context this is a data minimisation failure.",
  "fix": "Clear mcq_responses from state after ingestion node completes. Set it to None or remove from return dict in ingestion_node.",
  "effort": "15 minutes"
}
```

---

```json
{
  "issue_id": "P1-06",
  "title": "raw_cv field persists in InterviewState through all evaluation agents — PII not isolated",
  "file": "models/candidate.py",
  "description": "InterviewState carries raw_cv (containing candidate name, employer names, institution names, and full career history) through every pipeline node from ingestion to feedback compilation. The CV Parsing Agent produces an anonymised CandidateSkillsSummary specifically to prevent PII from reaching evaluation agents — but raw_cv is never cleared from state after the CV parsing node completes. Any node that reads from state can access raw_cv.",
  "consequence": "The anonymisation architecture promise is not enforced by the data model. A future agent added to the pipeline that reads raw_cv would break the anonymisation guarantee silently. In a regulated GDPR or EEOC context, this represents a data minimisation failure — personal data is retained in active processing state longer than required.",
  "fix": "After cv_parsing_node completes, clear raw_cv from state or replace it with a truncated placeholder. Add a note in InterviewState documenting that raw_cv is ingestion-only and should not be read by any node after parse_cv.",
  "effort": "30 minutes"
}
```

---

```json
{
  "issue_id": "P1-07",
  "title": "Three SQLite database files exist in project root — only one is authoritative",
  "file": "project root",
  "description": "The project root contains database.db, interview.db, and interview_db.sqlite. The Settings model specifies database_path = 'database.db' as the default. The other two files are remnants of earlier development sessions. There is no migration tool, no schema version table, and no documentation explaining which file is the production database.",
  "consequence": "Any developer cloning the repo and running the server will use database.db. But if database.db is empty and interview.db contains actual candidate records from a previous session, those records are invisible to the running server. A support incident (missing candidate) caused by this confusion is a matter of time.",
  "fix": "Delete interview.db and interview_db.sqlite. Add a .gitignore entry for *.db to prevent future accumulation. Add a comment in settings.py naming database.db as the single authoritative database file.",
  "effort": "10 minutes"
}
```

---

## MEDIUM — Fix before production use

---

```json
{
  "issue_id": "P2-01",
  "title": "Transcript preprocessor strips timestamps but does not isolate candidate speech turns",
  "file": "services/transcript_preprocessor.py",
  "description": "The preprocess_transcript_node runs before all evaluation agents and produces clean_session1 and clean_session2. However, 'clean' means timestamps are stripped — the diarized transcript still contains both interviewer and candidate speech turns interleaved. Evaluation agents (Communication, Problem Solving, Cultural) receive this mixed output and must implicitly filter candidate turns during the same LLM call as the evaluation.",
  "consequence": "Each evaluation call performs two tasks simultaneously: speaker isolation and dimensional scoring. This increases prompt complexity, token consumption (interviewer turns account for 30–50% of transcript length), and reduces the precision of evidence extraction. The evidence field in EvalScore quotes are harder to trace back to the candidate unambiguously.",
  "fix": "Extend TranscriptPreprocessor to produce a candidate_only_session1 and candidate_only_session2 field in state — speaker turns belonging to the candidate extracted and concatenated. Pass these to evaluation agents instead of the full cleaned transcript. Use InterviewState to carry both versions.",
  "effort": "2–3 hours"
}
```

---

```json
{
  "issue_id": "P2-02",
  "title": "Communication, Problem Solving, and Cultural agents lack dimension-level output — asymmetric granularity",
  "file": "agents/communication_agent.py, agents/problem_solving_agent.py, agents/cultural_alignment_agent.py",
  "description": "The Technical Depth Agent correctly produces a TechnicalDimensionReport with per-rubric-dimension scoring, justification, and evidence. The other three evaluation agents return a flat EvalScore — one integer score, one 2-sentence justification, one evidence field. There is no rubric-level breakdown for Communication, Problem Solving, or Cultural Alignment.",
  "consequence": "A hiring manager cannot determine which specific communication dimension failed (e.g., active listening vs. question framing vs. structured articulation). The FeedbackReport presents a single Communication score of 3/5 with no granularity about where the deficit lies. The system cannot generate targeted developmental feedback. The evaluation granularity is asymmetric and inconsistent across agent types.",
  "fix": "Define dimension rubrics for Communication, Problem Solving, and Cultural Alignment (similar to the technical rubric JSON files). Update each agent to return a DimensionReport model. Update FeedbackReport to carry these dimension breakdowns. This is a significant but high-value change.",
  "effort": "1–2 days"
}
```

---

```json
{
  "issue_id": "P2-03",
  "title": "LLM evaluation output has no calibration mechanism — scores cannot be trusted without ground truth",
  "file": "agents/ (all evaluation agents)",
  "description": "The system generates candidate scores using LLM calls with temperature=0.0. While temperature 0 reduces non-determinism, it does not prevent consistently wrong evaluations. There is no mechanism to compare LLM-generated scores against human-panel scores on the same transcript, no anomaly detection for implausible score patterns (e.g., 5/5 communication + 1/5 technical), and no re-evaluation or consistency check across two separate LLM calls on the same input.",
  "consequence": "The system generates reproducible noise with no way to detect it. A hiring manager who sees a 4/5 technical score has no way to know whether the LLM hallucinated a high score because the candidate used confident-sounding language. Over time, uncalibrated scores produce systematic hiring biases that are invisible in the output.",
  "fix": "Add a calibration dataset of 3–5 manually scored transcripts per role type. Run a weekly calibration check: evaluate the fixture transcripts and compare LLM scores to ground truth. Alert if any dimension drifts more than 1 point. This does not require new agents — it requires a calibration script and a monitoring mechanism.",
  "effort": "1 day for calibration fixtures + script; ongoing monitoring cadence"
}
```

---

```json
{
  "issue_id": "P2-04",
  "title": "Dashboard has no role-based access control — any authenticated user can see all candidates",
  "file": "dashboard/app.py (or app_merged.py)",
  "description": "The Streamlit dashboard authenticates users but does not implement role-based access control. Any user with valid credentials can view all candidate records, all FeedbackReports, and all audit trails. There is no separation between HR viewers (can see reports), hiring managers (can submit decisions), and admins (can delete records).",
  "consequence": "In a regulated hiring context, access to candidate PII and evaluation reports should be restricted by role. A junior HR coordinator should not have access to the same data as the hiring manager. Without RBAC, every dashboard user is effectively an administrator. This fails basic access control requirements for any HR system handling personal data.",
  "fix": "Extend the authentication layer to assign roles (viewer, manager, admin). Gate the decision-patching UI behind manager role. Gate delete operations behind admin role. Read-only report views can be viewer-accessible. This requires a users table with a role column in the database.",
  "effort": "4–6 hours"
}
```

---

```json
{
  "issue_id": "P2-05",
  "title": "candidate_name appears in FeedbackReport — CV anonymisation is undermined at compilation",
  "file": "agents/feedback_compiler_agent.py, models/evaluation.py",
  "description": "The CV Parsing Agent anonymises the raw CV into CandidateSkillsSummary with no names, employers, or institutions. But FeedbackReport.candidate_name is a required field and is populated by FeedbackCompilerAgent using the candidate_name from pipeline state. The final report — which evaluation agents contribute to and which goes to the hiring manager — is attributed to a named individual.",
  "consequence": "Evaluation agents that produce EvalScore objects do not see the candidate name directly. But the FeedbackReport that aggregates their output does. If the goal is to prevent name-based bias from influencing the evaluation (a stated purpose of the anonymisation step), attribution in the final compiled report is at minimum inconsistent with that goal.",
  "fix": "Decide architecturally: either evaluations are anonymous (report contains only candidate_id until a human manager attaches the name) or they are named (remove the anonymisation framing from documentation). Currently the codebase claims anonymisation but delivers named reports. Pick one and be consistent.",
  "effort": "Design decision: 30 minutes. Implementation of chosen approach: 1–2 hours."
}
```

---

## LOW — Quality and maintainability improvements

---

```json
{
  "issue_id": "P3-01",
  "title": "update_candidate_intake_files function references columns that do not exist in schema",
  "file": "services/database.py",
  "lines": "148–186",
  "description": "The function update_candidate_intake_files references columns mcq_score, mcq_selections, programming_answer_1, and programming_answer_2 in its UPDATE statement. The actual candidate_intake table schema contains mcq_path and programming_path. These four column names do not exist in the current schema. This function will throw a sqlite3.OperationalError if called.",
  "consequence": "The function is dead code — it is never called by the current API (which uses patch_intake_candidate instead). But it will cause confusion for any developer who discovers it and tries to use it, and it represents schema drift that will get worse as the codebase evolves.",
  "fix": "Either delete the function (it is unreachable) or update it to match the current schema with mcq_path and programming_path columns.",
  "effort": "10 minutes"
}
```

---

```json
{
  "issue_id": "P3-02",
  "title": "mcq_responses field in InterviewState creates false impression of an intake contract",
  "file": "models/candidate.py",
  "line": 38,
  "description": "InterviewState declares mcq_responses: Optional[Dict[str, str]] as a field. It is initialized as {} in api/main.py, passed to IngestionAgent.process_intake (which never uses it), and explicitly nulled in ingestion_node return dict. The field serves no purpose and is never read by any agent.",
  "consequence": "Any developer reading InterviewState for the first time will spend time understanding what mcq_responses contains, why it is passed to process_intake, and where it goes after ingestion. It creates false complexity in the state schema.",
  "fix": "Remove mcq_responses from InterviewState entirely. Remove the mcq_responses argument from IngestionAgent.process_intake. Remove the {} initialization in api/main.py initial_inputs dict.",
  "effort": "15 minutes"
}
```

---

```json
{
  "issue_id": "P3-03",
  "title": "Token pricing in AITokenCostTrackingMiddleware is hardcoded to GPT-4o rates",
  "file": "api/middleware.py",
  "lines": "157–158",
  "description": "The cost calculation uses hardcoded values: $5.00 per 1M input tokens and $15.00 per 1M output tokens. These are the Azure OpenAI GPT-4o pricing tiers as of mid-2025. Pricing changes frequently and varies by deployment type, region, and contract.",
  "consequence": "The X-AI-Cost response header will show incorrect cost estimates if the model, region, or pricing tier changes. This is also a maintenance burden — pricing logic buried in middleware is easy to forget to update.",
  "fix": "Move pricing constants to settings.py as llm_cost_per_1m_input_tokens and llm_cost_per_1m_output_tokens. Load them in the middleware from settings. This makes pricing adjustable via environment variables without a code change.",
  "effort": "20 minutes"
}
```

---

```json
{
  "issue_id": "P3-04",
  "title": "CORS allow_origins is hardcoded to localhost:3000 only",
  "file": "api/main.py",
  "line": 57,
  "description": "The CORSMiddleware is configured with allow_origins=['http://localhost:3000']. The frontend (Streamlit dashboard) does not run on port 3000 — it runs on port 8501 by default. The frontend is also same-origin from a browser perspective when served by Streamlit. This CORS config appears to be a leftover from a previous React frontend assumption.",
  "consequence": "If any client other than the same-host server attempts to call the API (e.g., a future Next.js frontend on port 3000, or an external service), CORS will behave in an unexpected and potentially blocking way. The current Streamlit dashboard calls the API server-side, so CORS does not apply. But the setting is misleading about who the intended browser client is.",
  "fix": "Update allow_origins to reflect the actual intended browser clients. If the only client is the Streamlit dashboard (server-side HTTP calls, no browser CORS concerns), set allow_origins=['*'] or remove the CORSMiddleware entirely. If a browser-based frontend is planned, set the correct origin.",
  "effort": "5 minutes"
}
```

---

```json
{
  "issue_id": "P3-05",
  "title": "on_startup uses deprecated @app.on_event decorator",
  "file": "api/main.py",
  "line": 73,
  "description": "FastAPI deprecated the @app.on_event('startup') decorator in favour of lifespan context managers in FastAPI 0.93+. The current code uses the deprecated pattern.",
  "consequence": "No immediate runtime impact, but deprecation warnings will appear in logs and the pattern will eventually be removed in a future FastAPI version. This creates technical debt that becomes a breaking change later.",
  "fix": "Replace @app.on_event('startup') with a lifespan context manager: `from contextlib import asynccontextmanager; @asynccontextmanager async def lifespan(app): init_database(); yield; app = FastAPI(lifespan=lifespan, ...)`.",
  "effort": "15 minutes"
}
```

---

*Register last updated: 2026-06-23*  
*Total issues: 14 (2 Critical · 5 High · 5 Medium · 4 Low)*  
*Next review: after P1-01 and P1-02 are resolved*
