"""Raw exports in, clean SQLite database out."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import db
from .clean import clean
from .ingest import read_all


def build(raw_dir: Path, db_path: Path) -> dict:
    formulations = pd.read_csv(raw_dir / "formulations.csv", dtype=str)
    raw = read_all(raw_dir)
    measurements, issues = clean(raw, set(formulations["code"]))
    conn = db.connect(db_path)
    db.load(conn, formulations, measurements, issues)
    conn.close()
    return {"raw_rows": len(raw), "clean_rows": len(measurements), "issues": len(issues),
            "formulations": len(formulations)}
