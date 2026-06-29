# LLM Council Review — AI Interview Feedback System
## Session Type: Codebase Audit — Post-Fix State Review (v2)
## Project: AI Interview Feedback System
## Date: 2026-06-23

---

## STAGE 1 — THE FIVE ADVISORS

---

### ADVISOR 1 — THE CONTRARIAN
*Find what will fail. Where does this break? What is the user not seeing? Be blunt.*

This system is one unhandled exception away from a silent hire or a silent reject. Let me show you where it actually breaks.

**The bias gate always clears — it is not a gate.**
`bias_detection_agent.py` line 135: `return bias_output, clean_comm, clean_tech, clean_prob, clean_cult, True, token_meta`. The fifth positional return value — `bias_clear` — is **hardcoded to `True`**. Always. Even in the success path. The defensive fallback at line 94 also returns `True`. This means the "mandatory compliance gate" that is marketed as the system's ethical backbone will clear regardless of what `bias_detected` returns. The pipeline will always proceed to compile a report. A candidate could receive a deeply biased evaluation and the gate would wave it through.

**PROGRESS_STORE is an in-memory dict on a multi-worker server — it will fail silently.**
`api/main.py` line 71: `PROGRESS_STORE: Dict[str, Dict[str, Any]] = {}`. When FastAPI runs under any production ASGI server with multiple workers (uvicorn `--workers 4`), each worker has its own memory space. A request to `/intake/{id}/evaluate` may hit worker 1. The polling request to `/intake/{id}/progress` may hit worker 2. Worker 2 has an empty `PROGRESS_STORE`. It returns `not_started`. The UI will show perpetual "not started" while the pipeline is actually running on another worker. This is not a hypothetical — it is guaranteed in any multi-worker deployment.

**The `mcq_responses` field is passed into the pipeline as an empty dict `{}` and serves no purpose.**
`api/main.py` line 473: `"mcq_responses": {}`. `ingestion_node` reads it, passes it to `IngestionAgent.process_intake` as `mcq_responses`, which never uses it. The field exists in `InterviewState` as `Optional[Dict[str, str]]` and is explicitly set to `None` on line 63 of `pipeline.py`. This entire field is dead weight — defined, passed, consumed nowhere, nulled. It adds confusion about what the intake contract actually is.

**The pipeline has no timeout. At all.**
A single LangGraph pipeline run makes approximately 8 LLM calls (MCQ checker, programming checker, communication, technical depth, problem solving, cultural alignment, bias detection, feedback compiler). If Azure OpenAI rate-limits mid-pipeline, the `max_retries=3` in `base_agent.py` will block the background thread for minutes with exponential backoff — silently. There is no `asyncio.wait_for`, no `httpx` timeout override, no circuit breaker. The background thread will hang indefinitely. The `PROGRESS_STORE` will show `running` forever. The candidate record will never be saved. The hiring manager will see a perpetual spinner.

**`programming_answers` is duplicated intentionally — and this is a design smell.**
`api/main.py` lines 448–451:
```python
programming_answers=[
    programming_text,
    programming_text,   # duplicate so downstream list access is safe
],
```
The comment says "duplicate so downstream list access is safe." This means the Technical Depth Agent receives the same document twice as if it were two separate programming submissions. The technical depth evaluation is running against duplicated input. If the candidate only answered Question 1, Question 2's evaluation is fabricated from Q1's text. The score is invalid.

**The raw CV lives in state all the way to the Feedback Compiler.**
`InterviewState` carries `raw_cv` from ingestion through every node to the end of the pipeline. The CV Parsing Agent anonymises it into `CandidateSkillsSummary` specifically to prevent PII leakage to evaluation agents. But `raw_cv` — with the candidate's name, employer names, and institutions — is still available as a key in `InterviewState` throughout. Any agent that reads from `state` has access to it. The anonymisation is a promise that the architecture does not enforce.

---

### ADVISOR 2 — THE FIRST PRINCIPLES THINKER
*Strip away every assumption. Rebuild from scratch. What is actually being asked?*

The question underneath all of this is: **can a machine evaluate a human interview more consistently and more fairly than a human hiring panel?**

That question has two sub-problems. First: can the machine extract a faithful signal from the interview? Second: can it apply that signal consistently against a defined standard?

Strip away the agents, the DAG, the API, the dashboard. The actual value chain is:

```
Raw interview transcript → Signal extraction → Rubric comparison → Structured verdict
```

