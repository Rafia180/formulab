"""Read each team's export and convert it to one shared format.

Every reader returns the same columns, so the rest of the tool does not need to know
where a measurement came from:

    source, sample_id, formulation_raw, temperature_c, time_days, residual_pct
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMNS = ["source", "sample_id", "formulation_raw", "temperature_c", "time_days", "residual_pct"]


def _number(series: pd.Series) -> pd.Series:
    """Turn text such as '1 234,5' or '' into numbers (NaN when empty)."""
    text = series.astype("string").str.strip().str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(text.replace("", pd.NA), errors="coerce")


def read_liquid(path: Path) -> pd.DataFrame:
    """Liquid Formulation team: ';' separated, comma decimals, weeks, absolute activity (U/g)."""
    df = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False)
    out = pd.DataFrame({
        "source": "liquid_lab",
        "sample_id": df["Sample ID"],
        "formulation_raw": df["Formulation"],
        "temperature_c": _number(df["Temp (°C)"]),
        "time_days": _number(df["Week"]) * 7,
        "activity": _number(df["Activity (U/g)"]),
    })
    # Residual activity = activity / activity at day 0 for the same formulation and temperature.
    start = (out[out["time_days"] == 0]
             .groupby(["formulation_raw", "temperature_c"])["activity"].first()
             .rename("start_activity"))
    out = out.join(start, on=["formulation_raw", "temperature_c"])
    out["residual_pct"] = out["activity"] / out["start_activity"] * 100
    return out[COLUMNS]


def read_granulate(path: Path) -> pd.DataFrame:
    """Granulation team: temperature in Kelvin, days, residual activity already in %."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return pd.DataFrame({
        "source": "granulate_lab",
        "sample_id": df["sample"],
        "formulation_raw": df["form_code"],
        "temperature_c": (_number(df["temperature_K"]) - 273.15).round(1),
        "time_days": _number(df["days"]),
        "residual_pct": _number(df["residual_pct"]),
    })[COLUMNS]


def read_analytics(path: Path) -> pd.DataFrame:
    """Analytics team: start and test dates instead of a day count."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    days = (pd.to_datetime(df["test_date"]) - pd.to_datetime(df["start_date"])).dt.days
    return pd.DataFrame({
        "source": "analytics_lab",
        "sample_id": df["sample_id"],
        "formulation_raw": df["formulation"],
        "temperature_c": _number(df["temp_c"]),
        "time_days": days.astype(float),
        "residual_pct": _number(df["residual_activity_pct"]),
    })[COLUMNS]


READERS = {
    "liquid_lab.csv": read_liquid,
    "granulate_lab.csv": read_granulate,
    "analytics_lab.csv": read_analytics,
}


def read_all(raw_dir: Path) -> pd.DataFrame:
    frames = [reader(raw_dir / name) for name, reader in READERS.items() if (raw_dir / name).exists()]
    return pd.concat(frames, ignore_index=True)
