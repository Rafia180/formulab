"""Create fictional stability-study exports from three teams, each in its own format.

The numbers follow first-order decay with temperature dependence (Arrhenius), plus
measurement noise. Some data problems are added on purpose so the cleaning step has
something to find. Nothing here is real Novonesis or enzyme data.

Run:  python generate_sample_data.py
"""

from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

RAW = Path(__file__).resolve().parent / "data" / "raw"
R = 8.314  # J/(mol*K)
TEMPS_C = [25, 30, 37, 45]
DAYS = [0, 7, 14, 28, 56, 84]

# code: (name, type, stabiliser, k at 37 C per day, activation energy kJ/mol, start activity U/g)
FORMULATIONS = {
    "F-101": ("Liquid, glycerol 40%", "Liquid", "Glycerol", 0.0040, 80, 1200),
    "F-102": ("Liquid, sorbitol 30%", "Liquid", "Sorbitol", 0.0060, 75, 1150),
    "F-103": ("Liquid, no stabiliser (control)", "Liquid", "None", 0.0200, 60, 1250),
    "F-104": ("Granulate, coated", "Granulate", "Coating", 0.0020, 95, None),
    "F-105": ("Granulate, uncoated", "Granulate", "None", 0.0050, 85, None),
    "F-106": ("Liquid, glycerol 40% + salt", "Liquid", "Glycerol + salt", 0.0030, 85, 1180),
}


def k_at(code: str, temp_c: float) -> float:
    _, _, _, k37, ea_kj, _ = FORMULATIONS[code]
    t = temp_c + 273.15
    return k37 * math.exp(-ea_kj * 1000 / R * (1 / t - 1 / 310.15))


def residual(code: str, temp_c: float, day: int, rng: random.Random) -> float:
    if day == 0:
        return 100.0
    return 100 * math.exp(-k_at(code, temp_c) * day) * rng.gauss(1, 0.012)


def danish(x: float, digits: int = 1) -> str:
    """Danish Excel exports use a comma as the decimal separator."""
    return f"{x:.{digits}f}".replace(".", ",")


def main(seed: int = 7) -> None:
    rng = random.Random(seed)
    RAW.mkdir(parents=True, exist_ok=True)

    with open(RAW / "formulations.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "name", "type", "stabiliser"])
        for code, (name, typ, stab, *_rest) in FORMULATIONS.items():
            w.writerow([code, name, typ, stab])

    # 1) Liquid Formulation team: semicolon-separated, comma decimals, weeks, absolute activity.
    liquid_rows = []
    n = 1
    for code, spec in FORMULATIONS.items():
        if spec[1] != "Liquid":
            continue
        for temp in TEMPS_C:
            if temp == 45:
                continue  # the Analytics team runs the 45 C samples
            for day in DAYS:
                activity = spec[5] * residual(code, temp, day, rng) / 100
                shown = code.replace("-", "") if (code == "F-102" and temp == 30) else code  # "F102"
                liquid_rows.append([f"LQ-{n:04d}", shown, str(temp), danish(day / 7, 0), danish(activity)])
                n += 1
    liquid_rows.insert(9, list(liquid_rows[8]))       # duplicate row
    liquid_rows.insert(30, list(liquid_rows[29]))     # duplicate row
    liquid_rows[40][4] = ""                           # missing activity
    with open(RAW / "liquid_lab.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Sample ID", "Formulation", "Temp (°C)", "Week", "Activity (U/g)"])
        w.writerows(liquid_rows)

    # 2) Granulation team: Kelvin, days, residual activity already in %, inconsistent codes.
    gran_rows = []
    n = 1
    for code, spec in FORMULATIONS.items():
        if spec[1] != "Granulate":
            continue
        for temp in TEMPS_C:
            for day in DAYS:
                shown = code.lower() + " " if (code == "F-104" and temp == 37) else code
                gran_rows.append([f"GR-{n:04d}", shown, f"{temp + 273.15:.2f}", str(day),
                                  f"{residual(code, temp, day, rng):.1f}"])
                n += 1
    gran_rows[15][4] = "161.0"                        # impossible value (typing error)
    gran_rows.append(["GR-9999", "F-1O3", "310.15", "28", "71.2"])  # letter O instead of zero
    with open(RAW / "granulate_lab.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sample", "form_code", "temperature_K", "days", "residual_pct"])
        w.writerows(gran_rows)

    # 3) Analytics team: 45 C samples for the liquids, start and test dates instead of days.
    an_rows = []
    n = 1
    for code, spec in FORMULATIONS.items():
        if spec[1] != "Liquid":
            continue
        for day in DAYS:
            start = date(2026, 3, 2)
            test = start + timedelta(days=day)
            an_rows.append([f"AN-{n:04d}", code, "45", start.isoformat(), test.isoformat(),
                            f"{residual(code, 45, day, rng):.1f}"])
            n += 1
    an_rows.insert(5, list(an_rows[4]))               # duplicate row
    an_rows[12][5] = ""                               # missing value
    with open(RAW / "analytics_lab.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sample_id", "formulation", "temp_c", "start_date", "test_date", "residual_activity_pct"])
        w.writerows(an_rows)
    print(f"Wrote {len(liquid_rows)} + {len(gran_rows)} + {len(an_rows)} rows to {RAW}")


if __name__ == "__main__":
    main()
