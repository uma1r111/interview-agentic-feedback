import streamlit as st
import requests

# Setup page configurations
st.set_page_config(
    page_title="AI Interview Evaluation Dashboard",
    page_icon="💼",
    layout="wide"
)

# API Endpoint Configurations
API_BASE_URL = "http://127.0.0.1:8000"

st.title("💼 AI Interview Feedback - Reviewer Dashboard")
st.subheader("Hiring Manager One-Click Review & Evaluation Suite")
st.markdown("---")

# ==============================================================================
# Helper API Fetch Utilities
# ==============================================================================
def fetch_report(candidate_id: str):
    try:
        response = requests.get(f"{API_BASE_URL}/candidates/{candidate_id}/report")
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            st.warning(f"🔍 Profile Record for ID '{candidate_id}' not found. Please verify the ID or submit your sample candidate payload to the FastAPI backend first.")
        elif response.status_code == 204:
            st.info("⏳ Candidate profile is initializing but the multi-agent report synthesis has not finished processing.")
        else:
            st.error(f"❌ Server error track encountered. Code: {response.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("🔌 Connection Failure: Cannot reach the backend engine. Ensure your FastAPI server is actively running on port 8000.")
    return None

def submit_decision(candidate_id: str, decision: str):
    try:
        payload = {"decision": decision}
        response = requests.patch(f"{API_BASE_URL}/candidates/{candidate_id}/decision", json=payload)
        if response.status_code == 200:
            st.success(f"✅ Status updated! Candidate locked to status: '{decision}'")
            return True
        else:
            st.error(f"❌ Failed to submit decision change: {response.json().get('detail')}")
    except Exception as e:
        st.error(f"💥 Error processing data transaction: {str(e)}")
    return False

# ==============================================================================
# Sidebar Management Pane
# ==============================================================================
with st.sidebar:
    st.header("Search & Filters")
    st.markdown("Enter a compiled candidate ID from your API tracking records to audit performance narratives.")
    candidate_id_input = st.text_input("Active Candidate ID", value="", placeholder="e.g., cand_xyz123")
    fetch_btn = st.button("Load Assessment Profile", use_container_width=True)

# ==============================================================================
# Main Screen Interface Route Tree
# ==============================================================================
# Explicitly check if the user triggered a search or provided an ID
if fetch_btn and candidate_id_input.strip() != "":
    report = fetch_report(candidate_id_input.strip())
    
    if report:
        # Row 1: Profile Header Metrics Block
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
            st.metric(label="Programming Q1 Correctness Score", value=f"{report['programming_q1_score']} / 5")
        with code_col2:
            st.metric(label="Programming Q2 Correctness Score", value=f"{report['programming_q2_score']} / 5")

        st.markdown("---")
        
        # Row 2: Multi-Agent Evaluation Cards
        st.markdown("### 🎛️ Multi-Agent Dimensional Analysis Breakdown")
        dim_col1, dim_col2 = st.columns(2)
        with dim_col1:
            with st.expander(f"🗣️ Communication Dimensions - Score: {report['communication']['score']}/5", expanded=True):
                st.info(f"**Justification:** {report['communication']['justification']}")
                st.caption(f"**Transcript Evidence:** *\"{report['communication']['evidence']}\"*")
                
            with st.expander(f"🧩 Problem Solving Dynamics - Score: {report['problem_solving']['score']}/5", expanded=True):
                st.info(f"**Justification:** {report['problem_solving']['justification']}")
                st.caption(f"**Transcript Evidence:** *\"{report['problem_solving']['evidence']}\"*")

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
                st.caption(f"**Transcript Evidence:** *\"{report['cultural_alignment']['evidence']}\"*")

        st.markdown("---")
        
        # Row 3: Comprehensive Bullet Synthesis
        st.markdown("### 🧠 AI Core Synthesis Summaries")
        synth_col1, synth_col2 = st.columns(2)
        with synth_col1:
            st.success("#### 📈 Extracted Strengths Core Signals")
            for bullet in report["strengths"]:
                st.markdown(f"* {bullet}")
        with synth_col2:
            st.error("#### ⚠️ Critical Concerns / Performance Risks")
            for bullet in report["concerns"]:
                st.markdown(f"* {bullet}")
                
        st.markdown("---")

        # Row 4: Executive Decision Form Slat
        st.markdown("### 🏛️ Executive Verification & Human Decision Authorization")
        rec_color_map = {"Strong Yes": "🟢", "Yes": "🔵", "Maybe": "🟡", "No": "🔴"}
        rec_token = report["ai_recommendation"]
        
        st.markdown(f"#### Pipeline AI Recommendation: {rec_color_map.get(rec_token, '⚪')} **{rec_token}**")
        st.markdown(f"**System Rationale Statement:** *{report['ai_justification']}*")
        st.warning(f"Current System State Value: **Hiring Manager Status = {report['hiring_manager_decision']}**")
        
        with st.form("decision_override_form"):
            selected_decision = st.selectbox(
                "Modify Candidate Status Application Outcome Directive:",
                options=["Hold", "Hired", "Rejected"]
            )
            submit_action = st.form_submit_button("Commit Decision to Server Logs", use_container_width=True)
            if submit_action:
                submit_decision(candidate_id_input.strip(), selected_decision)

else:
    # ==============================================================================
    # Welcome / Empty State Landing Guide Block
    # ==============================================================================
    st.info("👋 Welcome! The dashboard is standing by and waiting for data processing signals.")
    
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("""
        ### 🔄 Next Steps to Populating Your Dashboard:
        1. **Ensure Your Stack is Running:** Your FastAPI backend should be running on `http://127.0.0.1:8000`.
        2. **Push a Test Candidate:** Since we are running on an in-memory development dictionary cache database, you need to send a `POST` request to `/candidates` to initialize the data.
        3. **Load the ID:** Once the pipeline completes execution, copy the generated `"candidate_id"` hash from the response, paste it into the sidebar input field on the left, and click **Load Assessment Profile**.
        """)
    with col_right:
        st.markdown("""
        ### 🛠️ Quick Diagnostics Check:
        """)
        try:
            health = requests.get(f"{API_BASE_URL}/health", timeout=2).json()
            st.success(f"🟢 Connected to FastAPI Server Health Endpoint! Status: `{health.get('status')}`")
        except Exception:
            st.error("🔴 Connection to FastAPI server failed! Make sure you run `uvicorn api.main:app --reload` in another terminal pane before analyzing.")