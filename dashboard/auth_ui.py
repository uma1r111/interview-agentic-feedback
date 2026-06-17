"""
Login screen and session management for the AI Interview Evaluation Dashboard.

Visual identity follows Imperium Dynamics branding: deep royal purple primary
color, white surfaces, soft purple gradients, clean sans-serif typography,
and rounded pill-style buttons.

This module is imported by dashboard/app.py and gates all dashboard content
behind a successful login.
"""
import os
import sys

import streamlit as st

# Ensure the project root (one level above dashboard/) is importable so that
# `from services.auth import ...` resolves regardless of how Streamlit's
# sys.path setup varies across versions/launch methods. This mirrors the
# same defensive pattern already used in tests/test_cv_parsing_agent.py and
# tests/test_pdf_extractor.py for the identical reason.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from services.auth import authenticate, init_users_table

# ==============================================================================
# Imperium Dynamics Brand Tokens
# ==============================================================================

IMPERIUM_PURPLE      = "#5B2A8E"   # primary brand purple
IMPERIUM_PURPLE_DARK = "#3D1B63"   # deep accent / gradient end
IMPERIUM_PURPLE_LIGHT = "#8B5FBF"  # lighter accent for hover states
IMPERIUM_LAVENDER    = "#F3EEFA"   # soft background tint
IMPERIUM_WHITE       = "#FFFFFF"
IMPERIUM_TEXT_DARK   = "#1F1530"
IMPERIUM_TEXT_MUTED  = "#6B6178"


