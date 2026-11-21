"""Tiny client for the FastAPI backend. The dashboard talks to the API only, never to the data files."""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

API = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def call(method: str, path: str, **params: Any) -> dict:
    """Call the API and return the JSON body. Stops the page with a clear message if it is unreachable."""
    try:
        resp = httpx.request(method, f"{API}/api/v1{path}", params=params or None, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        st.error(
            f"Cannot reach the API at {API}. It may still be starting; reload in a few seconds."
        )
    except httpx.HTTPError as exc:
        st.error(f"The API returned an error: {exc}")
    st.stop()


def get(path: str, **params: Any) -> dict:
    return call("GET", path, **{k: v for k, v in params.items() if v is not None})


def data(path: str, **params: Any) -> tuple[str, Any]:
    """GET an enveloped endpoint; returns ``(source, data)``."""
    body = get(path, **params)
    return body["source"], body["data"]
