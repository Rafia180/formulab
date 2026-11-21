# How work is done in this repository

1. **Start from an issue.** Each change begins as an issue (feature request or bug report) that says who needs it and how we will know it works.
2. **One branch per issue**, named by type: `feature/<short-name>`, `fix/<short-name>`, `docs/<short-name>`.
3. **Small commits** with messages that say what and why, e.g. `Add Kelvin conversion for granulate exports`.
4. **Open a pull request** into `main` using the template. CI must pass (lint, database build, tests).
5. **Review, then merge.** Delete the branch after merging.

## Project layout

| Folder | What lives there |
| --- | --- |
| `formulab/ingest.py` | One reader per team export, all returning the same columns |
| `formulab/clean.py` | Cleaning rules and the issue log |
| `formulab/db.py` | SQLite schema and the SQL queries the app uses |
| `formulab/kinetics.py` | Decay rates, Arrhenius fit and shelf-life prediction |
| `formulab/components.py` | Reusable layout pieces (cards, KPIs, tables) |
| `formulab/figures.py` | Chart builders (pure functions, easy to test) |
| `formulab/app.py` | The Dash app: layout and callbacks |
| `tests/` | pytest tests, run in CI on every push and pull request |
