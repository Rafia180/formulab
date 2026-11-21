"""Chart builders. Pure functions: data in, Plotly figure out (easy to test)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# Colour-blind-safe categorical palette (Okabe-Ito), assigned in a fixed order so a
# formulation keeps its colour whatever is selected.
PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"]
FONT = "Inter, Segoe UI, Arial, sans-serif"


def colour_map(codes: list[str]) -> dict[str, str]:
    return {code: PALETTE[i % len(PALETTE)] for i, code in enumerate(sorted(codes))}


def _layout(fig: go.Figure, title: str, x: str, y: str) -> go.Figure:
    fig.update_layout(
        title={"text": title, "x": 0, "font": {"size": 15}},
        font={"family": FONT, "size": 13, "color": "#1f2933"},
        plot_bgcolor="white", paper_bgcolor="white",
        margin={"l": 60, "r": 20, "t": 50, "b": 50},
        legend={"orientation": "h", "y": -0.2},
        hoverlabel={"font_family": FONT},
    )
    fig.update_xaxes(title=x, gridcolor="#e5e7eb", zeroline=False, linecolor="#9aa5b1")
    fig.update_yaxes(title=y, gridcolor="#e5e7eb", zeroline=False, linecolor="#9aa5b1")
    return fig


def stability(measurements: pd.DataFrame, rates: pd.DataFrame, colours: dict[str, str], temperature_c: float) -> go.Figure:
    """Measured residual activity (dots) and the fitted first-order curve (line) per formulation."""
    fig = go.Figure()
    for code, g in measurements.groupby("formulation"):
        colour = colours.get(code, "#52606d")
        fig.add_trace(go.Scatter(
            x=g["time_days"], y=g["residual_pct"], mode="markers", name=code, legendgroup=code,
            marker={"size": 9, "color": colour, "line": {"width": 2, "color": "white"}},
            hovertemplate=f"<b>{code}</b><br>Day %{{x:.0f}}<br>%{{y:.1f}}% residual<extra></extra>",
        ))
        fit = rates[(rates["formulation"] == code) & (rates["temperature_c"] == temperature_c)]
        if not fit.empty:
            k = float(fit["k_per_day"].iloc[0])
            t = np.linspace(0, float(g["time_days"].max()), 50)
            fig.add_trace(go.Scatter(
                x=t, y=100 * np.exp(-k * t), mode="lines", legendgroup=code, showlegend=False,
                line={"width": 2, "color": colour}, hoverinfo="skip",
            ))
    fig = _layout(fig, f"Residual activity at {temperature_c:g} °C",
                  "Days in storage", "Residual activity (%)")
    fig.update_yaxes(range=[0, 105])
    return fig


def shelf_life(table: pd.DataFrame, colours: dict[str, str], storage_c: float, threshold: float) -> go.Figure:
    t = table.sort_values("months")
    fig = go.Figure(go.Bar(
        x=t["months"], y=t["formulation"], orientation="h",
        marker={"color": [colours.get(c, "#52606d") for c in t["formulation"]], "cornerradius": 4},
        text=[f"{m:.1f} months" for m in t["months"]], textposition="outside", cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>%{x:.1f} months<extra></extra>",
    ))
    fig = _layout(fig, f"Months until {threshold:g}% activity, stored at {storage_c:g} °C",
                  "Months", "")
    fig.update_layout(showlegend=False, bargap=0.35)
    fig.update_xaxes(range=[0, float(t["months"].max()) * 1.2 if len(t) else 1])
    return fig
