"""Reusable layout pieces, so every page looks and behaves the same way."""

from __future__ import annotations

import pandas as pd
from dash import html


def kpi(label: str, value: str, note: str = "") -> html.Div:
    return html.Div(className="kpi", children=[
        html.Div(label, className="kpi-label"),
        html.Div(value, className="kpi-value"),
        html.Div(note, className="kpi-note"),
    ])


def card(title: str, *children, subtitle: str = "") -> html.Section:
    head = [html.H2(title)]
    if subtitle:
        head.append(html.P(subtitle, className="subtitle"))
    return html.Section(className="card", children=head + list(children))


def control(label: str, component) -> html.Div:
    return html.Div(className="control", children=[html.Label(label), component])


def table(df: pd.DataFrame, columns: dict[str, str], empty: str = "Nothing to show yet.", table_id: str | None = None) -> html.Div:
    """Render a DataFrame as an HTML table. `columns` maps column name -> header text."""
    if df.empty:
        return html.P(empty, className="empty")
    head = html.Thead(html.Tr([html.Th(text) for text in columns.values()]))
    body = html.Tbody([html.Tr([html.Td(_fmt(row[c])) for c in columns]) for _, row in df.iterrows()])
    props = {"id": table_id} if table_id else {}
    return html.Div(className="table-wrap", children=html.Table([head, body], **props))


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:,.1f}"
    return "" if value is None else str(value)
