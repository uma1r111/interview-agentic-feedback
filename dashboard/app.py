import json
import streamlit as st
import requests
from datetime import datetime, timezone

from auth_ui import require_login, render_topbar

st.set_page_config(
    page_title="AI Interview Evaluation Dashboard",
    page_icon="💼",
    layout="wide"
)

# ==============================================================================
# Authentication Gate — must run before anything else renders
# ==============================================================================
current_user = require_login()
render_topbar(current_user)

USER_ROLE = current_user["role"]            # "hr" or "hiring_manager"
USER_DISPLAY_NAME = current_user["display_name"]

API_BASE_URL = "http://127.0.0.1:8000"

# ==============================================================================
# Custom CSS — Imperium Dynamics purple/white theme
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .step-card {
        background: linear-gradient(135deg, #FAF8FD 0%, #F3EEFA 100%);
        border: 1px solid #E5DEF0;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
    }
    .step-header {
        font-size: 1rem;
        font-weight: 600;
        color: #5B2A8E;
        margin-bottom: 4px;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .step-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #1F1530;
        margin-bottom: 12px;
    }
    .status-badge-awaiting {
        background: #FFF6E5; color: #92660B;
        padding: 3px 10px; border-radius: 20px;
        font-size: 0.75rem; font-weight: 600;
    }
    .status-badge-ready {
        background: #E3F8EC; color: #0F7A3D;
        padding: 3px 10px; border-radius: 20px;
        font-size: 0.75rem; font-weight: 600;
    }
    .status-badge-evaluated {
        background: #EDE4F8; color: #3D1B63;
        padding: 3px 10px; border-radius: 20px;
        font-size: 0.75rem; font-weight: 600;
    }
    .queue-card {
        background: #FAF8FD;
        border: 1px solid #E5DEF0;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
    }
    .completeness-bar {
        height: 6px; border-radius: 3px;
        background: #E5DEF0; margin-top: 6px;
    }
    .decision-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
    }
    .decision-badge-hired { background: #E3F8EC; color: #0F7A3D; }
    .decision-badge-rejected { background: #FDE9E9; color: #B42318; }
    .decision-badge-hold { background: #FFF6E5; color: #92660B; }
    .decision-meta {
        font-size: 0.75rem;
        color: #6B6178;
        margin-top: 4px;
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


def fetch_audit_trail(candidate_id: str):
    """Fetches the decision audit history for a candidate. Returns [] on failure."""
    try:
        r = requests.get(f"{API_BASE_URL}/candidates/{candidate_id}/audit", timeout=3)
        if r.status_code == 200:
            return r.json()
    except requests.exceptions.ConnectionError:
        pass
    return []


def submit_decision(candidate_id: str, decision: str, changed_by: str):
    try:
        r = requests.patch(
            f"{API_BASE_URL}/candidates/{candidate_id}/decision",
            json={"decision": decision, "changed_by": changed_by},
            timeout=3
        )
        if r.status_code == 200:
            st.success(f"✅ Status updated! Candidate locked to: '{decision}'")
            return True
        else:
            st.error(f"❌ Failed to submit decision: {r.json().get('detail')}")
    except Exception as e:
        st.error(f"💥 Error: {str(e)}")
    return False


def intake_completeness(row: dict) -> int:
    """Returns a 0–100 completeness score for a candidate intake row."""
    fields = ["mcq_score", "cv_path", "session1_path", "session2_path",
              "programming_answer_1", "programming_answer_2"]
    filled = sum(1 for f in fields if row.get(f))
    return int((filled / len(fields)) * 100)


def render_decision_readonly_badge(candidate_id: str, current_decision: str):
    """
    Renders a read-only badge showing the current hiring decision plus who/when
    it was last changed. Used in the HR view, where the decision form itself
    is hidden — HR can see the outcome but cannot set or change it.
    """
    badge_class_map = {
        "Hired": "decision-badge-hired",
        "Rejected": "decision-badge-rejected",
        "Hold": "decision-badge-hold",
    }
    badge_class = badge_class_map.get(current_decision, "decision-badge-hold")

    st.markdown(
        f'<span class="decision-badge {badge_class}">{current_decision}</span>',
        unsafe_allow_html=True
    )

    audit_trail = fetch_audit_trail(candidate_id)
    if audit_trail:
        latest = audit_trail[-1]
        changed_by = latest.get("changed_by", "unknown")
        changed_at = latest.get("changed_at", "")[:16].replace("T", " ")
        st.markdown(
            f'<div class="decision-meta">Set by {changed_by} · {changed_at} UTC</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="decision-meta">No decision changes recorded yet.</div>',
            unsafe_allow_html=True
        )


# ==============================================================================
# Page Header
# ==============================================================================
st.markdown("## 💼 AI Interview Evaluation Dashboard")
if USER_ROLE == "hiring_manager":
    st.markdown("**Hiring Manager Review — Final Decision Authority**")
else:
    st.markdown("**HR Review & Candidate Intake Suite**")
st.markdown("---")

# ==============================================================================
# Top-Level Tabs — role-gated
# ==============================================================================
# Hiring Managers never see the Add Candidate tab rendered at all (not just
# hidden) — intake is exclusively an HR responsibility. HR never sees the
# decision-commit controls — they can view the AI recommendation and the
# final decision once set, but cannot change it.
if USER_ROLE == "hr":
    tab_reports, tab_intake = st.tabs(["📊 Candidate Reports", "➕ Add Candidate"])
else:
    tab_reports = st.tabs(["📊 Candidate Reports"])[0]
    tab_intake = None


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 1 — Candidate Reports                                                  ║
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

                st.markdown("### 📊 Automated Test Code Submissions Insights")
                code_col1, code_col2 = st.columns(2)
                with code_col1:
                    st.metric(label="Programming Q1 Score", value=f"{report['programming_q1_score']} / 5")
                with code_col2:
                    st.metric(label="Programming Q2 Score", value=f"{report['programming_q2_score']} / 5")

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
                st.markdown("### 🏛️ Executive Verification & Decision")
                rec_color_map = {"Strong Yes": "🟢", "Yes": "🔵", "Maybe": "🟡", "No": "🔴"}
                rec_token = report["ai_recommendation"]
                st.markdown(f"#### Pipeline AI Recommendation: {rec_color_map.get(rec_token, '⚪')} **{rec_token}**")
                st.markdown(f"**System Rationale:** *{report['ai_justification']}*")

                # ──────────────────────────────────────────────────────────
                # ROLE-GATED SECTION
                # Hiring Manager: full acknowledgment + decision form, exactly
                #                  as before, but changed_by now records the
                #                  real logged-in user instead of a hardcoded
                #                  string.
                # HR:              read-only badge only. HR can see the
                #                  outcome but never gets the commit controls,
                #                  since final decision authority belongs
                #                  solely to the Hiring Manager.
                # ──────────────────────────────────────────────────────────
                if USER_ROLE == "hiring_manager":
                    st.warning(f"Current Status: **Hiring Manager Decision = {report['hiring_manager_decision']}**")

                    st.markdown("---")
                    st.markdown("#### 📋 Human Review Acknowledgment")
                    st.info(
                        "Before committing a hiring decision, confirm you have reviewed the full evaluation "
                        "report including all dimension scores, bias flags, and agent justifications."
                    )

                    load_key = f"report_loaded_at_{candidate_id_to_load}"
                    if load_key not in st.session_state:
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
                            loaded_at = st.session_state.get(load_key, "Unknown")
                            st.caption(f"📅 Report first loaded at: `{loaded_at}`")
                            st.caption(f"⏱️ Decision being committed at: `{datetime.now(timezone.utc).isoformat()}`")
                            st.caption(f"👤 Committing as: **{USER_DISPLAY_NAME}**")
                            if st.form_submit_button("Commit Decision to Server", use_container_width=True):
                                commit_time = datetime.now(timezone.utc).isoformat()
                                import logging
                                oversight_logger = logging.getLogger("HumanOversight")
                                oversight_logger.info(
                                    f"HUMAN DECISION COMMITTED | Candidate: {candidate_id_to_load} | "
                                    f"Decision: {selected_decision} | Committed by: {USER_DISPLAY_NAME} | "
                                    f"Report loaded at: {loaded_at} | Committed at: {commit_time}"
                                )
                                if submit_decision(candidate_id_to_load, selected_decision, USER_DISPLAY_NAME):
                                    st.session_state.selected_candidate_id = candidate_id_to_load
                                    if load_key in st.session_state:
                                        del st.session_state[load_key]
                else:
                    # HR view — read-only outcome badge, no commit controls
                    st.markdown("#### Final Hiring Decision")
                    render_decision_readonly_badge(
                        candidate_id_to_load,
                        report["hiring_manager_decision"]
                    )
                    st.caption(
                        "The final hiring decision is set exclusively by the Hiring Manager. "
                        "This view is read-only."
                    )
        else:
            st.info("👋 Select a candidate from the registry or use Manual ID Lookup.")
            col_left, col_right = st.columns(2)
            with col_left:
                if USER_ROLE == "hr":
                    st.markdown("""
                    ### 🔄 Getting Started:
                    1. Ensure FastAPI is running on `http://127.0.0.1:8000`
                    2. Add a candidate via the **➕ Add Candidate** tab
                    3. Run evaluation once all files are uploaded
                    4. Click their name here to load the full report
                    """)
                else:
                    st.markdown("""
                    ### 🔄 Getting Started:
                    1. Ensure FastAPI is running on `http://127.0.0.1:8000`
                    2. Select an evaluated candidate from the registry
                    3. Review the full dimensional breakdown and bias screen
                    4. Acknowledge the review checklist to unlock the decision form
                    """)
            with col_right:
                st.markdown("### 🛠️ Quick Diagnostics:")
                try:
                    health = requests.get(f"{API_BASE_URL}/health", timeout=2).json()
                    st.success(f"🟢 FastAPI connected. Status: `{health.get('status')}`")
                except Exception:
                    st.error("🔴 FastAPI not reachable. Run `uvicorn api.main:app --reload` first.")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 2 — Add Candidate (HR only — tab_intake is None for Hiring Manager)   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
if tab_intake is not None:
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
                    return True, r.json().get("message", "Saved."), r.json()
                return False, r.json().get("detail", "Upload failed."), None
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
                                st.error(f"❌ {resp.json().get('detail', 'Error')}")
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
                            if check_r.status_code == 200 and check_r.json().get("has_duplicates"):
                                st.session_state.intake_confirm_dupe = True
                                st.session_state.intake_dupe_name = name_clean
                                st.session_state.intake_dupe_role = s1_role
                                st.session_state.intake_dupe_records = check_r.json()["existing_records"]
                                st.rerun()
                            else:
                                # No duplicate — create immediately
                                resp = requests.post(
                                    f"{API_BASE_URL}/intake/create",
                                    data={"candidate_name": name_clean, "role_type": s1_role},
                                    timeout=5
                                )
                                if resp.status_code == 201:
                                    data = resp.json()
                                    st.session_state.intake_candidate_id = data["candidate_id"]
                                    st.session_state.intake_candidate_name = name_clean
                                    st.session_state.intake_step2_done = False
                                    st.rerun()
                                else:
                                    st.error(f"❌ {resp.json().get('detail', 'Unknown error')}")
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
                    live_rec = requests.get(f"{API_BASE_URL}/intake/{cid}", timeout=3).json()
                except Exception:
                    live_rec = {}

                doc_status = _doc_status(live_rec)
                pct = _completeness_pct(live_rec)

                # Progress bar
                bar_color = "#0F7A3D" if pct == 100 else "#92660B"
                st.markdown(
                    f"**Completeness: {pct}%**"
                    f"<div style='background:#E5DEF0;border-radius:4px;height:6px;margin-bottom:12px'>"
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

                for doc_key, label, types, field_name, hint in DOC_META:
                    done        = doc_status.get(doc_key, False)
                    replace_key = f"replace_mode_{doc_key}_{cid}"
                    in_replace  = st.session_state.get(replace_key, False)

                    icon   = "✅" if done else "⬜"
                    border = "#0F7A3D" if (done and not in_replace) else ("#5B2A8E" if in_replace else "#E5DEF0")

                    st.markdown(
                        f"<div style='border:1px solid {border};border-radius:8px;padding:10px 14px;margin-bottom:8px'>",
                        unsafe_allow_html=True
                    )
                    col_lbl, col_up = st.columns([2, 3])
                    with col_lbl:
                        st.markdown(f"**{icon} {label}**")
                        st.caption(hint)
                        if done and not in_replace:
                            st.markdown(
                                "<span style='color:#0F7A3D;font-size:0.75rem'>✔ Saved — locked</span>",
                                unsafe_allow_html=True
                            )
                        elif in_replace:
                            st.markdown(
                                "<span style='color:#5B2A8E;font-size:0.75rem'>🔄 Replace mode active</span>",
                                unsafe_allow_html=True
                            )

                    with col_up:
                        if done and not in_replace:
                            # ── LOCKED: show Replace button only ─────────────────
                            if st.button(
                                f"🔄 Replace {label}",
                                key=f"replace_btn_{doc_key}_{cid}",
                                use_container_width=True
                            ):
                                st.session_state[replace_key] = True
                                st.rerun()

                        elif done and in_replace:
                            # ── REPLACE MODE: uploader + Save & Cancel ────────────
                            st.caption("⚠️ New file will overwrite the existing one on disk and in the database.")
                            uploaded = st.file_uploader(
                                f"Choose replacement for {label}",
                                type=types,
                                key=f"uploader_{doc_key}_{cid}",
                                label_visibility="collapsed"
                            )
                            save_col, cancel_col = st.columns(2)
                            with save_col:
                                if uploaded:
                                    if st.button("💾 Save & Replace", key=f"save_{doc_key}_{cid}", use_container_width=True):
                                        with st.spinner(f"Replacing {label}..."):
                                            ok, msg, result = _upload_partial(cid, {field_name: uploaded})
                                        if ok:
                                            st.success(
                                                f"✅ {label} replaced!"
                                                + (f" New MCQ Score: **{result.get('mcq_score')}/5.0**"
                                                   if doc_key == "mcq" and result.get("mcq_score") else "")
                                            )
                                            st.session_state[replace_key] = False
                                            st.rerun()
                                        else:
                                            st.error(f"❌ {msg}")
                            with cancel_col:
                                if st.button("❌ Cancel", key=f"cancel_{doc_key}_{cid}", use_container_width=True):
                                    st.session_state[replace_key] = False
                                    st.rerun()

                        else:
                            # ── EMPTY: first-time upload ──────────────────────────
                            uploaded = st.file_uploader(
                                f"Upload {label}",
                                type=types,
                                key=f"uploader_{doc_key}_{cid}",
                                label_visibility="collapsed"
                            )
                            if uploaded:
                                if st.button(f"💾 Save {label}", key=f"save_{doc_key}_{cid}", use_container_width=True):
                                    with st.spinner(f"Saving {label}..."):
                                        ok, msg, result = _upload_partial(cid, {field_name: uploaded})
                                    if ok:
                                        st.success(
                                            f"✅ {label} saved!"
                                            + (f" MCQ Score extracted: **{result.get('mcq_score')}/5.0**"
                                               if doc_key == "mcq" and result.get("mcq_score") else "")
                                        )
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
                    with st.spinner(f"Evaluating {cname}... (1–2 minutes)"):
                        try:
                            resp = requests.post(f"{API_BASE_URL}/intake/{cid}/evaluate", timeout=300)
                            if resp.status_code == 200:
                                st.success(
                                    f"✅ Evaluation complete! Switch to **📊 Candidate Reports** "
                                    f"and load ID `{cid}` to view the report."
                                )
                                st.session_state.intake_candidate_id = None
                                st.session_state.intake_candidate_name = ""
                                st.session_state.intake_step2_done = False
                            else:
                                st.error(f"❌ {resp.json().get('detail', 'Evaluation failed.')}")
                        except requests.exceptions.ReadTimeout:
                            st.warning("⏱️ Request timed out — pipeline may still be running. Check Reports tab.")
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
                evaluated = [r for r in intake_list if r["status"] == "evaluated"]

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
                                with st.spinner(f"Evaluating {row['candidate_name']}..."):
                                    try:
                                        r = requests.post(
                                            f"{API_BASE_URL}/intake/{row['candidate_id']}/evaluate",
                                            timeout=300
                                        )
                                        if r.status_code == 200:
                                            st.success("Done! Check Candidate Reports.")
                                            st.rerun()
                                        else:
                                            st.error(r.json().get("detail", "Error"))
                                    except requests.exceptions.ReadTimeout:
                                        st.warning("Timeout — check Reports tab in a moment.")
                                    except requests.exceptions.ConnectionError:
                                        st.error("FastAPI not reachable.")
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
                            f"<div style='background:#E5DEF0;border-radius:3px;height:4px;margin-bottom:6px'>"
                            f"<div style='background:#92660B;width:{pct}%;height:4px;border-radius:3px'></div></div>",
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
                                            st.success(f"✅ {r.json().get('message', 'Deleted.')}")
                                            st.session_state.confirm_delete_id = None
                                            # If this was the active wizard candidate, reset wizard
                                            if st.session_state.intake_candidate_id == cid_row:
                                                st.session_state.intake_candidate_id = None
                                                st.session_state.intake_candidate_name = ""
                                                st.session_state.intake_step2_done = False
                                            st.rerun()
                                        else:
                                            st.error(f"❌ {r.json().get('detail', 'Delete failed.')}")
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

                # ── Evaluated ────────────────────────────────────────────────────
                if evaluated:
                    st.markdown(f"**🟢 Evaluated ({len(evaluated)})**")
                    for row in evaluated:
                        st.markdown(
                            f"**{row['candidate_name']}**  \n"
                            f"<span class='status-badge-evaluated'>EVALUATED</span> &nbsp; {row['role_type']}",
                            unsafe_allow_html=True
                        )
                        st.caption(
                            f"`{row['candidate_id']}` · "
                            f"Evaluated: {(row.get('evaluated_at') or '')[:10]}"
                        )
                        st.markdown("---")