Everything else is scaffolding.

**Now here is the first principles problem: the system conflates signal extraction with evaluation in every single agent.**

Look at `communication_agent.py`, `problem_solving_agent.py`, `cultural_alignment_agent.py`. Each agent receives a raw cleaned transcript and in a single LLM call must simultaneously: parse the diarized text, identify relevant candidate speech turns, extract behavioural signals, and score them against a rubric. That is four cognitive tasks in one call.

The transcript preprocessor exists (`services/transcript_preprocessor.py`) and runs in the pipeline, but it produces `clean_session1` and `clean_session2`. Examine what "clean" actually means — it is the entire transcript with timestamps stripped, not candidate-only turns. The fundamental information separation — interviewer questions vs. candidate answers — is never made. Every evaluation agent still receives interviewer speech mixed with candidate speech, making evidence extraction harder and less precise.

**What is actually being asked in the Technical Depth evaluation?**
Not "how well does this candidate communicate." That is a separate agent. The Technical Depth Agent is asking: "given these rubric dimensions, what did the candidate demonstrate?" But the agent receives the full session1 transcript — containing both interviewer questions and candidate responses, plus code submissions. The LLM must infer which turns are the candidate's and which are the interviewers', then evaluate the candidate's turns only.

**The first principles fix is a speaker isolation step, not a "preprocessing" step.**
The current preprocessor strips timestamps. It should strip interviewer turns entirely and produce a `candidate_responses_only` field in state. This would:
1. Reduce token consumption by approximately 40–50% per evaluation call (interviewer turns are substantial)
2. Force evidence extraction to be sourced from candidate speech only
3. Make the technical evaluation more precise and less susceptible to interviewer framing effects

**The second first principles problem: rubric adherence is enforced by prompt engineering, not by schema.**
The system knows which dimensions exist (from the rubric JSON). The Technical Depth Agent correctly produces a `TechnicalDimensionReport` with per-dimension scores. But the Communication, Problem Solving, and Cultural agents return a flat `EvalScore` — one score, one justification, one evidence field. These agents have no rubric-level dimension breakdown. The question "what specific communication dimension did the candidate fail?" cannot be answered from the current output schema. The granularity is asymmetric: Technical gets full dimension breakdown, the other three do not.

---

### ADVISOR 3 — THE EXPANSIONIST
*Find the upside the user is missing. What is the bigger version of this?*

This system, as built, is a **hiring decision support tool**. That is the smallest possible frame.

Look at what is actually present in this codebase: a multi-agent rubric-driven evaluation engine with structured output, bias detection, audit trails, role-aware scoring, and a pipeline that can process any diarized interview transcript against any JSON rubric. That is not a hiring tool. That is a **competency assessment infrastructure platform**.

**Opportunity 1: The rubric system is a product in itself.**
Four role rubrics currently exist: SWE, AI, BA, Trainee. Each is a structured JSON file with dimension names, descriptions, and scoring anchors. Any organisation that wants to run structured competency interviews needs exactly this — a machine-readable, versioned rubric that can be loaded, extended, and applied consistently. The `extends` directive in the rubric system is already there. This is the beginning of a rubric marketplace: publish community rubrics for Data Scientists, DevOps Engineers, Product Managers, and let organisations import and customise them. The code to do this exists today.

**Opportunity 2: The bias detection pipeline is the compliance product.**
The `TranscriptScreener` already scans for 15+ protected characteristic categories. The `BiasDetectionAgent` rewrites biased language in evaluation output. The `BiasLog` records every correction with agent ID, original phrase, corrected phrase, and rationale. These three components together constitute a compliance audit trail that regulators would pay for independently. An "Interviewer Bias Report" product — aggregate `BiasLog` entries across all interviews, rank interviewers by flag rate, surface which question categories generate the most flags — requires zero new agents. It requires one aggregation query and one new dashboard view.

**Opportunity 3: The evaluation pipeline is a coaching engine.**
Every `EvalScore` contains `evidence` — verbatim quotes from the transcript. Every `TechnicalDimensionReport` contains per-dimension justifications and quotes. This is not just a hiring signal. This is structured feedback that a candidate could receive to understand exactly where they fell short and what evidence the evaluator used. A "candidate feedback letter" product — a structured, evidence-backed developmental report — is one prompt change away from the current `FeedbackCompilerAgent`. The schema already supports it. The data is already there.

