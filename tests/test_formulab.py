"""Tests for FormuLab. Run with:  python -m pytest -q"""

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from formulab import db, figures, kinetics
from formulab.app import create_app, shelf_table
from formulab.clean import clean, normalise_code
from formulab.ingest import read_granulate, read_liquid
from formulab.pipeline import build

ROOT = Path(__file__).resolve().parents[1]
KNOWN = {"F-101", "F-102"}


def raw(rows):
    cols = ["source", "sample_id", "formulation_raw", "temperature_c", "time_days", "residual_pct"]
    return pd.DataFrame(rows, columns=cols)


# --- cleaning ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [("F-101", "F-101"), ("f-101 ", "F-101"), ("F101", "F-101"),
                                            ("F-1O1", "F-1O1")])
def test_normalise_code(text, expected):
    assert normalise_code(text) == expected


def test_clean_logs_every_problem():
    df = raw([
        ("lab", "S1", "F-101", 25, 0, 100.0),
        ("lab", "S2", "f101", 25, 7, 98.0),        # code variant -> fixed
        ("lab", "S3", "F-101", 25, 7, 98.0),       # duplicate of S2 once the code is fixed
        ("lab", "S4", "F-101", 25, 14, None),      # missing
        ("lab", "S5", "F-101", 25, 28, 160.0),     # impossible
        ("lab", "S6", "F-1O1", 25, 28, 90.0),      # unknown code
    ])
    out, issues = clean(df, KNOWN)
    assert list(out["sample_id"]) == ["S1", "S2"]
    assert set(issues["issue"].str.split(" ").str[0]) == {"Code", "Duplicate", "Missing", "Residual", "Unknown"}


# --- reading the team formats -------------------------------------------------------------

def test_liquid_reader_handles_danish_decimals_and_weeks(tmp_path):
    f = tmp_path / "liquid_lab.csv"
    f.write_text("Sample ID;Formulation;Temp (°C);Week;Activity (U/g)\n"
                 "A;F-101;25;0;1200,0\nB;F-101;25;2;1080,0\n", encoding="utf-8")
    df = read_liquid(f)
    assert df["time_days"].tolist() == [0, 14]
    assert df["residual_pct"].round(1).tolist() == [100.0, 90.0]


def test_granulate_reader_converts_kelvin(tmp_path):
    f = tmp_path / "granulate_lab.csv"
    f.write_text("sample,form_code,temperature_K,days,residual_pct\nG,F-101,310.15,7,95.5\n")
    assert read_granulate(f)["temperature_c"].iloc[0] == 37.0


# --- kinetics ---------------------------------------------------------------------------

def test_fit_rate_recovers_known_rate():
    t = np.array([0, 7, 14, 28, 56])
    k, r2 = kinetics.fit_rate(t, 100 * np.exp(-0.01 * t))
    assert k == pytest.approx(0.01, rel=1e-9)
    assert r2 == pytest.approx(1.0)


def test_arrhenius_recovers_activation_energy():
    temps = np.array([25, 30, 37, 45])
    ks = 0.004 * np.exp(-80_000 / kinetics.R * (1 / (temps + 273.15) - 1 / 310.15))
    ea, ln_a = kinetics.fit_arrhenius(temps, ks)
    assert ea == pytest.approx(80, rel=1e-6)
    assert kinetics.k_from_arrhenius(ea, ln_a, 37) == pytest.approx(0.004, rel=1e-6)


def test_days_to_threshold():
    assert kinetics.days_to(80, 0.01) == pytest.approx(math.log(1.25) / 0.01)


def test_shelf_life_flags_extrapolation():
    rates = pd.DataFrame({"formulation": ["F-101"] * 3, "temperature_c": [25.0, 37.0, 45.0],
                          "k_per_day": [0.001, 0.004, 0.009], "r2": [0.99] * 3, "points": [6] * 3})
    assert not kinetics.shelf_life(rates, 30)["extrapolated"].iloc[0]
    assert kinetics.shelf_life(rates, 5)["extrapolated"].iloc[0]


# --- database ----------------------------------------------------------------------------

def test_database_round_trip_and_feedback(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    forms = pd.DataFrame({"code": ["F-101"], "name": ["Test"], "type": ["Liquid"], "stabiliser": ["None"]})
    meas = pd.DataFrame({"source": ["lab"], "sample_id": ["S1"], "formulation": ["F-101"],
                         "temperature_c": [25.0], "time_days": [0.0], "residual_pct": [100.0]})
    db.load(conn, forms, meas, pd.DataFrame(columns=["source", "sample_id", "issue", "action"]))
    assert len(db.measurements(conn, ["F-101"], 25.0)) == 1
    assert db.measurements(conn, ["F-101"], 37.0).empty
    with pytest.raises(ValueError):
        db.add_feedback(conn, "General", "   ")
    db.add_feedback(conn, "Stability", "Add a 40 °C option")
    assert db.feedback(conn)["message"].tolist() == ["Add a 40 °C option"]


# --- end to end ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sample_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "formulab.db"
    stats = build(ROOT / "data" / "raw", path)
    return path, stats


def test_sample_pipeline(sample_db):
    _, stats = sample_db
    assert stats["issues"] == 9
    assert stats["clean_rows"] == 141


def test_shelf_life_ranking_on_sample(sample_db):
    path, _ = sample_db
    conn = db.connect(path)
    rates = kinetics.rates(db.measurements(conn))
    table = shelf_table(rates, db.formulations(conn), 25, 80)
    assert table["formulation"].iloc[-1] == "F-103"          # the control without stabiliser is worst
    assert "Uncertain fit" in " ".join(table["note"])        # weak fits are flagged, not hidden


def test_app_builds_and_draws(sample_db):
    path, _ = sample_db
    app = create_app(path)
    ids = {"stability-graph", "shelf-graph", "fb-send", "download-btn"}
    assert ids <= set(_ids(app.layout))
    conn = db.connect(path)
    m = db.measurements(conn, ["F-101"], 37.0)
    fig = figures.stability(m, kinetics.rates(db.measurements(conn)), figures.colour_map(["F-101"]), 37.0)
    assert len(fig.data) == 2                                 # dots + fitted line


def _ids(component):
    if hasattr(component, "id") and component.id:
        yield component.id
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for c in children:
            yield from _ids(c)
    elif children is not None and hasattr(children, "children"):
        yield from _ids(children)
