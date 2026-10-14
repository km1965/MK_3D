"""Test hors interface : import, figures et rapport."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mk3d.data_loader import load_points
from mk3d.plotting import PlotOptions, generate_all
from mk3d.report import ReportOptions, build_report
from tools.make_sample_data import main as make_sample


def main() -> int:
    xlsx = make_sample()
    print("=" * 60)

    data = load_points(xlsx)
    print(f"[OK] Import : {data.size} points, colonnes X='{data.x_col}' Y='{data.y_col}' Z='{data.z_col}'")
    print(data.statistics().to_string(index=False))
    print("=" * 60)

    out_dir = ROOT / "output" / "_test"
    opts = PlotOptions(title="Test - Nuage de points XYZ", marker_size=18, dpi=120)
    figures = generate_all(data, out_dir, opts)
    for fig in figures:
        size_kb = fig.path.stat().st_size / 1024 if fig.path.exists() else 0
        print(f"[OK] Figure '{fig.key}' -> {fig.path.name} ({size_kb:.0f} Ko)")

    report_path = out_dir / "rapport_test.docx"
    build_report(
        data,
        figures,
        report_path,
        ReportOptions(title="Rapport de test", author="MK_3D", subject="Vérification"),
    )
    print(f"[OK] Rapport -> {report_path} ({report_path.stat().st_size / 1024:.0f} Ko)")
    print("=" * 60)
    print("PIPELINE COMPLET : SUCCES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
