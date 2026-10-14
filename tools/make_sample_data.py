"""Génère un fichier Excel d'exemple de points XYZ pour tester l'application."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def make_points(count: int = 600, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x = rng.uniform(0, 250, count)
    y = rng.uniform(0, 180, count)
    z = (
        120
        + 12 * np.exp(-(((x - 70) ** 2 + (y - 60) ** 2) / 3500))
        + 8 * np.exp(-(((x - 180) ** 2 + (y - 120) ** 2) / 2600))
        + 0.03 * x
        - 0.02 * y
        + rng.normal(0, 0.6, count)
    )
    return pd.DataFrame({"X": x.round(3), "Y": y.round(3), "Z": z.round(3)})


def main() -> Path:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    frame = make_points()
    xlsx_path = SAMPLE_DIR / "points_xyz_exemple.xlsx"
    frame.to_excel(xlsx_path, index=False, sheet_name="Points")
    csv_path = SAMPLE_DIR / "points_xyz_exemple.csv"
    frame.to_csv(csv_path, index=False, sep=";")
    print(f"Fichier créé : {xlsx_path} ({len(frame)} points)")
    print(f"Fichier créé : {csv_path} ({len(frame)} points)")
    return xlsx_path


if __name__ == "__main__":
    main()
