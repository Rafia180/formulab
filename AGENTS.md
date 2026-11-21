# Notes for AI coding assistants (GitHub Copilot, Claude Code and similar)

This file tells an AI assistant how to work in this repository, so its suggestions fit the project.

- Python 3.10+. Keep functions small and typed. Line length 120 (`ruff check .` must pass).
- Data flows one way: `ingest` -> `clean` -> `db` -> `kinetics` / `figures` -> `app`. Do not query raw files from the app.
- Never drop or change a measurement without adding a row to the issue log in `clean.py`.
- Charts are pure functions in `figures.py`; keep callbacks in `app.py` thin.
- Every new rule or calculation needs a test in `tests/`. Run `python build_db.py && python -m pytest -q` before proposing a change.
- The sample data is fictional. Do not add real company or personal data.