def inject_login_styles():
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif;
        }}

        /* Hide default Streamlit chrome on the login screen */
        #MainMenu, header, footer {{ visibility: hidden; }}

        .stApp {{
            background: linear-gradient(135deg, {IMPERIUM_LAVENDER} 0%, #FFFFFF 55%, {IMPERIUM_LAVENDER} 100%);
        }}

        /* CRITICAL: Wipe out Streamlit's automatic block borders and internal forms completely */
        div[data-testid="stForm"], 
        div[data-testid="stVerticalBlockBorderWrapper"],
        .stForm {{
            max-width: 430px !important;
            margin: 0 auto !important;
            background: {IMPERIUM_WHITE} !important;
            border-radius: 20px !important;
            padding: 40px 36px !important;
            box-shadow: 0 12px 40px rgba(91, 42, 142, 0.12), 0 2px 8px rgba(0,0,0,0.04) !important;
            border: 1px solid rgba(91, 42, 142, 0.08) !important;
        }}

        /* Remove the inner secondary border wrap lines injected by Streamlit core */
        div[data-testid="stForm"] > div,
        div[data-testid="stVerticalBlockBorderWrapper"] > div {{
            padding: 0 !important;
            background: transparent !important;
            border: none !important;
        }}

        .login-header-zone {{
            max-width: 430px;
            margin: 8vh auto 1vh auto;
            text-align: center;
        }}

        .login-logo-mark {{
            width: 56px;
            height: 56px;
            border-radius: 16px;
            background: linear-gradient(135deg, {IMPERIUM_PURPLE} 0%, {IMPERIUM_PURPLE_DARK} 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 20px auto;
            box-shadow: 0 8px 24px rgba(91, 42, 142, 0.25);
        }}

        .login-title {{
            font-size: 1.65rem;
            font-weight: 800;
            color: {IMPERIUM_TEXT_DARK};
            margin-bottom: 6px;
            letter-spacing: -0.02em;
        }}

        .login-subtitle {{
            font-size: 0.9rem;
            color: {IMPERIUM_TEXT_MUTED};
            margin-bottom: 20px;
            font-weight: 500;
        }}

        .login-brand-footer {{
            text-align: center;
            margin-top: 32px;
            font-size: 0.75rem;
            color: {IMPERIUM_TEXT_MUTED};
            letter-spacing: 0.06em;
            text-transform: uppercase;
            font-weight: 600;
        }}

        /* Input field refinements */
        .stTextInput > div > div > input {{
            border-radius: 10px !important;
            border: 1.5px solid #E5DEF0 !important;
            padding: 11px 14px !important;
            font-size: 0.95rem !important;
            background: #FAF8FD !important;
            color: {IMPERIUM_TEXT_DARK} !important;
        }}
        
        .stTextInput > div > div > input:focus {{
            border-color: {IMPERIUM_PURPLE} !important;
            box-shadow: 0 0 0 3px rgba(91, 42, 142, 0.12) !important;
        }}

        .stTextInput label p {{
            font-weight: 600 !important;
            color: #4A3E56 !important;
            font-size: 0.9rem !important;
            margin-bottom: 2px !important;
        }}

        /* Premium submit action button updates */
        div.stButton > button {{
            width: 100% !important;
            border-radius: 999px !important;
            background: linear-gradient(135deg, {IMPERIUM_PURPLE} 0%, {IMPERIUM_PURPLE_DARK} 100%) !important;
            color: white !important;
            border: none !important;
            padding: 12px 0 !important;
            font-weight: 700 !important;
            font-size: 0.95rem !important;
            letter-spacing: 0.01em !important;
            transition: all 0.15s ease !important;
            box-shadow: 0 6px 18px rgba(91, 42, 142, 0.28) !important;
            margin-top: 16px !important;
        }}
        
        div.stButton > button:hover {{
            transform: translateY(-1px) !important;
            box-shadow: 0 8px 22px rgba(91, 42, 142, 0.38) !important;
            background: linear-gradient(135deg, {IMPERIUM_PURPLE_LIGHT} 0%, {IMPERIUM_PURPLE} 100%) !important;
            color: white !important;
        }}
        
        div.stButton > button:active {{
            transform: translateY(0px) !important;
        }}

        .role-pill {{
            display: inline-block;
            padding: 3px 12px;
            border-radius: 999px;
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }}
        .role-pill-hr {{
            background: #EDE4F8;
            color: {IMPERIUM_PURPLE_DARK};
        }}
        .role-pill-hm {{
            background: #E8F0FE;
            color: #1A4FB8;
        }}
    </style>
    """, unsafe_allow_html=True)


def inject_app_chrome_styles():
    """Styles applied across the app once logged in — top bar, badges, etc."""
    st.markdown(f"""
    <style>
        .topbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 0 18px 0;
            border-bottom: 1px solid #EDE4F8;
            margin-bottom: 20px;
        }}
        .topbar-brand {{
            font-size: 1.15rem;
            font-weight: 800;
            color: {IMPERIUM_TEXT_DARK};
            letter-spacing: -0.01em;
        }}
        .topbar-brand-accent {{
            color: {IMPERIUM_PURPLE};
        }}
        .user-chip {{
            background: {IMPERIUM_LAVENDER};
            border-radius: 999px;
            padding: 6px 16px;
            font-size: 0.85rem;
            font-weight: 600;
            color: {IMPERIUM_TEXT_DARK};
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }}
        .decision-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 700;
        }}
        .decision-badge-hired {{ background: #E3F8EC; color: #0F7A3D; }}
        .decision-badge-rejected {{ background: #FDE9E9; color: #B42318; }}
        .decision-badge-hold {{ background: #FFF6E5; color: #92660B; }}
        .decision-meta {{
            font-size: 0.72rem;
            color: {IMPERIUM_TEXT_MUTED};
            margin-top: 2px;
        }}
    </style>
    """, unsafe_allow_html=True)


def render_login_screen():
    """Renders the centered Imperium-branded login card. Sets session state on success."""
    inject_login_styles()

    st.markdown('<div class="login-header-zone">', unsafe_allow_html=True)
    st.markdown('<div class="login-logo-mark">', unsafe_allow_html=True)
    st.markdown(
        """<svg width="28" height="28" viewBox="0 0 24 24" fill="none">
        <path d="M12 2L2 7l10 5 10-5-10-5z" fill="white" opacity="0.95"/>
        <path d="M2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" stroke-width="1.6" fill="none" opacity="0.85"/>
        </svg>""",
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-title">AI Interview Evaluation</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-subtitle">Sign in to continue to your dashboard</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Standard layout grid mapping
    _, col_center, _ = st.columns([1.1, 1.8, 1.1])

    with col_center:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email Address", placeholder="name@imperiumdynamics.com")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Sign In")

            if submitted:
                if not email or not password:
                    st.error("Please enter both email and password.")
                else:
                    user = authenticate(email.strip(), password)
                    if user:
                        st.session_state.auth_user = user
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")

        st.markdown(
            '<div class="login-brand-footer">Imperium Dynamics</div>',
            unsafe_allow_html=True
        )


def require_login() -> dict:
    """
    Call this at the very top of dashboard/app.py.
    Blocks all further execution until a valid login exists in session state.
    Returns the logged-in user dict ({email, role, display_name, ...}) once authenticated.
    """
    if "users_table_ready" not in st.session_state:
        init_users_table()
        st.session_state.users_table_ready = True

    if "auth_user" not in st.session_state or st.session_state.auth_user is None:
        render_login_screen()
        st.stop()

    return st.session_state.auth_user


def render_topbar(user: dict):
    """Renders the post-login top bar with brand mark, role pill, and logout."""
    inject_app_chrome_styles()

    role_label = "Hiring Manager" if user["role"] == "hiring_manager" else "HR"
    role_pill_class = "role-pill-hm" if user["role"] == "hiring_manager" else "role-pill-hr"

    col_brand, col_user, col_logout = st.columns([5, 2, 1])
    with col_brand:
        st.markdown(
            '<div class="topbar-brand">AI Interview <span class="topbar-brand-accent">Evaluation</span></div>',
            unsafe_allow_html=True
        )
    with col_user:
        st.markdown(
            f'<div class="user-chip">{user["display_name"]} '
            f'<span class="role-pill {role_pill_class}">{role_label}</span></div>',
            unsafe_allow_html=True
        )
    with col_logout:
        if st.button("Log out", key="logout_btn", use_container_width=True):
            st.session_state.auth_user = None
            st.rerun()

    st.markdown('<hr style="border-color:#EDE4F8;margin-top:8px;margin-bottom:8px;">', unsafe_allow_html=True)