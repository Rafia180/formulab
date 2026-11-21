"""Start the FormuLab web app.

Run:  python build_db.py   (once, or after the raw data changes)
      python app.py        then open http://127.0.0.1:8050
"""

from pathlib import Path

from formulab.app import create_app

DB = Path(__file__).resolve().parent / "data" / "formulab.db"

if __name__ == "__main__":
    if not DB.exists():
        raise SystemExit("No database yet. Run: python build_db.py")
    create_app(DB).run(debug=False)