**Opportunity 4: Cohort analytics transforms individual scores into benchmarks.**
The database already stores `mcq_score`, `ai_recommendation`, `role_type`, and `evaluated_at` for every candidate. One SQL query gives you: median technical score for AI candidates this quarter; percentage of candidates cleared by the bias gate; average MCQ score by role. These are hiring intelligence metrics that no ATS currently provides at this granularity. Add a `/analytics` endpoint and one dashboard tab. The pipeline already generates the data.

**The user is building a hiring tool. The opportunity is a hiring intelligence platform.** The marginal engineering cost from one to the other is two endpoints and three SQL queries.

---

### ADVISOR 4 — THE OUTSIDER
*Zero context. Smart generalist seeing this for the first time. What looks weird from the outside?*

I have never seen this system before. Here is what looks immediately strange:

**The bias gate always passes.** I read that the system has a mandatory "bias gate" — a compliance checkpoint that blocks report compilation if bias is detected. Then I read the actual code. The gate unconditionally returns `True` (cleared) regardless of what it found. The description and the implementation are opposite things. To an outsider, this is not a bug — it is a misrepresentation. If someone showed this system to a regulator or an ethics board, the documented "mandatory compliance gate" would be cited as a feature. The implementation would be cited as evidence of misrepresentation.

**The system makes 8 LLM API calls per candidate evaluation, serially.** From the outside, this looks extremely expensive and slow. At Azure OpenAI pricing, roughly $0.15–$0.40 per full pipeline run depending on transcript length. That may sound cheap until you evaluate 200 candidates in a hiring round. More importantly, the user waits (polled by background task) for all 8 calls to complete before seeing any results. In a world where users expect real-time feedback, a 3–7 minute wait for a single candidate report will feel broken even when it works.

**The candidate's name appears in the final FeedbackReport.** The CV Parsing Agent goes to significant effort to anonymise the CV — stripping names, employers, institutions — and produces a `CandidateSkillsSummary` that is explicitly described as "PII-free." But the `FeedbackReport` at the top level has `candidate_name: str`. The Feedback Compiler Agent receives `candidate_name` as a direct argument and puts it in the report. The anonymisation effort is undermined at the final stage by design. Either the report should not contain names (so evaluators review anonymously), or the anonymisation effort is theatre.

**The dashboard authentication is Streamlit.** For a system handling candidate PII, hiring decisions, and audit trails, the authentication layer appears to be a Streamlit username/password check against hardcoded or env-var credentials. There is no session token, no role-based access control, no separation between an HR user who can view reports and an admin who can delete records. Any hiring manager with the dashboard URL and credentials can see all candidate records.

**The three databases are inconsistent.** I can see `database.db`, `interview.db`, and `interview_db.sqlite` in the project root. Three SQLite files. The settings say `database_path: str = "database.db"`. Which one is authoritative? Are there candidates in the other two from previous runs? No migration tooling is visible. This is a data integrity problem waiting to cause a support incident.

---

### ADVISOR 5 — THE EXECUTOR
*Skip theory. What is the single concrete action to take first? What ships this week?*

Stop. One action. Here is the only thing that matters right now:

**The bias gate returns `True` unconditionally. Fix it before anything else.**

File: `agents/bias_detection_agent.py`, line 135.
Current: `return bias_output, clean_comm, clean_tech, clean_prob, clean_cult, True, token_meta`
Fix: `return bias_output, clean_comm, clean_tech, clean_prob, clean_cult, not bias_output.bias_detected, token_meta`

That is a one-word change: replace the hardcoded `True` with `not bias_output.bias_detected`.

After that, the next five things in order of Monday-morning impact:

1. **Fix the `programming_answers` duplication** (api/main.py:448–451). Read the file once, split on a delimiter or section header if two questions exist. If only one question exists, pass it as a single-item list and let the Technical Depth Agent handle it. Stop passing the same text twice.

2. **Move PROGRESS_STORE to Redis or a shared state store.** If you are not ready for Redis, constrain the server to a single worker (`uvicorn --workers 1`) and document this as a known limitation. Right now it silently breaks in any non-trivial deployment.

3. **Add a request timeout to the background evaluation.** Wrap `interview_graph.stream(...)` in a `concurrent.futures.ThreadPoolExecutor` with a `timeout` argument, or add a `signal.alarm` on Linux. 300 seconds maximum. If the pipeline exceeds this, set `PROGRESS_STORE[candidate_id]["status"] = "timeout"` and surface it to the UI.

