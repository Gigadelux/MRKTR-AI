"""Single entry point: starts the FastAPI app (uvicorn) and the Streamlit dashboard.

uv run main.py            # API on :8000, dashboard on :8501
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys

import uvicorn

from app.backend.app import create_app
from app.backend.core.company import load_company
from app.backend.core.errors import ConfigError
from app.backend.core.logging import setup_logging
from app.backend.core.settings import ROOT, get_settings

log = logging.getLogger("main")

THEME = {
    "base": "dark",
    "backgroundColor": "#000000",
    "secondaryBackgroundColor": "#000000",
    "textColor": "#ffffff",
    "primaryColor": "#9ad7ff",
}


def start_streamlit(api_base_url: str, host: str, port: int) -> subprocess.Popen:
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "streamlit" / "app.py"),
        "--server.address", host,  # local only: the dashboard shows lead data
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--client.toolbarMode", "minimal",
    ]  # fmt: skip
    for key, value in THEME.items():
        cmd += [f"--theme.{key}", value]
    return subprocess.Popen(cmd, cwd=ROOT, env={**os.environ, "API_BASE_URL": api_base_url})


def stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> int:
    settings = get_settings()
    setup_logging(settings)
    try:
        company = load_company(settings)  # fail fast, before anything starts
    except ConfigError as exc:
        print(f"Cannot start: {exc}", file=sys.stderr)
        return 1
    log.info("Starting for %s: API %s, dashboard http://localhost:%s",
             company.name, settings.api_base_url, settings.streamlit_port)  # fmt: skip
    dashboard = start_streamlit(settings.api_base_url, settings.api_host, settings.streamlit_port)
    try:
        uvicorn.run(
            create_app(settings), host=settings.api_host, port=settings.api_port, log_config=None
        )
    finally:
        stop(dashboard)
        log.info("Stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
