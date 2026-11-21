"""Estimate how fast activity is lost and predict shelf life at a storage temperature.

Model (a common simplification for stability studies):

* First-order decay at each temperature:   residual(t) = 100 * exp(-k * t)
  k is fitted by least squares on ln(residual / 100) = -k * t (line through the origin).
* Temperature dependence (Arrhenius):      ln k = ln A - Ea / (R * T)
  Fitted across the tested temperatures, then used to predict k at a storage temperature.
* Shelf life = days until residual activity falls to a threshold (for example 80%):
  t = ln(100 / threshold) / k

Predictions outside the tested temperature range are extrapolations and are labelled so.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

R = 8.314  # J/(mol*K)
DAYS_PER_MONTH = 30.44
MIN_POINTS = 3


def fit_rate(time_days: np.ndarray, residual_pct: np.ndarray) -> tuple[float, float]:
    """Return (k per day, R squared) for first-order decay through 100% at day 0."""
    t = np.asarray(time_days, dtype=float)
    y = np.log(np.clip(np.asarray(residual_pct, dtype=float), 0.1, None) / 100)
    denom = float((t * t).sum())
    if denom == 0:
        return float("nan"), float("nan")
    k = -float((t * y).sum()) / denom
    pred = -k * t
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return k, r2


def rates(df: pd.DataFrame) -> pd.DataFrame:
    """One fitted rate per formulation and temperature."""
    rows = []
    for (code, temp), g in df.groupby(["formulation", "temperature_c"]):
        if len(g) < MIN_POINTS:
            continue
        k, r2 = fit_rate(g["time_days"].to_numpy(), g["residual_pct"].to_numpy())
        rows.append({"formulation": code, "temperature_c": float(temp), "k_per_day": k, "r2": r2, "points": len(g)})
    return pd.DataFrame(rows)


def fit_arrhenius(temps_c: np.ndarray, ks: np.ndarray) -> tuple[float, float]:
    """Return (Ea in kJ/mol, ln A) from rates measured at several temperatures."""
    x = 1 / (np.asarray(temps_c, dtype=float) + 273.15)
    y = np.log(np.asarray(ks, dtype=float))
    slope, intercept = np.polyfit(x, y, 1)
    return -slope * R / 1000, float(intercept)


def k_from_arrhenius(ea_kj: float, ln_a: float, temp_c: float) -> float:
    return math.exp(ln_a - ea_kj * 1000 / (R * (temp_c + 273.15)))


def days_to(threshold_pct: float, k: float) -> float:
    return math.log(100 / threshold_pct) / k if k > 0 else float("inf")


def shelf_life(rate_table: pd.DataFrame, storage_c: float, threshold_pct: float = 80) -> pd.DataFrame:
    """Predicted months until residual activity reaches the threshold, per formulation."""
    rows = []
    for code, g in rate_table.groupby("formulation"):
        g = g[g["k_per_day"] > 0]
        if g["temperature_c"].nunique() < 2:
            continue
        ea, ln_a = fit_arrhenius(g["temperature_c"].to_numpy(), g["k_per_day"].to_numpy())
        k = k_from_arrhenius(ea, ln_a, storage_c)
        lo, hi = g["temperature_c"].min(), g["temperature_c"].max()
        rows.append({
            "formulation": code,
            "ea_kj_mol": round(ea, 1),
            "k_storage_per_day": k,
            "months": round(days_to(threshold_pct, k) / DAYS_PER_MONTH, 1),
            "temps_tested": len(g),
            "extrapolated": not (lo <= storage_c <= hi),
        })
    return pd.DataFrame(rows).sort_values("months", ascending=False, ignore_index=True)
