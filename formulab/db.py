"""SQLite storage: a small, explicit data model and the SQL queries the app uses."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS formulation (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL,
    stabiliser  TEXT
);
CREATE TABLE IF NOT EXISTS measurement (
    id            INTEGER PRIMARY KEY,
    source        TEXT NOT NULL,
    sample_id     TEXT NOT NULL,
    formulation   TEXT NOT NULL REFERENCES formulation(code),
    temperature_c REAL NOT NULL,
    time_days     REAL NOT NULL,
    residual_pct  REAL NOT NULL CHECK (residual_pct BETWEEN 0 AND 105)
);
CREATE INDEX IF NOT EXISTS ix_measurement ON measurement (formulation, temperature_c);
CREATE TABLE IF NOT EXISTS data_issue (
    id        INTEGER PRIMARY KEY,
    source    TEXT NOT NULL,
    sample_id TEXT,
    issue     TEXT NOT NULL,
    action    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    id         INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    page       TEXT NOT NULL,
    message    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'New'
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def load(conn: sqlite3.Connection, formulations: pd.DataFrame, measurements: pd.DataFrame, issues: pd.DataFrame) -> None:
    """Replace the study data (feedback is kept)."""
    with conn:
        conn.execute("DELETE FROM measurement")
        conn.execute("DELETE FROM data_issue")
        conn.execute("DELETE FROM formulation")
        conn.executemany("INSERT INTO formulation (code, name, type, stabiliser) VALUES (?, ?, ?, ?)",
                         formulations[["code", "name", "type", "stabiliser"]].itertuples(index=False))
        conn.executemany(
            "INSERT INTO measurement (source, sample_id, formulation, temperature_c, time_days, residual_pct) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            measurements[["source", "sample_id", "formulation", "temperature_c", "time_days", "residual_pct"]]
            .itertuples(index=False))
        conn.executemany("INSERT INTO data_issue (source, sample_id, issue, action) VALUES (?, ?, ?, ?)",
                         issues[["source", "sample_id", "issue", "action"]].itertuples(index=False))


def measurements(conn: sqlite3.Connection, codes: list[str] | None = None, temperature_c: float | None = None) -> pd.DataFrame:
    sql = ("SELECT m.formulation, f.name, m.temperature_c, m.time_days, m.residual_pct, m.source "
           "FROM measurement m JOIN formulation f ON f.code = m.formulation WHERE 1 = 1")
    params: list = []
    if codes:
        sql += f" AND m.formulation IN ({','.join('?' * len(codes))})"
        params += codes
    if temperature_c is not None:
        sql += " AND m.temperature_c = ?"
        params.append(temperature_c)
    sql += " ORDER BY m.formulation, m.temperature_c, m.time_days"
    return pd.read_sql_query(sql, conn, params=params)


def formulations(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query("SELECT code, name, type, stabiliser FROM formulation ORDER BY code", conn)


def issues(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query("SELECT source, sample_id, issue, action FROM data_issue ORDER BY source, sample_id", conn)


def issue_counts(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT source, COUNT(*) AS issues FROM data_issue GROUP BY source ORDER BY issues DESC", conn)


def add_feedback(conn: sqlite3.Connection, page: str, message: str) -> None:
    message = message.strip()
    if not message:
        raise ValueError("Feedback message is empty")
    with conn:
        conn.execute("INSERT INTO feedback (created_at, page, message) VALUES (?, ?, ?)",
                     (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), page, message[:1000]))


def feedback(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query("SELECT created_at, page, message, status FROM feedback ORDER BY id DESC", conn)
