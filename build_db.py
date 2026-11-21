"""Read the raw exports in data/raw, clean them and write data/formulab.db.

Run:  python build_db.py
"""

from pathlib import Path

from formulab.pipeline import build

ROOT = Path(__file__).resolve().parent

if __name__ == "__main__":
    stats = build(ROOT / "data" / "raw", ROOT / "data" / "formulab.db")
    print(f"Read {stats['raw_rows']} rows from 3 team exports")
    print(f"Kept {stats['clean_rows']} clean measurements for {stats['formulations']} formulations")
    print(f"Logged {stats['issues']} data issues (see the Data quality tab)")
