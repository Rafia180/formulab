"""The Dash web app: four tabs on top of the SQLite database."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from dash import Dash, Input, Output, State, dcc, html, no_update

from . import components as ui
from . import db, figures, kinetics

LOW_R2 = 0.90  # below this the fitted rate is shown as uncertain
PAGES = ["Stability", "Shelf life", "Data quality", "General"]


def shelf_table(rates: pd.DataFrame, names: pd.DataFrame, storage_c: float, threshold: float) -> pd.DataFrame:
    """Shelf-life prediction plus the notes a scientist needs to judge it."""
    sl = kinetics.shelf_life(rates, storage_c, threshold)
    if sl.empty:
        return sl
    fit = rates.groupby("formulation")["r2"].min().rename("min_r2")
    sl = sl.join(fit, on="formulation").merge(names, left_on="formulation", right_on="code")
    notes = []
    for _, r in sl.iterrows():
        n = []
        if r["extrapolated"]:
            n.append("Outside tested temperatures")
        if r["min_r2"] < LOW_R2:
            n.append(f"Uncertain fit (R² {r['min_r2']:.2f})")
        notes.append("; ".join(n) or "OK")
    return sl.assign(note=notes)


def create_app(db_path: Path | str) -> Dash:
    conn = db.connect(db_path)
    names = db.formulations(conn)
    all_m = db.measurements(conn)
    rates = kinetics.rates(all_m)
    colours = figures.colour_map(names["code"].tolist())
    temps = sorted(all_m["temperature_c"].unique().tolist())
    counts = db.issue_counts(conn)
    best = shelf_table(rates, names, 25, 80)

    app = Dash(__name__, title="FormuLab", assets_folder=str(Path(__file__).resolve().parent.parent / "assets"))

    tab = {"padding": "10px 14px", "fontWeight": 500, "color": "#52606d", "backgroundColor": "#eef1f5",
           "border": "1px solid #e4e7eb"}
    tab_on = {**tab, "color": "#1f2933", "backgroundColor": "#ffffff", "borderTop": "3px solid #0072b2",
              "borderBottom": "none", "fontWeight": 650}
    options = [{"label": f"{r.code}  {r.name}", "value": r.code} for r in names.itertuples()]

    app.layout = html.Div(className="page", children=[
        html.Header(className="header", children=[
            html.H1("FormuLab"),
            html.P("Stability data from three lab teams, cleaned into one model, with shelf-life estimates. "
                   "Fictional sample data."),
        ]),
        html.Div(className="kpis", children=[
            ui.kpi("Formulations", str(len(names)), "in the study"),
            ui.kpi("Clean measurements", str(len(all_m)), "from 3 team exports"),
            ui.kpi("Data issues logged", str(int(counts["issues"].sum()) if len(counts) else 0), "see Data quality"),
            ui.kpi("Longest shelf life at 25 °C", f"{best['months'].iloc[0]:.1f} mo" if len(best) else "n/a",
                   f"{best['formulation'].iloc[0]} to 80% activity" if len(best) else ""),
        ]),
        dcc.Tabs(id="tabs", value="stability", className="tabs", children=[
            dcc.Tab(label="Stability", value="stability", style=tab, selected_style=tab_on, children=[
                ui.card("How fast does activity drop?",
                        html.Div(className="controls", children=[
                            ui.control("Formulations", dcc.Dropdown(id="codes", options=options, multi=True,
                                                                    value=["F-101", "F-103", "F-104"])),
                            ui.control("Storage temperature", dcc.RadioItems(
                                id="temp", options=[{"label": f" {t:g} °C", "value": t} for t in temps],
                                value=37.0, inline=True, className="radio")),
                        ]),
                        dcc.Graph(id="stability-graph", config={"displaylogo": False}),
                        subtitle="Each dot is a measurement. Lines are first-order decay fitted to those dots."),
            ]),
            dcc.Tab(label="Shelf life", value="shelf", style=tab, selected_style=tab_on, children=[
                ui.card("Predicted shelf life",
                        html.Div(className="controls", children=[
                            ui.control("Storage temperature (°C)", dcc.Slider(
                                id="storage", min=5, max=45, step=1, value=25,
                                marks={t: f"{t}" for t in [5, 15, 25, 35, 45]},
                                tooltip={"placement": "bottom", "always_visible": False})),
                            ui.control("Minimum acceptable activity", dcc.RadioItems(
                                id="threshold", options=[{"label": f" {t}%", "value": t} for t in [90, 80, 70]],
                                value=80, inline=True, className="radio")),
                        ]),
                        dcc.Graph(id="shelf-graph", config={"displaylogo": False}),
                        html.Div(id="shelf-table"),
                        subtitle="Rates from the tested temperatures are combined with the Arrhenius equation "
                                 "to predict the rate at the storage temperature you choose."),
            ]),
            dcc.Tab(label="Data quality", value="quality", style=tab, selected_style=tab_on, children=[
                ui.card("What the cleaning step changed",
                        html.P(", ".join(f"{r.source}: {r.issues}" for r in counts.itertuples()) or "No issues.",
                               className="summary"),
                        ui.table(db.issues(conn), {"source": "Team export", "sample_id": "Sample",
                                                   "issue": "Issue", "action": "What happened"}),
                        html.Button("Download clean data (CSV)", id="download-btn", className="button"),
                        dcc.Download(id="download"),
                        subtitle="Nothing is removed silently. Share this list with the teams so they can fix "
                                 "the source files."),
            ]),
            dcc.Tab(label="Feedback", value="feedback", style=tab, selected_style=tab_on, children=[
                ui.card("Tell us what would make this tool more useful",
                        html.Div(className="controls", children=[
                            ui.control("About", dcc.Dropdown(id="fb-page", options=PAGES, value="General",
                                                             clearable=False)),
                        ]),
                        dcc.Textarea(id="fb-message", className="textarea", maxLength=1000,
                                     placeholder="For example: I need to compare two temperatures in one chart."),
                        html.Button("Send feedback", id="fb-send", className="button"),
                        html.Div(id="fb-status", className="status"),
                        html.Div(id="fb-table", children=_feedback_table(conn)),
                        subtitle="Feedback is stored in the database and reviewed when planning the next version."),
            ]),
        ]),
        html.Footer("FormuLab · portfolio project by Rafia Tasnim · fictional data, simplified model",
                    className="footer"),
    ])

    @app.callback(Output("stability-graph", "figure"), Input("codes", "value"), Input("temp", "value"))
    def _stability(codes, temp):
        data = db.measurements(conn, codes or None, temp)
        return figures.stability(data, rates, colours, temp)

    @app.callback(Output("shelf-graph", "figure"), Output("shelf-table", "children"),
                  Input("storage", "value"), Input("threshold", "value"))
    def _shelf(storage, threshold):
        t = shelf_table(rates, names, storage, threshold)
        table = ui.table(t, {"formulation": "Code", "name": "Formulation", "ea_kj_mol": "Ea (kJ/mol)",
                             "months": "Months", "note": "Note"})
        return figures.shelf_life(t, colours, storage, threshold), table

    @app.callback(Output("download", "data"), Input("download-btn", "n_clicks"), prevent_initial_call=True)
    def _download(_):
        return dcc.send_data_frame(db.measurements(conn).to_csv, "formulab_clean_measurements.csv", index=False)

    @app.callback(Output("fb-status", "children"), Output("fb-table", "children"), Output("fb-message", "value"),
                  Input("fb-send", "n_clicks"), State("fb-page", "value"), State("fb-message", "value"),
                  prevent_initial_call=True)
    def _feedback(_, page, message):
        try:
            db.add_feedback(conn, page, message or "")
        except ValueError:
            return "Please write a message first.", no_update, no_update
        return "Thank you, your feedback was saved.", _feedback_table(conn), ""

    return app


def _feedback_table(conn) -> html.Div:
    return ui.table(db.feedback(conn), {"created_at": "Sent (UTC)", "page": "About", "message": "Message",
                                        "status": "Status"}, empty="No feedback yet.")
