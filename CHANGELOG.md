# Changelog

_Last updated: 2026-11-20_

All notable changes to this project are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

Add one line per meaningful change under `[Unreleased]`. Security-relevant changes are also noted in `SECURITY.md`.

## [Unreleased]

### Added
- 2026-11-21: `crm.company_description` (what the lead's company does) in `SCHEMA.sql`, the models, the mock data and the Leads page.
- 2026-11-20: `requirements.txt` (runtime dependencies, exported from `uv.lock`) for pip users.
- 2026-11-20: `SCHEMA.sql` and `SCHEMA.md`: Supabase schema (funnel tables, `email_drafts`, Braintrust-shaped `eval_*` tables), RLS on every table.
- 2026-11-20: generic knowledge-base collector (`app/backend/services/kb_scraper.py`) driven by `kb_sources` in the company profile.
- 2026-11-20: FastAPI backend (`/api/v1`: health, company, funnel, leads, conversations, masked, approvals, evals, logs, mock data) and `main.py` that starts it with the Streamlit dashboard.
- 2026-11-20: pitch-black Streamlit dashboard with an animated 3D orb (vendored three.js r149, MIT) and pages for overview, leads, conversations, safety, approvals, evals, logs and data.
- 2026-11-20: deletable mock data (`gitignore/temp/mock/`) so the dashboard can be previewed before real data exists.
- 2026-11-20: unit tests in `app/tests/` for the collector, mock data, API, schema and orb component.

### Changed
- 2026-11-21: unified the project name spelling to Mrktr in the docs, code, UI title, API title, package name and User-Agent.
- 2026-11-21: README shows the Mrktr logo (`assets/mrktr_logo.png`).
- 2026-11-20: every doc file now carries a `Last updated` line; LICENSE year set to 2026.
- 2026-11-20: CLAUDE.md now cites `app/tests/`, `SCHEMA.*` and `assets/`.

### Fixed
- 2026-11-21: dashboard sidebar could not be reopened after collapsing (the CSS hid the toolbar that holds the expand button); it is kept visible now.
- 2026-11-21: replaced deprecated `use_container_width` with `width="stretch"` and `st.components.v1.html` with `st.iframe`.

### Security
- 2026-11-20: dashboard and API bind to `127.0.0.1` only; RLS enabled on all tables with no policies.
