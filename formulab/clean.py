"""Clean the combined measurements and record every change in an issue log.

Nothing is removed silently: each dropped or corrected row gets a line in the log, so
the people who own the data can see what happened and fix it at the source.
"""

from __future__ import annotations

import re

import pandas as pd

MAX_RESIDUAL = 105.0   # above this is physically implausible (noise is a few %)
CODE = re.compile(r"^F-?(\d{3})$")


def normalise_code(raw: str) -> str:
    """'f-104 ' -> 'F-104', 'F102' -> 'F-102'. Unrecognised text is returned upper-cased."""
    text = str(raw).strip().upper()
    m = CODE.match(text)
    return f"F-{m.group(1)}" if m else text


def clean(raw: pd.DataFrame, known_codes: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = raw.copy()
    issues: list[dict] = []

    def log(rows: pd.DataFrame, issue: str, action: str) -> None:
        for _, r in rows.iterrows():
            issues.append({"source": r["source"], "sample_id": r["sample_id"], "issue": issue, "action": action})

    # 1. Formulation codes written in different ways.
    df["formulation"] = df["formulation_raw"].map(normalise_code)
    changed = df[(df["formulation"] != df["formulation_raw"]) & df["formulation"].isin(known_codes)]
    for (source, raw_code, code), g in changed.groupby(["source", "formulation_raw", "formulation"]):
        ids = sorted(g["sample_id"])
        issues.append({"source": source, "sample_id": f"{ids[0]} to {ids[-1]}" if len(ids) > 1 else ids[0],
                       "issue": f"Code written as '{raw_code}' ({len(ids)} rows)",
                       "action": f"Standardised to {code}"})

    unknown = df[~df["formulation"].isin(known_codes)]
    log(unknown, "Unknown formulation code", "Removed; check the code with the team")
    df = df[df["formulation"].isin(known_codes)]

    # 2. Missing values.
    missing = df[df[["temperature_c", "time_days", "residual_pct"]].isna().any(axis=1)]
    log(missing, "Missing value", "Removed; ask the team for the measurement")
    df = df.dropna(subset=["temperature_c", "time_days", "residual_pct"])

    # 3. Exact duplicates (same team, formulation, temperature, day and value).
    key = ["source", "formulation", "temperature_c", "time_days", "residual_pct"]
    dupes = df[df.duplicated(subset=key, keep="first")]
    log(dupes, "Duplicate row", "Removed the copy")
    df = df.drop_duplicates(subset=key, keep="first")

    # 4. Impossible values.
    bad = df[(df["residual_pct"] > MAX_RESIDUAL) | (df["residual_pct"] < 0)]
    log(bad, f"Residual activity outside 0-{MAX_RESIDUAL:.0f}%", "Removed; likely a typing error")
    df = df[(df["residual_pct"] <= MAX_RESIDUAL) & (df["residual_pct"] >= 0)]

    df = df.assign(residual_pct=df["residual_pct"].round(2))
    cols = ["source", "sample_id", "formulation", "temperature_c", "time_days", "residual_pct"]
    clean_df = df[cols].sort_values(["formulation", "temperature_c", "time_days"], ignore_index=True)
    return clean_df, pd.DataFrame(issues, columns=["source", "sample_id", "issue", "action"])