4. **Clean up the three SQLite files.** Delete `interview.db` and `interview_db.sqlite`. Set `database_path = "database.db"` as the single source of truth. Add a one-line comment in settings.py explaining that there is one database and one database only.

5. **Remove the `mcq_responses` field from `InterviewState` entirely.** It is initialized as `{}`, never populated, set to `None` in `ingestion_node`, and serves no purpose. Every time a developer reads `InterviewState`, this field creates confusion about what the intake contract is.

---

## STAGE 2 — ANONYMISE AND PEER REVIEW

**Shuffled mapping:**
- **Response A** → Advisor 5 (Executor)
- **Response B** → Advisor 2 (First Principles)
- **Response C** → Advisor 1 (Contrarian)
- **Response D** → Advisor 3 (Expansionist)
- **Response E** → Advisor 4 (Outsider)

---

### Peer Review — Three Questions

**1. Which response is strongest, and why?**

**Response C (Contrarian) is the strongest.** It is the only response that opens every claim with a specific file name, line number, and the exact code in question — then explains the consequence in plain terms. The bias gate finding alone (hardcoded `True` return value masquerading as a compliance mechanism) is a finding that neither the developer nor a project manager would have caught by reading the documentation. The `PROGRESS_STORE` multi-worker failure is similarly precise: not "this might be a problem in production" but "here is exactly when it breaks and why." The programming_answers duplication finding points to a data quality issue that directly corrupts the technical evaluation score. Response C earns its authority by doing the work — reading the actual code — rather than reasoning from structure.

**2. Which response has the biggest blind spot, and what is it?**

**Response D (Expansionist) has the biggest blind spot.** It proposes building a rubric marketplace, a compliance audit product, and a cohort analytics platform. Every one of these requires the core pipeline to produce correct, reliable output first. Response C established that the bias gate does not work, the PROGRESS_STORE fails under multi-worker deployment, and the programming answer input is corrupted. Building a "hiring intelligence platform" on top of a pipeline with a fake compliance gate is not ambitious — it is irresponsible. The expansionist frame treats the current system as a stable foundation when it is not.

**3. What did all five responses miss?**

**The LLM evaluation quality has no ground truth and no validation loop.**

None of the five advisors raised the question: how do we know the LLM evaluations are correct? The Technical Depth Agent produces per-dimension scores. The Communication Agent produces a score and evidence. But there is no mechanism anywhere in the system to:
- Compare LLM-generated scores against human-panel scores on the same transcript
- Flag when the LLM produces a 5/5 communication score for a candidate with a 1/5 technical score (suspicious correlation patterns)
- Alert when the same candidate evaluated twice produces scores more than 1 point apart (non-determinism check)

The `llm_temperature: float = 0.0` setting reduces but does not eliminate non-determinism. More importantly, `temperature=0` does not prevent the model from confidently producing wrong evaluations — it only makes wrong evaluations reproducible. Without a calibration mechanism, the system generates consistent noise with no way to detect it. The hiring manager sees a 4/5 technical score and trusts it. There is no evidence they should.

---

## STAGE 3 — THE CHAIRMAN

**Final Recommendation:**

The system's architecture is sound and several of the v1 bugs — TypedDict, parallel edges, SQLite persistence, per-dimension technical scoring — have been correctly addressed since the first council review. The pipeline now runs end-to-end, the data model is correct, and the rubric-driven evaluation produces structured, role-aware output.

**The single most important reason to act now:**

The bias gate — documented as the system's ethical backbone and compliance mechanism — unconditionally returns `True` and has never blocked a report in its existence. This is not a UX bug. It is a correctness failure in the feature that the system's entire ethical legitimacy rests on. If this system is used to evaluate real candidates, biased evaluations will be compiled into reports that the compliance log says were cleared. The audit trail will show "bias_detected: true" alongside a completed FeedbackReport. That combination is legally and ethically indefensible.

**One concrete next step:**

In `agents/bias_detection_agent.py`, line 135, change the hardcoded `True` to `not bias_output.bias_detected`. Then add a test: run the pipeline with a deliberately biased evaluation justification and confirm the pipeline routes to `END` instead of `compile_report`. Everything else — the PROGRESS_STORE fix, the programming_answers deduplication, the speaker isolation, the three SQLite files — is important, but none of it compromises the system's core claim the way a fake compliance gate does.

---
*Council session generated: 2026-06-23*
*Codebase state: post-v1-fixes, pre-deployment*
