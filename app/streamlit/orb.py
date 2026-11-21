"""Render the orb component: reads orb.html and inlines three.min.js so it needs no network."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

HERE = Path(__file__).parent / "components"
SCRIPT_TAG = '<script src="three.min.js"></script>'


def orb_html() -> str:
    html = (HERE / "orb.html").read_text(encoding="utf-8")
    three = (HERE / "three.min.js").read_text(encoding="utf-8")
    assert SCRIPT_TAG in html, "orb.html must load three.min.js with the exact tag expected here"
    return html.replace(SCRIPT_TAG, f"<script>{three}</script>")


def render_orb(height: int = 460) -> None:
    st.iframe(orb_html(), height=height)  # our own trusted HTML, never user input
