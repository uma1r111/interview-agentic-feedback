import streamlit as st
import requests

st.set_page_config(
    page_title="AI Interview Evaluation Dashboard",
    page_icon="💼",
    layout="wide"
)

API_BASE_URL = "http://127.0.0.1:8000"

st.title("💼 AI Interview Feedback - Reviewer Dashboard")
st.subheader("Hiring Manager One-Click Review & Evaluation Suite")
st.markdown("---")

# ==============================================================================
# Helper API Fetch Utilities
# ==============================================================================
def fetch_all_candidates():
    """Fetches the list of all candidates from the backend SQLite database."""
    try:
        response = requests.get(f"{API_BASE_URL}/candidates", timeout=3)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.ConnectionError:
        pass
    return []

def fetch_report(candidate_id: str):
    """Retrieves a candidate's consolidated FeedbackReport from the backend server."""
    try:
        response = requests.get(f"{API_BASE_URL}/candidates/{candidate_id}/report", timeout=5)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            st.warning(f"🔍 Profile Record for ID '{candidate_id}' not found.")
        elif response.status_code == 204:
            st.info("⏳ Candidate profile is initializing but report synthesis has not finished.")
        else:
            st.error(f"❌ Server error encountered. Code: {response.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("🔌 Connection Failure: Cannot reach the backend engine.")
    return None

def submit_decision(candidate_id: str, decision: str):
    """Submits the hiring manager's final decision selection for a candidate back to the database."""
    try:
        response = requests.patch(
            f"{API_BASE_URL}/candidates/{candidate_id}/decision",
            json={"decision": decision},
            timeout=3
        )
        if response.status_code == 200:
            st.success(f"✅ Status updated! Candidate locked to: '{decision}'")
            return True
        else:
            st.error(f"❌ Failed to submit decision: {response.json().get('detail')}")
    except Exception as e:
        st.error(f"💥 Error: {str(e)}")
    return False

# ==============================================================================
# Sidebar — Candidate List + Manual Lookup
# ==============================================================================
with st.sidebar:
    st.header("🗂️ Candidate Registry")

    # Fetch candidate list from API
    all_candidates = fetch_all_candidates()

    # Decision color indicators
    decision_indicators = {
        "Hired": "🟢",
        "Rejected": "🔴",
        "Hold": "🟡"
    }
    rec_indicators = {
        "Strong Yes": "🟢",
        "Yes": "🔵",
        "Maybe": "🟡",
        "No": "🔴"
    }

    if all_candidates:
        st.markdown(f"**{len(all_candidates)} candidate(s) evaluated**")
        st.markdown("---")

        # Initialize selected candidate in session state
        if "selected_candidate_id" not in st.session_state:
            st.session_state.selected_candidate_id = ""

        for candidate in all_candidates:
            cid = candidate["candidate_id"]
            name = candidate["candidate_name"]
            role = candidate["role_type"]
            mcq = candidate["mcq_score"]
            rec = candidate.get("ai_recommendation", "—")
            decision = candidate.get("hiring_decision", "Hold")
            evaluated_at = candidate.get("evaluated_at", "")[:10]  # Date only

            dec_icon = decision_indicators.get(decision, "⚪")
            rec_icon = rec_indicators.get(rec, "⚪")

            # Candidate card button
            button_label = f"{dec_icon} {name}\n{role} | MCQ: {mcq}/5 | {rec_icon} {rec}"
            if st.button(button_label, key=cid, use_container_width=True):
                st.session_state.selected_candidate_id = cid

            st.caption(f"Evaluated: {evaluated_at}")

        st.markdown("---")
    else:
        st.info("No candidates evaluated yet. Submit a candidate via `submit_test.py` to populate this list.")

    # Manual ID lookup still available as fallback
    st.markdown("**Manual ID Lookup**")
    manual_id = st.text_input("Candidate ID", value="", placeholder="e.g., cand_xyz123")
    if st.button("Load by ID", use_container_width=True):
        if manual_id.strip():
            st.session_state.selected_candidate_id = manual_id.strip()

# ==============================================================================
# Resolve which candidate ID to display
# ==============================================================================
candidate_id_to_load = st.session_state.get("selected_candidate_id", "").strip()

# ==============================================================================
# Main Report View
# ==============================================================================
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

        # Row 2: CV Experience Match — only shown if cv_experience_match is present in report
        cv_match = report.get("cv_experience_match")
        if cv_match:
            st.markdown("### 📄 CV Experience Match")
            st.caption("Extracted from the candidate's uploaded CV — informational only, does not affect dimension scores.")

            # Top metrics row
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

            # Skills present vs missing
            skills_col1, skills_col2 = st.columns(2)
            with skills_col1:
                st.success("#### ✅ Required Skills Present")
                present = cv_match.get("required_skills_present", [])
                if present:
                    for skill in present:
                        st.markdown(f"* {skill}")
                else:
                    st.markdown("*None of the required skills were found in the CV.*")

            with skills_col2:
                st.error("#### ❌ Required Skills Missing")
                missing = cv_match.get("required_skills_missing", [])
                if missing:
                    for skill in missing:
                        st.markdown(f"* {skill}")
                else:
                    st.markdown("*All required skills are present — no gaps detected.*")

            st.markdown("---")
        st.markdown("### 🎛️ Multi-Agent Dimensional Analysis Breakdown")
        dim_col1, dim_col2 = st.columns(2)

        with dim_col1:
            with st.expander(f"🗣️ Communication Dimensions - Score: {report['communication']['score']}/5", expanded=True):
                st.info(f"**Justification:** {report['communication']['justification']}")
                if report['communication'].get('evidence'):
                    st.caption(f"**Evidence:** *\"{report['communication']['evidence']}\"*")

            with st.expander(f"🧩 Problem Solving Dynamics - Score: {report['problem_solving']['score']}/5", expanded=True):
                st.info(f"**Justification:** {report['problem_solving']['justification']}")
                if report['problem_solving'].get('evidence'):
                    st.caption(f"**Evidence:** *\"{report['problem_solving']['evidence']}\"*")

        with dim_col2:
            with st.expander(f"💻 Technical Depth Evaluation - Overall Score: {report['technical_depth']['overall_score']}/5", expanded=True):
                st.info(f"**Overall Justification:** {report['technical_depth']['overall_justification']}")
                st.markdown("#### 📐 Dimension Breakdown")
                for dim in report['technical_depth']['dimensions']:
                    if dim.get('not_assessed'):
                        st.markdown(f"**⚪ {dim['dimension_name'].replace('_', ' ').title()}** — Not Assessed")
                        st.caption(f"{dim['justification']}")
                    else:
                        score = dim['score']
                        indicator = "🟢" if score >= 4 else "🟡" if score == 3 else "🔴"
                        st.markdown(f"**{indicator} {dim['dimension_name'].replace('_', ' ').title()}** — {score}/5")
                        st.caption(f"{dim['justification']}")
                        if dim.get('evidence'):
                            st.caption(f"*Evidence: \"{dim['evidence']}\"*")

            with st.expander(f"🤝 Cultural Alignment Metrics - Score: {report['cultural_alignment']['score']}/5", expanded=True):
                st.info(f"**Justification:** {report['cultural_alignment']['justification']}")
                if report['cultural_alignment'].get('evidence'):
                    st.caption(f"**Evidence:** *\"{report['cultural_alignment']['evidence']}\"*")

        st.markdown("---")

        # ==============================================================================
        # Interviewer Bias Flags Warning Block
        # ==============================================================================
        bias_flags = report.get("interviewer_bias_flags")
        if bias_flags:
            st.markdown("### ⚠️ Interviewer Bias Pre-Screen Alerts")
            st.error(
                f"**{len(bias_flags)} biased interviewer question(s) detected** in the transcript "
                f"pre-screen. These questions may have influenced the candidate's responses. "
                f"Scores have NOT been adjusted — review these flags before committing a hiring decision."
            )
            for flag in bias_flags:
                severity_icon = "🔴" if flag["severity"] == "high" else "🟡"
                with st.expander(
                    f"{severity_icon} [{flag['severity'].upper()}] {flag['bias_category'].replace('_', ' ').title()}",
                    expanded=True
                ):
                    st.markdown(f"**Question:** {flag['question_text']}")
                    st.caption(f"**Rationale:** {flag['rationale']}")
        else:
            st.success("✅ Interviewer Bias Pre-Screen: No biased questions detected in either session transcript.")

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
            "Before committing a hiring decision, you must confirm that you have reviewed "
            "the full evaluation report including all dimension scores, bias flags, and "
            "agent justifications. This acknowledgment is logged against your decision."
        )

        # Track when report was first loaded into session
        load_key = f"report_loaded_at_{candidate_id_to_load}"
        if load_key not in st.session_state:
            from datetime import datetime, timezone
            st.session_state[load_key] = datetime.now(timezone.utc).isoformat()

        # Acknowledgment checkboxes — all three must be checked before form unlocks
        check_dimensions = st.checkbox(
            "✅ I have reviewed all dimension scores and justifications in the technical breakdown."
        )
        check_bias = st.checkbox(
            "✅ I have reviewed the bias pre-screen results and any interviewer bias flags."
        )
        check_responsibility = st.checkbox(
            "✅ I understand this decision is my professional responsibility and is not solely based on the AI recommendation."
        )

        all_acknowledged = check_dimensions and check_bias and check_responsibility

        if not all_acknowledged:
            st.error(
                "⛔ Decision form is locked. Please confirm all three acknowledgments above "
                "to unlock the hiring decision controls."
            )
        else:
            st.success("🔓 Acknowledgments confirmed. You may now commit a hiring decision.")

            with st.form("decision_override_form"):
                selected_decision = st.selectbox(
                    "Update Candidate Status:",
                    options=["Hold", "Hired", "Rejected"]
                )

                st.markdown("---")

                # Show time elapsed between report load and decision commit
                from datetime import datetime, timezone
                loaded_at = st.session_state.get(load_key, "Unknown")
                st.caption(f"📅 Report first loaded at: `{loaded_at}`")
                st.caption(f"⏱️ Decision being committed at: `{datetime.now(timezone.utc).isoformat()}`")

                if st.form_submit_button("Commit Decision to Server", use_container_width=True):
                    commit_time = datetime.now(timezone.utc).isoformat()
                    loaded_time = st.session_state.get(load_key, "Unknown")

                    # Log the oversight audit trail to console
                    import logging
                    oversight_logger = logging.getLogger("HumanOversight")
                    oversight_logger.info(
                        f"HUMAN DECISION COMMITTED | "
                        f"Candidate: {candidate_id_to_load} | "
                        f"Decision: {selected_decision} | "
                        f"Report loaded at: {loaded_time} | "
                        f"Decision committed at: {commit_time} | "
                        f"Acknowledgments: dimensions=True, bias=True, responsibility=True"
                    )

                    if submit_decision(candidate_id_to_load, selected_decision):
                        st.session_state.selected_candidate_id = candidate_id_to_load
                        # Clear the load timestamp so next load gets a fresh timestamp
                        if load_key in st.session_state:
                            del st.session_state[load_key]
else:
    # ==============================================================================
    # Welcome / Empty State
    # ==============================================================================
    st.info("👋 Welcome! Select a candidate from the sidebar or use Manual ID Lookup to load a report.")

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("""
        ### 🔄 Getting Started:
        1. Ensure FastAPI is running on `http://127.0.0.1:8000`
        2. Submit a candidate via `python submit_test.py`
        3. The candidate appears in the sidebar automatically
        4. Click their name to load the full report
        """)
    with col_right:
        st.markdown("### 🛠️ Quick Diagnostics:")
        try:
            health = requests.get(f"{API_BASE_URL}/health", timeout=2).json()
            st.success(f"🟢 FastAPI connected. Status: `{health.get('status')}`")
        except Exception:
            st.error("🔴 FastAPI not reachable. Run `uvicorn api.main:app --reload` first.")