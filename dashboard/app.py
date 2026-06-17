import json
import streamlit as st
import requests

st.set_page_config(
    page_title="AI Interview Evaluation Dashboard",
    page_icon="💼",
    layout="wide"
)

API_BASE_URL = "http://127.0.0.1:8000"

# ==============================================================================
# Custom CSS — premium dark theme
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .step-card {
        background: linear-gradient(135deg, #1e1e2e 0%, #2a2a3e 100%);
        border: 1px solid #3a3a5c;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
    }
    .step-header {
        font-size: 1rem;
        font-weight: 600;
        color: #a78bfa;
        margin-bottom: 4px;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .step-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #e2e8f0;
        margin-bottom: 12px;
    }
    .status-badge-awaiting {
        background: #92400e; color: #fde68a;
        padding: 3px 10px; border-radius: 20px;
        font-size: 0.75rem; font-weight: 600;
    }
    .status-badge-ready {
        background: #065f46; color: #6ee7b7;
        padding: 3px 10px; border-radius: 20px;
        font-size: 0.75rem; font-weight: 600;
    }
    .status-badge-evaluated {
        background: #1e3a5f; color: #93c5fd;
        padding: 3px 10px; border-radius: 20px;
        font-size: 0.75rem; font-weight: 600;
    }
    .queue-card {
        background: #1a1a2e;
        border: 1px solid #2d2d44;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
    }
    .completeness-bar {
        height: 6px; border-radius: 3px;
        background: #2d2d44; margin-top: 6px;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# Helper API Utilities
# ==============================================================================

def fetch_all_candidates():
    try:
        r = requests.get(f"{API_BASE_URL}/candidates", timeout=3)
        if r.status_code == 200:
            return r.json()
    except requests.exceptions.ConnectionError:
        pass
    return []


def fetch_intake_candidates():
    try:
        r = requests.get(f"{API_BASE_URL}/intake/candidates", timeout=3)
        if r.status_code == 200:
            return r.json()
    except requests.exceptions.ConnectionError:
        pass
    return []


def fetch_report(candidate_id: str):
    try:
        r = requests.get(f"{API_BASE_URL}/candidates/{candidate_id}/report", timeout=5)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 404:
            st.warning(f"🔍 Profile Record for ID '{candidate_id}' not found.")
        else:
            st.error(f"❌ Server error. Code: {r.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("🔌 Connection Failure: Cannot reach the backend engine.")
    return None


def submit_decision(candidate_id: str, decision: str):
    try:
        r = requests.patch(
            f"{API_BASE_URL}/candidates/{candidate_id}/decision",
            json={"decision": decision},
            timeout=3
        )
        if r.status_code == 200:
            st.success(f"✅ Status updated! Candidate locked to: '{decision}'")
            return True
        else:
            try:
                detail = r.json().get('detail', 'Unknown error')
            except ValueError:
                detail = f"Server error {r.status_code}"
            st.error(f"❌ Failed to submit decision: {detail}")
    except Exception as e:
        st.error(f"💥 Error: {str(e)}")
    return False


def intake_completeness(row: dict) -> int:
    """Returns a 0–100 completeness score for a candidate intake row."""
    fields = ["mcq_score", "cv_path", "session1_path", "session2_path",
              "programming_answer_1", "programming_answer_2"]
    filled = sum(1 for f in fields if row.get(f))
    return int((filled / len(fields)) * 100)


# ==============================================================================
# Page Header
# ==============================================================================
st.markdown("## 💼 AI Interview Evaluation Dashboard")
st.markdown("**Hiring Manager Review & Candidate Intake Suite**")
st.markdown("---")

# ==============================================================================
# Top-Level Tabs
# ==============================================================================
tab_reports, tab_intake = st.tabs(["📊 Candidate Reports", "➕ Add Candidate"])


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 1 — Candidate Reports (existing view, preserved exactly)              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_reports:

    col_main, col_sidebar = st.columns([3, 1])

    with col_sidebar:
        st.markdown("### 🗂️ Candidate Registry")

        all_candidates = fetch_all_candidates()
        decision_indicators = {"Hired": "🟢", "Rejected": "🔴", "Hold": "🟡"}
        rec_indicators = {"Strong Yes": "🟢", "Yes": "🔵", "Maybe": "🟡", "No": "🔴"}

        if all_candidates:
            st.markdown(f"**{len(all_candidates)} candidate(s) evaluated**")
            st.markdown("---")

            if "selected_candidate_id" not in st.session_state:
                st.session_state.selected_candidate_id = ""

            for candidate in all_candidates:
                cid = candidate["candidate_id"]
                name = candidate["candidate_name"]
                role = candidate["role_type"]
                mcq = candidate["mcq_score"]
                rec = candidate.get("ai_recommendation", "—")
                decision = candidate.get("hiring_decision", "Hold")
                evaluated_at = candidate.get("evaluated_at", "")[:10]

                dec_icon = decision_indicators.get(decision, "⚪")
                rec_icon = rec_indicators.get(rec, "⚪")
                button_label = f"{dec_icon} {name}\n{role} | MCQ: {mcq}/5 | {rec_icon} {rec}"
                if st.button(button_label, key=f"rep_{cid}", use_container_width=True):
                    st.session_state.selected_candidate_id = cid
                st.caption(f"Evaluated: {evaluated_at}")

            st.markdown("---")
        else:
            st.info("No candidates evaluated yet.")

        st.markdown("**Manual ID Lookup**")
        manual_id = st.text_input("Candidate ID", value="", placeholder="e.g., cand_xyz123",
                                   key="manual_id_input")
        if st.button("Load by ID", use_container_width=True, key="load_by_id_btn"):
            if manual_id.strip():
                st.session_state.selected_candidate_id = manual_id.strip()

    with col_main:
        candidate_id_to_load = st.session_state.get("selected_candidate_id", "").strip()

        if candidate_id_to_load:
            report = fetch_report(candidate_id_to_load)

            if report:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(label="Candidate Name", value=report["candidate_name"])
                with col2:
                    st.metric(label="Applied Target Track", value=report["role_applied"])
                with col3:
                    st.metric(label="Automated MCQ Score", value=f"{report['mcq_score']} / 5.0")
                    if report.get('mcq_insight'):
                        with st.expander("📝 MCQ Insight", expanded=True):
                            st.info(report['mcq_insight'])

                st.markdown("### 📊 Automated Test Code Submissions Insights")
                
                # Handle new programming_passed schema and fallback to legacy q1/q2
                if "programming_passed" in report and report["programming_passed"] is not None:
                    prog_status = "✅ PASS" if report["programming_passed"] else "❌ FAIL"
                    st.metric(label="Programming Logic & Approach", value=prog_status)
                    if report.get("programming_insight"):
                        with st.expander("💻 Programming Insight", expanded=True):
                            st.info(report["programming_insight"])
                else:
                    code_col1, code_col2 = st.columns(2)
                    with code_col1:
                        st.metric(label="Programming Q1 Score", value=f"{report.get('programming_q1_score', 'N/A')} / 5")
                    with code_col2:
                        st.metric(label="Programming Q2 Score", value=f"{report.get('programming_q2_score', 'N/A')} / 5")

                st.markdown("---")

                cv_match = report.get("cv_experience_match")
                if cv_match:
                    st.markdown("### 📄 CV Experience Match")
                    st.caption("Extracted from the candidate's uploaded CV — informational only.")
                    cv_col1, cv_col2, cv_col3 = st.columns(3)
                    with cv_col1:
                        st.metric(
                            label="Years of Experience",
                            value=cv_match["years_of_experience"],
                            delta=f"Role requires {cv_match['role_min_experience']}",
                            delta_color="off"
                        )
                    with cv_col2:
                        domain_emoji = {"strong": "🟢", "moderate": "🟡", "weak": "🔴"}.get(cv_match["domain_match"], "⚪")
                        st.metric(label="Domain Match", value=f"{domain_emoji} {cv_match['domain_match'].capitalize()}")
                    with cv_col3:
                        rating_emoji = {"strong": "🟢", "moderate": "🟡", "weak": "🔴"}.get(cv_match["overall_match_rating"], "⚪")
                        st.metric(label="Overall CV Rating", value=f"{rating_emoji} {cv_match['overall_match_rating'].capitalize()}")

                    skills_col1, skills_col2 = st.columns(2)
                    with skills_col1:
                        st.success("#### ✅ Required Skills Present")
                        for skill in cv_match.get("required_skills_present", []):
                            st.markdown(f"* {skill}")
                    with skills_col2:
                        st.error("#### ❌ Required Skills Missing")
                        missing = cv_match.get("required_skills_missing", [])
                        if missing:
                            for skill in missing:
                                st.markdown(f"* {skill}")
                        else:
                            st.markdown("*All required skills present.*")
                    st.markdown("---")

                st.markdown("### 🎛️ Multi-Agent Dimensional Analysis Breakdown")
                dim_col1, dim_col2 = st.columns(2)
                with dim_col1:
                    with st.expander(f"🗣️ Communication — Score: {report['communication']['score']}/5", expanded=True):
                        st.info(f"**Justification:** {report['communication']['justification']}")
                        if report['communication'].get('evidence'):
                            st.caption(f"**Evidence:** *\"{report['communication']['evidence']}\"*")

                    with st.expander(f"🧩 Problem Solving — Score: {report['problem_solving']['score']}/5", expanded=True):
                        st.info(f"**Justification:** {report['problem_solving']['justification']}")
                        if report['problem_solving'].get('evidence'):
                            st.caption(f"**Evidence:** *\"{report['problem_solving']['evidence']}\"*")

                with dim_col2:
                    with st.expander(f"💻 Technical Depth — Overall: {report['technical_depth']['overall_score']}/5", expanded=True):
                        st.info(f"**Overall Justification:** {report['technical_depth']['overall_justification']}")
                        st.markdown("#### 📐 Dimension Breakdown")
                        for dim in report['technical_depth']['dimensions']:
                            if dim.get('not_assessed'):
                                st.markdown(f"**⚪ {dim['dimension_name'].replace('_', ' ').title()}** — Not Assessed")
                                st.caption(dim['justification'])
                            else:
                                score = dim['score']
                                indicator = "🟢" if score >= 4 else "🟡" if score == 3 else "🔴"
                                st.markdown(f"**{indicator} {dim['dimension_name'].replace('_', ' ').title()}** — {score}/5")
                                st.caption(dim['justification'])
                                if dim.get('evidence'):
                                    st.caption(f"*Evidence: \"{dim['evidence']}\"*")

                    with st.expander(f"🤝 Cultural Alignment — Score: {report['cultural_alignment']['score']}/5", expanded=True):
                        st.info(f"**Justification:** {report['cultural_alignment']['justification']}")
                        if report['cultural_alignment'].get('evidence'):
                            st.caption(f"**Evidence:** *\"{report['cultural_alignment']['evidence']}\"*")

                st.markdown("---")

                bias_flags = report.get("interviewer_bias_flags")
                if bias_flags:
                    st.markdown("### ⚠️ Interviewer Bias Pre-Screen Alerts")
                    st.error(
                        f"**{len(bias_flags)} biased interviewer question(s) detected** in the transcript "
                        f"pre-screen. Scores have NOT been adjusted — review before committing a decision."
                    )
                    for flag in bias_flags:
                        severity_icon = "🔴" if flag["severity"] == "high" else "🟡"
                        with st.expander(f"{severity_icon} [{flag['severity'].upper()}] {flag['bias_category'].replace('_', ' ').title()}", expanded=True):
                            st.markdown(f"**Question:** {flag['question_text']}")
                            st.caption(f"**Rationale:** {flag['rationale']}")
                else:
                    st.success("✅ Interviewer Bias Pre-Screen: No biased questions detected.")

                st.markdown("---")
                st.markdown("### 🧠 AI Core Synthesis Summaries")
                synth_col1, synth_col2 = st.columns(2)
                with synth_col1:
                    st.success("#### 📈 Extracted Strengths")
                    for bullet in report["strengths"]:
                        st.markdown(f"* {bullet}")
                with synth_col2:
                    st.error("#### ⚠️ Critical Concerns")
                    for bullet in report["concerns"]:
                        st.markdown(f"* {bullet}")

                st.markdown("---")
                st.markdown("### 🏛️ Executive Verification & Human Decision Authorization")
                rec_color_map = {"Strong Yes": "🟢", "Yes": "🔵", "Maybe": "🟡", "No": "🔴"}
                rec_token = report["ai_recommendation"]
                st.markdown(f"#### Pipeline AI Recommendation: {rec_color_map.get(rec_token, '⚪')} **{rec_token}**")
                st.markdown(f"**System Rationale:** *{report['ai_justification']}*")
                st.warning(f"Current Status: **Hiring Manager Decision = {report['hiring_manager_decision']}**")

                st.markdown("---")
                st.markdown("#### 📋 Human Review Acknowledgment")
                st.info(
                    "Before committing a hiring decision, confirm you have reviewed the full evaluation "
                    "report including all dimension scores, bias flags, and agent justifications."
                )

                load_key = f"report_loaded_at_{candidate_id_to_load}"
                if load_key not in st.session_state:
                    from datetime import datetime, timezone
                    st.session_state[load_key] = datetime.now(timezone.utc).isoformat()

                check_dimensions = st.checkbox("✅ I have reviewed all dimension scores and justifications.", key=f"chk_dim_{candidate_id_to_load}")
                check_bias = st.checkbox("✅ I have reviewed the bias pre-screen results.", key=f"chk_bias_{candidate_id_to_load}")
                check_responsibility = st.checkbox("✅ I understand this decision is my professional responsibility.", key=f"chk_resp_{candidate_id_to_load}")

                all_acknowledged = check_dimensions and check_bias and check_responsibility

                if not all_acknowledged:
                    st.error("⛔ Decision form is locked. Please confirm all three acknowledgments above.")
                else:
                    st.success("🔓 Acknowledgments confirmed. You may now commit a hiring decision.")
                    with st.form(f"decision_form_{candidate_id_to_load}"):
                        selected_decision = st.selectbox("Update Candidate Status:", options=["Hold", "Hired", "Rejected"])
                        st.markdown("---")
                        from datetime import datetime, timezone
                        loaded_at = st.session_state.get(load_key, "Unknown")
                        st.caption(f"📅 Report first loaded at: `{loaded_at}`")
                        st.caption(f"⏱️ Decision being committed at: `{datetime.now(timezone.utc).isoformat()}`")
                        if st.form_submit_button("Commit Decision to Server", use_container_width=True):
                            commit_time = datetime.now(timezone.utc).isoformat()
                            import logging
                            oversight_logger = logging.getLogger("HumanOversight")
                            oversight_logger.info(
                                f"HUMAN DECISION COMMITTED | Candidate: {candidate_id_to_load} | "
                                f"Decision: {selected_decision} | "
                                f"Report loaded at: {loaded_at} | Committed at: {commit_time}"
                            )
                            if submit_decision(candidate_id_to_load, selected_decision):
                                st.session_state.selected_candidate_id = candidate_id_to_load
                                if load_key in st.session_state:
                                    del st.session_state[load_key]
        else:
            st.info("👋 Select a candidate from the registry or use Manual ID Lookup.")
            col_left, col_right = st.columns(2)
            with col_left:
                st.markdown("""
                ### 🔄 Getting Started:
                1. Ensure FastAPI is running on `http://127.0.0.1:8000`
                2. Add a candidate via the **➕ Add Candidate** tab
                3. Run evaluation once all files are uploaded
                4. Click their name here to load the full report
                """)
            with col_right:
                st.markdown("### 🛠️ Quick Diagnostics:")
                try:
                    r_health = requests.get(f"{API_BASE_URL}/health", timeout=2)
                    health = r_health.json() if r_health.status_code == 200 else {}
                    st.success(f"🟢 FastAPI connected. Status: `{health.get('status', 'ok')}`")
                except Exception:
                    st.error("🔴 FastAPI not reachable. Run `uvicorn api.main:app --reload` first.")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 2 — Add Candidate (Structured Intake Wizard)                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_intake:

    col_wizard, col_queue = st.columns([3, 2])

    # ── Session state initialisation ──────────────────────────────────────────
    for _key, _default in [
        ("intake_candidate_id",   None),
        ("intake_candidate_name", ""),
        ("intake_step2_done",     False),
        ("intake_confirm_dupe",   False),   # pending duplicate confirmation
        ("intake_dupe_name",      ""),      # name that triggered the dupe check
        ("intake_dupe_role",      ""),      # role that triggered the dupe check
        ("intake_dupe_records",   []),      # existing records with that name
        ("confirm_delete_id",     None),    # candidate_id pending delete confirmation
    ]:
        if _key not in st.session_state:
            st.session_state[_key] = _default

    # ── Helper: completeness from an intake record dict ───────────────────────
    def _doc_status(rec: dict) -> dict:
        """Returns a per-document True/False map based on DB fields."""
        return {
            "cv":          bool(rec.get("cv_path")),
            "session1":    bool(rec.get("session1_path")),
            "session2":    bool(rec.get("session2_path")),
            "mcq":         bool(rec.get("mcq_path")),          # file saved — scored later by agent
            "programming": bool(rec.get("programming_path")),      # file saved — evaluated by agent
        }

    def _completeness_pct(rec: dict) -> int:
        s = _doc_status(rec)
        return int(sum(s.values()) / len(s) * 100)

    # ── Helper: upload files to partial endpoint ──────────────────────────────
    def _upload_partial(cid: str, files_dict: dict) -> tuple:
        """Calls /intake/{cid}/upload with only the provided file objects. Returns (ok, msg, result)."""
        multipart = {k: (v.name, v.getvalue(), v.type or "application/octet-stream")
                     for k, v in files_dict.items() if v}
        if not multipart:
            return False, "No files selected.", None
        try:
            r = requests.post(
                f"{API_BASE_URL}/intake/{cid}/upload",
                files=multipart,
                timeout=30
            )
            if r.status_code == 200:
                try:
                    body = r.json()
                except ValueError:
                    body = {}
                return True, body.get("message", "Saved."), body
            try:
                err_body = r.json()
                err_msg = err_body.get("detail", "Upload failed.")
            except ValueError:
                err_msg = f"Server error {r.status_code}"
            return False, err_msg, None
        except requests.exceptions.ConnectionError:
            return False, "🔌 Cannot reach FastAPI.", None

    # ─────────────────────────────────────────────────────────────────────────
    with col_wizard:
        st.markdown("### ➕ Register New Candidate")
        st.caption("Complete all three steps to run the evaluation pipeline.")

        # ════════════════════════════════════════════════════════════════════
        # STEP 1 — Register candidate (with duplicate-name check)
        # ════════════════════════════════════════════════════════════════════
        st.markdown('<div class="step-card">', unsafe_allow_html=True)
        st.markdown('<div class="step-header">Step 1</div>', unsafe_allow_html=True)
        st.markdown('<div class="step-title">🪪 Register Candidate</div>', unsafe_allow_html=True)

        if st.session_state.intake_candidate_id:
            st.success(
                f"✅ **{st.session_state.intake_candidate_name}** registered as "
                f"`{st.session_state.intake_candidate_id}`"
            )

        elif st.session_state.intake_confirm_dupe:
            # ── Duplicate confirmation gate ──────────────────────────────────
            name = st.session_state.intake_dupe_name
            role = st.session_state.intake_dupe_role
            dupes = st.session_state.intake_dupe_records

            st.warning(f"⚠️ **Duplicate name detected!**")
            st.markdown(
                f"A candidate named **{name}** already exists in the intake system:"
            )
            for d in dupes:
                badge = {"awaiting_files": "⏳", "ready": "✅", "evaluated": "🟢"}.get(d["status"], "⚪")
                st.markdown(
                    f"- {badge} `{d['candidate_id']}` — **{d['role_type']}** — "
                    f"Status: `{d['status']}` — Created: `{d['created_at'][:10]}`"
                )

            st.markdown("---")
            st.markdown("**Are you sure you want to add a new candidate with the same name?**")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("✅ Yes, create anyway", key="dupe_yes", use_container_width=True, type="primary"):
                    try:
                        resp = requests.post(
                            f"{API_BASE_URL}/intake/create",
                            data={"candidate_name": name, "role_type": role},
                            timeout=5
                        )
                        if resp.status_code == 201:
                            data = resp.json()
                            st.session_state.intake_candidate_id = data["candidate_id"]
                            st.session_state.intake_candidate_name = name
                            st.session_state.intake_step2_done = False
                            st.session_state.intake_confirm_dupe = False
                            st.session_state.intake_dupe_records = []
                            st.rerun()
                        else:
                            try:
                                _d = resp.json().get('detail', 'Error')
                            except ValueError:
                                _d = f"Server error {resp.status_code}"
                            st.error(f"❌ {_d}")
                    except requests.exceptions.ConnectionError:
                        st.error("🔌 Cannot reach FastAPI.")
            with col_no:
                if st.button("❌ Cancel", key="dupe_no", use_container_width=True):
                    st.session_state.intake_confirm_dupe = False
                    st.session_state.intake_dupe_records = []
                    st.rerun()

        else:
            # ── Normal Step 1 form ───────────────────────────────────────────
            with st.form("step1_form"):
                s1_name = st.text_input("Full Name *", placeholder="e.g. Muhammad Umair")
                s1_role = st.selectbox(
                    "Role Applied For *",
                    options=["AI", "SWE", "BA", "Trainee"],
                    format_func=lambda x: {
                        "AI": "🤖 AI Engineer",
                        "SWE": "💻 Software Engineer",
                        "BA": "📊 Business Analyst",
                        "Trainee": "🎓 Trainee"
                    }[x]
                )
                submitted_s1 = st.form_submit_button("Create Candidate Profile →", use_container_width=True)

            if submitted_s1:
                name_clean = s1_name.strip()
                if not name_clean:
                    st.error("Full Name is required.")
                else:
                    # Duplicate check first
                    try:
                        check_r = requests.get(
                            f"{API_BASE_URL}/intake/check-duplicate",
                            params={"name": name_clean},
                            timeout=3
                        )
                        check_body = {}
                        if check_r.status_code == 200:
                            try:
                                check_body = check_r.json()
                            except ValueError:
                                pass
                        if check_body.get("has_duplicates"):
                            st.session_state.intake_confirm_dupe = True
                            st.session_state.intake_dupe_name = name_clean
                            st.session_state.intake_dupe_role = s1_role
                            st.session_state.intake_dupe_records = check_body.get("existing_records", [])
                            st.rerun()
                        else:
                            # No duplicate — create immediately
                            resp = requests.post(
                                f"{API_BASE_URL}/intake/create",
                                data={"candidate_name": name_clean, "role_type": s1_role},
                                timeout=5
                            )
                            if resp.status_code == 201:
                                try:
                                    data = resp.json()
                                except ValueError:
                                    data = {}
                                st.session_state.intake_candidate_id = data.get("candidate_id")
                                st.session_state.intake_candidate_name = name_clean
                                st.session_state.intake_step2_done = False
                                st.rerun()
                            else:
                                try:
                                    _d = resp.json().get('detail', 'Unknown error')
                                except ValueError:
                                    _d = f"Server error {resp.status_code}"
                                st.error(f"❌ {_d}")
                    except requests.exceptions.ConnectionError:
                        st.error("🔌 Cannot reach FastAPI.")

        st.markdown('</div>', unsafe_allow_html=True)

        # ════════════════════════════════════════════════════════════════════
        # STEP 2 — Per-document upload (partial saves supported)
        # ════════════════════════════════════════════════════════════════════
        step2_locked = st.session_state.intake_candidate_id is None

        st.markdown('<div class="step-card">', unsafe_allow_html=True)
        st.markdown('<div class="step-header">Step 2</div>', unsafe_allow_html=True)
        st.markdown('<div class="step-title">📁 Upload Documents</div>', unsafe_allow_html=True)

        if step2_locked:
            st.warning("⚠️ Complete Step 1 first to unlock file uploads.")
        else:
            cid = st.session_state.intake_candidate_id

            # Fetch live intake record to show current completeness
            try:
                _rec_r = requests.get(f"{API_BASE_URL}/intake/{cid}", timeout=3)
                live_rec = _rec_r.json() if _rec_r.status_code == 200 else {}
            except Exception:
                live_rec = {}

            doc_status = _doc_status(live_rec)
            pct = _completeness_pct(live_rec)

            # Progress bar
            bar_color = "#10b981" if pct == 100 else "#f59e0b"
            st.markdown(
                f"**Completeness: {pct}%**"
                f"<div style='background:#2d2d44;border-radius:4px;height:6px;margin-bottom:12px'>"
                f"<div style='background:{bar_color};width:{pct}%;height:6px;border-radius:4px'></div></div>",
                unsafe_allow_html=True
            )

            if pct == 100:
                st.success("✅ All documents uploaded. Proceed to Step 3.")
                st.session_state.intake_step2_done = True
            else:
                st.caption(
                    "Upload documents individually — you can save each one separately and come back later. "
                    "**CV** = PDF only. Everything else = PDF, TXT, or Word (.docx)."
                )

            # ── Per-document upload rows ──────────────────────────────────
            DOC_META = [
                ("cv",          "📄 CV",                          ["pdf"],              "cv_file",       "PDF only"),
                ("session1",    "🎙️ Session 1 (Technical)",       ["pdf","txt","docx"], "session1_file", "PDF, TXT, or DOCX"),
                ("session2",    "🎙️ Session 2 (HR / Behavioural)",["pdf","txt","docx"], "session2_file", "PDF, TXT, or DOCX"),
                ("mcq",         "📊 MCQ Results",                 ["pdf","txt","docx"], "mcq_file",      "PDF, TXT, or DOCX — AI reads the score automatically"),
                ("programming", "💻 Programming Answers",         ["pdf","txt","docx"], "prog_file_1",   "One document containing both Q1 & Q2 answers"),
            ]

            done_docs = []
            pending_docs = []

            for doc_key, label, types, field_name, hint in DOC_META:
                done = doc_status.get(doc_key, False)
                in_replace = st.session_state.get(f"replace_mode_{doc_key}_{cid}", False)
                if done and not in_replace:
                    done_docs.append((doc_key, label, types, field_name, hint))
                else:
                    pending_docs.append((doc_key, label, types, field_name, hint, in_replace))

            # Render locked docs first
            for doc_key, label, types, field_name, hint in done_docs:
                st.markdown(
                    f"<div style='border:1px solid #065f46;border-radius:8px;padding:10px 14px;margin-bottom:8px'>",
                    unsafe_allow_html=True
                )
                col_lbl, col_up = st.columns([2, 3])
                with col_lbl:
                    st.markdown(f"**✅ {label}**")
                    st.caption(hint)
                    st.markdown("<span style='color:#6ee7b7;font-size:0.75rem'>✔ Saved — locked</span>", unsafe_allow_html=True)
                with col_up:
                    if st.button(f"🔄 Replace {label}", key=f"replace_btn_{doc_key}_{cid}", use_container_width=True):
                        st.session_state[f"replace_mode_{doc_key}_{cid}"] = True
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            # Render pending docs in a single form
            if pending_docs:
                with st.form(f"upload_form_{cid}"):
                    st.markdown("#### ⏳ Pending Uploads")
                    uploaders = {}
                    for doc_key, label, types, field_name, hint, in_replace in pending_docs:
                        st.markdown(f"**{'🔄' if in_replace else '⬜'} {label}**")
                        st.caption(hint)
                        if in_replace:
                            st.caption("⚠️ New file will overwrite the existing one on disk and in the database.")
                        
                        uploaders[field_name] = st.file_uploader(
                            f"Choose file", type=types, key=f"up_{doc_key}_{cid}", label_visibility="collapsed"
                        )
                        st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)

                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        submitted = st.form_submit_button("💾 Save Selected Documents", use_container_width=True, type="primary")
                    with col_cancel:
                        has_replace = any(in_rep for _, _, _, _, _, in_rep in pending_docs)
                        if has_replace:
                            if st.form_submit_button("❌ Cancel Replacements", use_container_width=True):
                                for doc_key, _, _, _, _, in_replace in pending_docs:
                                    if in_replace:
                                        st.session_state[f"replace_mode_{doc_key}_{cid}"] = False
                                st.rerun()

                    if submitted:
                        files_to_upload = {f_name: up for f_name, up in uploaders.items() if up is not None}
                        if not files_to_upload:
                            st.error("No files selected to upload.")
                        else:
                            with st.spinner("Uploading documents..."):
                                ok, msg, result = _upload_partial(cid, files_to_upload)
                            if ok:
                                st.success("✅ Documents saved successfully!")
                                # clear replace modes for the files that were just uploaded
                                for doc_key, _, _, field_name, _, in_replace in pending_docs:
                                    if in_replace and uploaders.get(field_name) is not None:
                                        st.session_state[f"replace_mode_{doc_key}_{cid}"] = False
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")



        st.markdown('</div>', unsafe_allow_html=True)

        # ════════════════════════════════════════════════════════════════════
        # STEP 3 — Run evaluation
        # ════════════════════════════════════════════════════════════════════
        step3_locked = not st.session_state.intake_step2_done

        st.markdown('<div class="step-card">', unsafe_allow_html=True)
        st.markdown('<div class="step-header">Step 3</div>', unsafe_allow_html=True)
        st.markdown('<div class="step-title">🚀 Run AI Evaluation Pipeline</div>', unsafe_allow_html=True)

        if step3_locked:
            st.warning("⚠️ All documents must be uploaded before evaluation can run.")
        else:
            cid  = st.session_state.intake_candidate_id
            cname = st.session_state.intake_candidate_name
            st.info(
                f"**Candidate:** {cname}  \n"
                f"**ID:** `{cid}`  \n"
                "All documents are uploaded. The multi-agent evaluation pipeline is ready to run. "
                "This takes 60–120 seconds."
            )
            if st.button("🚀 Run Full Evaluation Now", key="run_eval_btn",
                         use_container_width=True, type="primary"):
                try:
                    resp = requests.post(f"{API_BASE_URL}/intake/{cid}/evaluate", timeout=30)
                    if resp.status_code == 200:
                        import time
                        with st.status("Evaluating candidate in background...", expanded=True) as status_ui:
                            seen_events = set()
                            while True:
                                prog_resp = requests.get(f"{API_BASE_URL}/intake/{cid}/progress", timeout=5).json()
                                status_state = prog_resp.get("status")
                                events = prog_resp.get("events", [])
                                
                                for ev in events:
                                    if ev not in seen_events:
                                        friendly_name = ev.replace("_", " ").title()
                                        st.write(f"✅ Completed node: **{friendly_name}**")
                                        seen_events.add(ev)
                                        
                                if status_state == "completed":
                                    status_ui.update(label="Evaluation Complete!", state="complete", expanded=False)
                                    st.session_state.intake_candidate_id = None
                                    st.session_state.intake_candidate_name = ""
                                    st.session_state.intake_step2_done = False
                                    st.rerun()  # forces full page refresh so Reports tab picks up the new candidate
                                elif status_state == "failed":
                                    status_ui.update(label="Evaluation Failed!", state="error", expanded=True)
                                    st.error(f"❌ {prog_resp.get('error')}")
                                    break
                                    
                                time.sleep(1.5)
                    else:
                        try:
                            err_detail = resp.json().get('detail', 'Evaluation failed.')
                        except ValueError:
                            err_detail = f"Server returned {resp.status_code}: {resp.text}"
                        st.error(f"❌ {err_detail}")
                except requests.exceptions.ConnectionError:
                    st.error("🔌 Cannot reach FastAPI.")

        st.markdown('</div>', unsafe_allow_html=True)

        # Reset / start over
        if st.session_state.intake_candidate_id:
            st.markdown("---")
            if st.button("🔄 Start Over (new candidate)", key="reset_wizard"):
                for k in ["intake_candidate_id", "intake_candidate_name",
                          "intake_step2_done", "intake_confirm_dupe",
                          "intake_dupe_name", "intake_dupe_role", "intake_dupe_records"]:
                    st.session_state[k] = "" if k in ("intake_candidate_name","intake_dupe_name","intake_dupe_role") \
                                          else ([] if k == "intake_dupe_records" \
                                          else (False if "done" in k or "confirm" in k \
                                          else None))
                st.rerun()

    # ── RIGHT: Intake queue ────────────────────────────────────────────────────
    with col_queue:
        st.markdown("### 📋 Intake Queue")
        st.caption("All candidates in the intake pipeline.")

        if st.button("🔃 Refresh", key="refresh_queue", use_container_width=True):
            st.rerun()

        intake_list = fetch_intake_candidates()

        if not intake_list:
            st.info("No candidates yet. Use the wizard to add one.")
        else:
            awaiting  = [r for r in intake_list if r["status"] == "awaiting_files"]
            ready     = [r for r in intake_list if r["status"] == "ready"]
            awaiting  = [r for r in intake_list if r["status"] == "awaiting_files"]
            ready     = [r for r in intake_list if r["status"] == "ready"]

            # ── Ready ────────────────────────────────────────────────────────
            if ready:
                st.markdown(f"**✅ Ready to Evaluate ({len(ready)})**")
                for row in ready:
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.markdown(
                            f"**{row['candidate_name']}**  \n"
                            f"<span class='status-badge-ready'>READY</span> &nbsp; {row['role_type']}",
                            unsafe_allow_html=True
                        )
                        st.caption(f"`{row['candidate_id']}`")
                    with col_b:
                        if st.button("🚀", key=f"q_eval_{row['candidate_id']}", help="Run Evaluation"):
                            try:
                                r = requests.post(
                                    f"{API_BASE_URL}/intake/{row['candidate_id']}/evaluate",
                                    timeout=30
                                )
                                if r.status_code == 200:
                                    import time
                                    with st.status(f"Evaluating {row['candidate_name']}...", expanded=True) as status_ui:
                                        seen_ev = set()
                                        while True:
                                            pg = requests.get(f"{API_BASE_URL}/intake/{row['candidate_id']}/progress", timeout=5).json()
                                            for ev in pg.get("events", []):
                                                if ev not in seen_ev:
                                                    st.write(f"✅ {ev.replace('_', ' ').title()}")
                                                    seen_ev.add(ev)
                                            if pg.get("status") == "completed":
                                                status_ui.update(label="Done!", state="complete", expanded=False)
                                                st.rerun()
                                                break
                                            elif pg.get("status") == "failed":
                                                status_ui.update(label="Failed!", state="error")
                                                st.error(f"❌ {pg.get('error')}")
                                                break
                                            time.sleep(1.5)
                                else:
                                    try:
                                        detail = r.json().get("detail", "Evaluation failed.")
                                    except ValueError:
                                        detail = f"Server error {r.status_code}: {r.text[:200]}"
                                    st.error(f"❌ {detail}")
                            except requests.exceptions.ConnectionError:
                                st.error("🔌 FastAPI not reachable.")
                    st.markdown("---")

            # ── Awaiting ─────────────────────────────────────────────────────
            if awaiting:
                st.markdown(f"**⏳ Awaiting Files ({len(awaiting)})**")
                for row in awaiting:
                    pct = _completeness_pct(row)
                    cid_row = row["candidate_id"]
                    st.markdown(
                        f"**{row['candidate_name']}**  \n"
                        f"<span class='status-badge-awaiting'>AWAITING FILES</span> &nbsp; {row['role_type']}",
                        unsafe_allow_html=True
                    )
                    st.caption(f"`{cid_row}` · {pct}% complete · {row['created_at'][:10]}")
                    st.markdown(
                        f"<div style='background:#2d2d44;border-radius:3px;height:4px;margin-bottom:6px'>"
                        f"<div style='background:#f59e0b;width:{pct}%;height:4px;border-radius:3px'></div></div>",
                        unsafe_allow_html=True
                    )

                    # ── Delete confirmation flow ────────────────────────────────
                    if st.session_state.confirm_delete_id == cid_row:
                        st.error(
                            f"⚠️ **Delete `{row['candidate_name']}`?**  \n"
                            "This will permanently remove the DB record AND the entire "
                            f"`fixtures/candidates/{cid_row}/` folder."
                        )
                        del_col1, del_col2 = st.columns(2)
                        with del_col1:
                            if st.button(
                                "🗑️ Yes, permanently delete",
                                key=f"del_confirm_{cid_row}",
                                use_container_width=True,
                                type="primary"
                            ):
                                try:
                                    r = requests.delete(
                                        f"{API_BASE_URL}/intake/{cid_row}",
                                        timeout=5
                                    )
                                    if r.status_code == 200:
                                        try:
                                            _msg = r.json().get('message', 'Deleted.')
                                        except ValueError:
                                            _msg = 'Deleted.'
                                        st.success(f"✅ {_msg}")
                                        st.session_state.confirm_delete_id = None
                                        # If this was the active wizard candidate, reset wizard
                                        if st.session_state.intake_candidate_id == cid_row:
                                            st.session_state.intake_candidate_id = None
                                            st.session_state.intake_candidate_name = ""
                                            st.session_state.intake_step2_done = False
                                        st.rerun()
                                    else:
                                        try:
                                            _err = r.json().get('detail', 'Delete failed.')
                                        except ValueError:
                                            _err = f"Server error {r.status_code}"
                                        st.error(f"❌ {_err}")
                                        st.session_state.confirm_delete_id = None
                                except requests.exceptions.ConnectionError:
                                    st.error("🔌 Cannot reach FastAPI.")
                        with del_col2:
                            if st.button(
                                "❌ Cancel",
                                key=f"del_cancel_{cid_row}",
                                use_container_width=True
                            ):
                                st.session_state.confirm_delete_id = None
                                st.rerun()
                    else:
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button(
                                f"📂 Resume — {row['candidate_name']}",
                                key=f"q_resume_{cid_row}",
                                use_container_width=True,
                                type="primary"
                            ):
                                st.session_state.intake_candidate_id   = cid_row
                                st.session_state.intake_candidate_name = row["candidate_name"]
                                st.session_state.intake_step2_done     = False
                                st.session_state.intake_confirm_dupe   = False
                                st.rerun()
                        with btn_col2:
                            if st.button(
                                "🗑️ Delete",
                                key=f"q_delete_{cid_row}",
                                use_container_width=True
                            ):
                                st.session_state.confirm_delete_id = cid_row
                                st.rerun()

                    st.markdown("---")


