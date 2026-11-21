"""Dashboard entry point. Started by main.py; talks to the FastAPI backend only."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import client
import ui

LOGO = Path(__file__).resolve().parents[2] / "assets" / "mrktr_logo.png"

st.set_page_config(
    page_title="Mrktr", page_icon=str(LOGO) if LOGO.is_file() else None, layout="wide"
)
ui.setup_page()

if LOGO.is_file():
    st.logo(str(LOGO), size="large")
with st.sidebar:
    company = client.get("/company")
    st.caption(company["name"])
    if company.get("disclaimer"):
        st.markdown(f'<p class="muted">{company["disclaimer"]}</p>', unsafe_allow_html=True)

pages = [
    st.Page("views/overview.py", title="Overview", default=True),
    st.Page("views/leads.py", title="Leads"),
    st.Page("views/conversations.py", title="Conversations"),
    st.Page("views/safety.py", title="Safety"),
    st.Page("views/approvals.py", title="Approvals"),
    st.Page("views/evals.py", title="Evals"),
    st.Page("views/logs.py", title="Logs"),
    st.Page("views/data.py", title="Data"),
]
st.navigation(pages).run()
