"""Look and feel: pitch-black theme, Ubuntu font, shared helpers."""

from __future__ import annotations

import streamlit as st

ACCENT = "#9ad7ff"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Ubuntu:wght@400;500&display=swap');

html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
[data-testid="stSidebar"], [data-testid="stSidebarContent"], [data-testid="stBottom"] > div {
    background: #000000 !important;
}
.stApp, .stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp td, .stApp th, .stApp button, .stApp input, .stApp textarea, .stApp [data-baseweb="select"],
.stApp [data-testid="stMetricValue"], .stApp [data-testid="stMetricLabel"], .stApp code {
    font-family: 'Ubuntu', system-ui, sans-serif !important;
}
#MainMenu, footer, [data-testid="stDeployButton"] { display: none !important; }
/* keep the toolbar: it holds the button that reopens a collapsed sidebar */
[data-testid="stToolbar"] { background: transparent !important; }
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"] { opacity: 1 !important; visibility: visible !important; }
[data-testid="stExpandSidebarButton"] *, [data-testid="stSidebarCollapseButton"] * { color: #ffffff !important; }
[data-testid="stSidebarHeader"] img, [data-testid="stLogo"] { height: 5.5rem !important; width: auto !important; }
[data-testid="stHeader"] { height: 2.2rem; }
[data-testid="stSidebar"] { border-right: 1px solid #141414; }
.block-container { max-width: 1100px; padding-top: 1.5rem; }
h1 { font-weight: 500; letter-spacing: 0.01em; }
h2, h3 { font-weight: 500; }

/* cards and metrics */
[data-testid="stMetric"] {
    background: #050505; border: 1px solid #1a1a1a; border-radius: 12px; padding: 0.9rem 1rem;
}
[data-testid="stMetricValue"] { color: #ffffff; }
[data-testid="stMetricLabel"] p { color: #8a8a8a; }
[data-testid="stExpander"], [data-testid="stDataFrame"], [data-testid="stChatMessage"] {
    border: 1px solid #1a1a1a; border-radius: 12px; background: #050505;
}
.stButton > button { background: #000; color: #fff; border: 1px solid #333; border-radius: 10px; }
.stButton > button:hover { border-color: __ACCENT__; color: __ACCENT__; }

/* banners */
.banner { border: 1px solid #2a2a2a; border-radius: 10px; padding: 0.55rem 0.9rem; margin: 0 0 1rem 0;
          font-size: 0.9rem; color: #cfcfcf; background: #050505; }
.banner b { color: __ACCENT__; letter-spacing: 0.08em; }
.muted { color: #8a8a8a; font-size: 0.9rem; }
</style>
""".replace("__ACCENT__", ACCENT)


def setup_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def banner(source: str) -> None:
    """Say plainly whether the numbers on the page are fictional or missing."""
    if source == "mock":
        st.markdown(
            '<div class="banner"><b>MOCK DATA</b> &nbsp;Everything below is fictional, made to preview '
            "the dashboard. Remove it on the Data page.</div>",
            unsafe_allow_html=True,
        )
    elif source == "empty":
        st.markdown(
            '<div class="banner"><b>NO DATA YET</b> &nbsp;Open the Data page to load mock data, '
            "or connect the database.</div>",
            unsafe_allow_html=True,
        )


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"
