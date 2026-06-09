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
    try:
        response = requests.get(f"{API_BASE_URL}/candidates", timeout=3)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.ConnectionError:
        pass
    return []

def fetch_report(candidate_id: str):
    try:
        response = requests.get(f"{API_BASE_URL}/candidates/{candidate_id}/report")
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
    try:
        response = requests.patch(
            f"{API_BASE_URL}/candidates/{candidate_id}/decision",
            json={"decision": decision}
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

        with st.form("decision_override_form"):
            selected_decision = st.selectbox(
                "Update Candidate Status:",
                options=["Hold", "Hired", "Rejected"]
            )
            if st.form_submit_button("Commit Decision to Server", use_container_width=True):
                if submit_decision(candidate_id_to_load, selected_decision):
                    st.session_state.selected_candidate_id = candidate_id_to_load

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