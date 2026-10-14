"""Test de démarrage de l'interface CustomTkinter (s'auto-ferme)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import MK3DApp
from tools.make_sample_data import main as make_sample


def main() -> int:
    xlsx = make_sample()
    app = MK3DApp()
    print("[OK] Fenetre creee, widgets initialises.")

    app._load_file(xlsx)
    assert app.data is not None and app.data.size > 0
    print(f"[OK] Donnees chargees dans l'UI : {app.data.size} points")

    app.after(600, app.on_generate)

    def finish() -> None:
        print(f"[OK] Figures affichees dans la galerie : {len(app.figures)}")
        app.destroy()

    app.after(10000, finish)
    app.mainloop()
    print("SUCCES GUI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
