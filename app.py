"""MK_3D - Application CustomTkinter de génération de figures 3D et de rapports."""

from __future__ import annotations

import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from PIL import Image
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from mk3d import __app_name__, __version__
from mk3d.data_loader import LoadError, XYZData, list_sheets, load_points
from mk3d.plotting import FigureResult, PlotOptions, build_3d_figure, generate_all
from mk3d.report import ReportOptions, build_report

APP_DIR = Path(__file__).resolve().parent
BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else APP_DIR
OUTPUT_DIR = BASE_DIR / "output"


def resource_path(relative: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    return APP_DIR / relative


ICON_PATH = resource_path("assets/mk_mnt_3d.ico")

CMAPS = [
    "viridis", "plasma", "inferno", "magma", "cividis",
    "turbo", "jet", "terrain", "coolwarm", "Spectral_r",
]

APPEARANCE = {
    "Sombre": ("dark", False),
    "Clair": ("light", False),
}


class MK3DApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{__app_name__} v{__version__} - Figures 3D & Rapport Word")
        self.geometry("1320x860")
        self.minsize(1100, 720)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._set_window_icon()

        self.data: XYZData | None = None
        self.figures: list[FigureResult] = []
        self.current_sheet: str | None = None
        self._thumb_refs: list[ctk.CTkImage] = []
        self._interactive_window: ctk.CTkToplevel | None = None
        self._save_path: Path | None = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_sidebar()
        self._build_content()
        self._build_status()
        self._build_menu()
        self._set_status("Prêt. Importez un fichier de points XYZ pour commencer.")

    def _set_window_icon(self) -> None:
        try:
            if ICON_PATH.exists():
                self.iconbitmap(str(ICON_PATH))
        except Exception:  # noqa: BLE001
            pass

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, corner_radius=0, height=64)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header,
            text=f"  {__app_name__}",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=16, pady=(10, 0))

        subtitle = ctk.CTkLabel(
            header,
            text="Génération de figures 3D/2D et de rapports Word à partir de fichiers XYZ",
            font=ctk.CTkFont(size=12),
            text_color=("gray30", "gray70"),
        )
        subtitle.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))

        self.appearance_menu = ctk.CTkOptionMenu(
            header,
            values=list(APPEARANCE.keys()),
            width=110,
            command=self._on_appearance_change,
        )
        self.appearance_menu.set("Sombre")
        self.appearance_menu.grid(row=0, column=1, rowspan=2, padx=16)

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkScrollableFrame(self, width=350, label_text="Panneau de contrôle")
        sidebar.grid(row=1, column=0, sticky="nsw", padx=(10, 6), pady=10)
        sidebar.grid_columnconfigure(0, weight=1)

        self._section_import(sidebar)
        self._section_options(sidebar)
        self._section_actions(sidebar)

    def _section_import(self, parent) -> None:
        box = ctk.CTkFrame(parent)
        box.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(box, text="1. Import des points", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 4)
        )

        self.file_entry = ctk.CTkEntry(box, placeholder_text="Aucun fichier sélectionné")
        self.file_entry.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        self.file_entry.configure(state="disabled")

        ctk.CTkButton(box, text="Importer Excel / CSV", command=self.on_import).grid(
            row=2, column=0, sticky="ew", padx=10, pady=4
        )

        ctk.CTkLabel(box, text="Feuille Excel :").grid(
            row=3, column=0, sticky="w", padx=10, pady=(8, 0)
        )
        self.sheet_menu = ctk.CTkOptionMenu(box, values=["-"], command=self.on_sheet_change)
        self.sheet_menu.grid(row=4, column=0, sticky="ew", padx=10, pady=4)
        self.sheet_menu.configure(state="disabled")

        self.info_label = ctk.CTkLabel(
            box, text="Aucune donnée chargée.", justify="left", anchor="w", wraplength=310
        )
        self.info_label.grid(row=5, column=0, sticky="ew", padx=10, pady=(6, 10))

    def _section_options(self, parent) -> None:
        box = ctk.CTkFrame(parent)
        box.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(box, text="2. Paramètres des figures", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 4)
        )

        ctk.CTkLabel(box, text="Titre des figures :").grid(row=1, column=0, sticky="w", padx=10)
        self.title_entry = ctk.CTkEntry(box)
        self.title_entry.insert(0, "Nuage de points 3D (XYZ)")
        self.title_entry.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 8))

        self.size_value = ctk.CTkLabel(box, text="Taille des points : 20")
        self.size_value.grid(row=3, column=0, sticky="w", padx=10)
        self.size_slider = ctk.CTkSlider(box, from_=2, to=120, number_of_steps=118, command=self._on_size)
        self.size_slider.set(20)
        self.size_slider.grid(row=4, column=0, sticky="ew", padx=10, pady=(2, 8))

        ctk.CTkLabel(box, text="Palette de couleurs :").grid(row=5, column=0, sticky="w", padx=10)
        self.cmap_menu = ctk.CTkOptionMenu(box, values=CMAPS)
        self.cmap_menu.set("viridis")
        self.cmap_menu.grid(row=6, column=0, sticky="ew", padx=10, pady=(2, 8))

        ctk.CTkLabel(box, text="Résolution (dpi) :").grid(row=7, column=0, sticky="w", padx=10)
        self.dpi_menu = ctk.CTkOptionMenu(box, values=["100", "150", "200", "300", "450"])
        self.dpi_menu.set("150")
        self.dpi_menu.grid(row=8, column=0, sticky="ew", padx=10, pady=(2, 8))

        self.grid_switch = ctk.CTkSwitch(box, text="Afficher la grille")
        self.grid_switch.select()
        self.grid_switch.grid(row=9, column=0, sticky="w", padx=10, pady=3)

        self.invert_z_switch = ctk.CTkSwitch(box, text="Inverser l'axe Z")
        self.invert_z_switch.grid(row=10, column=0, sticky="w", padx=10, pady=3)

        self.dark_switch = ctk.CTkSwitch(box, text="Fond sombre des figures")
        self.dark_switch.grid(row=11, column=0, sticky="w", padx=10, pady=3)

        self.link_by_label_var = ctk.BooleanVar(value=False)
        self.link_by_label_switch = ctk.CTkSwitch(
            box,
            text="Lier les points par libellé",
            variable=self.link_by_label_var,
        )
        self.link_by_label_switch.grid(row=12, column=0, sticky="w", padx=10, pady=3)

        self.materialize_talus_var = ctk.BooleanVar(value=False)
        self.materialize_talus_switch = ctk.CTkSwitch(
            box,
            text="Matérialiser les talus (polygones fermés)",
            variable=self.materialize_talus_var,
        )
        self.materialize_talus_switch.grid(row=13, column=0, sticky="w", padx=10, pady=3)

        self.close_base_var = ctk.BooleanVar(value=False)
        self.close_base_switch = ctk.CTkSwitch(
            box,
            text="Fermer la base (relier les pieds)",
            variable=self.close_base_var,
        )
        self.close_base_switch.grid(row=14, column=0, sticky="w", padx=10, pady=3)

        self.face_fill_var = ctk.BooleanVar(value=True)
        self.face_fill_switch = ctk.CTkSwitch(
            box,
            text="Remplir les faces (semi-transparent)",
            variable=self.face_fill_var,
        )
        self.face_fill_switch.grid(row=15, column=0, sticky="w", padx=10, pady=3)

        self.export2d_switch = ctk.CTkSwitch(box, text="Exporter les projections 2D")
        self.export2d_switch.select()
        self.export2d_switch.grid(row=16, column=0, sticky="w", padx=10, pady=(3, 10))

    def _section_actions(self, parent) -> None:
        box = ctk.CTkFrame(parent)
        box.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(box, text="3. Actions", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 6)
        )

        self.generate_btn = ctk.CTkButton(
            box, text="Générer les figures", height=38, command=self.on_generate
        )
        self.generate_btn.grid(row=1, column=0, sticky="ew", padx=10, pady=4)

        self.preview_btn = ctk.CTkButton(
            box,
            text="Aperçu interactif 3D",
            height=34,
            fg_color="transparent",
            border_width=1,
            command=self.on_preview,
        )
        self.preview_btn.grid(row=2, column=0, sticky="ew", padx=10, pady=4)

        self.report_btn = ctk.CTkButton(
            box,
            text="Générer le rapport Word",
            height=34,
            fg_color="transparent",
            border_width=1,
            command=self.on_report,
        )
        self.report_btn.grid(row=3, column=0, sticky="ew", padx=10, pady=(4, 10))

    def _build_content(self) -> None:
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=1, sticky="nsew", padx=(6, 10), pady=10)

        self.data_tab = self.tabview.add("Données")
        self.figures_tab = self.tabview.add("Figures")
        self.report_tab = self.tabview.add("Rapport")

        self._build_data_tab()
        self._build_figures_tab()
        self._build_report_tab()

    def _build_data_tab(self) -> None:
        self.data_tab.grid_columnconfigure(0, weight=1)
        self.data_tab.grid_rowconfigure(1, weight=1)

        self.stats_box = ctk.CTkTextbox(self.data_tab, height=130, activate_scrollbars=True)
        self.stats_box.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.stats_box.insert("1.0", "Aucune donnée chargée.\n")
        self.stats_box.configure(state="disabled")

        table_frame = ctk.CTkFrame(self.data_tab)
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "MK3D.Treeview",
            background="#2b2b38",
            fieldbackground="#2b2b38",
            foreground="#e8e8f0",
            rowheight=24,
            bordercolor="#3a3a48",
        )
        style.configure(
            "MK3D.Treeview.Heading",
            background="#1f4e79",
            foreground="#ffffff",
            font=("Segoe UI", 9, "bold"),
        )
        style.map("MK3D.Treeview", background=[("selected", "#1f6fb2")])

        self.tree = ttk.Treeview(
            table_frame, columns=["index", "X", "Y", "Z"], show="headings", style="MK3D.Treeview"
        )
        for col, width in (("index", 70), ("X", 150), ("Y", 150), ("Z", 150)):
            self.tree.heading(col, text=col if col != "index" else "N°")
            self.tree.column(col, anchor="center", width=width)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self.table_count = ctk.CTkLabel(self.data_tab, text="0 point(s)")
        self.table_count.grid(row=2, column=0, sticky="w", pady=(6, 0))

    def _build_figures_tab(self) -> None:
        self.figures_tab.grid_columnconfigure(0, weight=1)
        self.figures_tab.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(self.figures_tab)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        toolbar.grid_columnconfigure(0, weight=1)

        self.figures_hint = ctk.CTkLabel(
            toolbar, text="Aucune figure générée.", anchor="w", justify="left"
        )
        self.figures_hint.grid(row=0, column=0, sticky="w", padx=8, pady=6)

        ctk.CTkButton(toolbar, text="Ouvrir le dossier de sortie", width=200, command=self.on_open_output).grid(
            row=0, column=1, padx=8, pady=6
        )

        self.gallery = ctk.CTkScrollableFrame(self.figures_tab, label_text="Galerie des figures")
        self.gallery.grid(row=1, column=0, sticky="nsew")
        self.gallery.grid_columnconfigure((0, 1), weight=1)

    def _build_report_tab(self) -> None:
        self.report_tab.grid_columnconfigure(0, weight=1)

        box = ctk.CTkFrame(self.report_tab)
        box.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(box, text="Titre du rapport :").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 2))
        self.report_title = ctk.CTkEntry(box)
        self.report_title.insert(0, "Rapport d'analyse XYZ")
        self.report_title.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(box, text="Auteur :").grid(row=2, column=0, sticky="w", padx=12)
        self.report_author = ctk.CTkEntry(box)
        self.report_author.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(box, text="Objet / sous-titre :").grid(row=4, column=0, sticky="w", padx=12)
        self.report_subject = ctk.CTkEntry(box)
        self.report_subject.insert(0, "Visualisation 3D de données de points")
        self.report_subject.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 8))

        self.report_table_switch = ctk.CTkSwitch(box, text="Inclure le tableau des statistiques")
        self.report_table_switch.select()
        self.report_table_switch.grid(row=6, column=0, sticky="w", padx=12, pady=(0, 12))

        ctk.CTkButton(
            self.report_tab, text="Générer et enregistrer le rapport Word", height=40, command=self.on_report
        ).grid(row=1, column=0, sticky="ew")

        self.report_log = ctk.CTkTextbox(self.report_tab, height=180)
        self.report_log.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.report_log.insert("1.0", "Le rapport intègrera toutes les figures générées.\n")
        self.report_log.configure(state="disabled")

        ctk.CTkButton(
            self.report_tab,
            text="Ouvrir le dossier de sortie",
            fg_color="transparent",
            border_width=1,
            command=self.on_open_output,
        ).grid(row=3, column=0, sticky="ew", pady=8)

    def _build_status(self) -> None:
        bar = ctk.CTkFrame(self, height=46, corner_radius=0)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(bar, text="", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", padx=14, pady=6)

        self.progress = ctk.CTkProgressBar(bar, width=240)
        self.progress.set(0)
        self.progress.grid(row=0, column=1, padx=14, pady=6)

    def _set_status(self, text: str) -> None:
        self.status_label.configure(text=text)

    def _on_size(self, value) -> None:
        self.size_value.configure(text=f"Taille des points : {int(float(value))}")

    def _on_appearance_change(self, choice: str) -> None:
        mode, _ = APPEARANCE.get(choice, ("dark", False))
        ctk.set_appearance_mode(mode)

    def _plot_options(self, title: str | None = None) -> PlotOptions:
        return PlotOptions(
            title=title or self.title_entry.get().strip() or "Nuage de points 3D (XYZ)",
            marker_size=int(self.size_slider.get()),
            cmap=self.cmap_menu.get(),
            dpi=int(self.dpi_menu.get()),
            show_grid=bool(self.grid_switch.get()),
            invert_z=bool(self.invert_z_switch.get()),
            dark_mode=bool(self.dark_switch.get()),
            export_2d=bool(self.export2d_switch.get()),
            link_by_label=bool(getattr(self, "link_by_label_var", None) and self.link_by_label_var.get()),
            materialize_talus=bool(getattr(self, "materialize_talus_var", None) and self.materialize_talus_var.get()),
            close_base=bool(getattr(self, "close_base_var", None) and self.close_base_var.get()),
            face_fill=bool(getattr(self, "face_fill_var", None) and self.face_fill_var.get()),
        )

    def on_import(self) -> None:
        path = filedialog.askopenfilename(
            title="Sélectionner un fichier de points XYZ",
            filetypes=[
                ("Fichiers de points", "*.xlsx *.xlsm *.xls *.csv *.txt"),
                ("Excel", "*.xlsx *.xlsm *.xls"),
                ("CSV", "*.csv"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if not path:
            return
        sheets = list_sheets(path)
        if sheets:
            self.sheet_menu.configure(state="normal")
            self.sheet_menu.configure(values=sheets)
            self.sheet_menu.set(sheets[0])
            self.current_sheet = sheets[0]
        else:
            self.sheet_menu.configure(values=["-"])
            self.sheet_menu.set("-")
            self.sheet_menu.configure(state="disabled")
            self.current_sheet = None
        self._load_file(Path(path))

    def on_sheet_change(self, sheet: str) -> None:
        if self.data is None:
            return
        if sheet in ("-", ""):
            return
        self.current_sheet = sheet
        self._load_file(self.data.source, sheet)

    def _load_file(self, path: Path, sheet: str | int | None = None) -> None:
        self._set_status(f"Chargement de {path.name}...")
        try:
            data = load_points(path, sheet=sheet if sheet not in (None, "-") else self.current_sheet)
        except LoadError as exc:
            messagebox.showerror("Erreur d'import", str(exc))
            self._set_status("Échec du chargement.")
            self.progress.set(0)
            return

        self.data = data
        self.file_entry.configure(state="normal")
        self.file_entry.delete(0, "end")
        self.file_entry.insert(0, str(path))
        self.file_entry.configure(state="disabled")

        info = (
            f"Fichier : {path.name}\n"
            f"Points valides : {data.size}\n"
            f"Colonnes détectées : X='{data.x_col}', Y='{data.y_col}', Z='{data.z_col}'"
        )
        if data.dropped:
            info += f"\nLignes ignorées : {data.dropped}"
        self.info_label.configure(text=info)

        self._fill_tree(data)
        self._fill_stats(data)
        self.progress.set(1)
        self._set_status(f"{data.size} points chargés depuis {path.name}.")

    def _fill_tree(self, data: XYZData) -> None:
        self.tree.delete(*self.tree.get_children())
        limit = 2000
        for i, row in data.frame.head(limit).iterrows():
            self.tree.insert(
                "", "end", values=(i + 1, f"{row['X']:.3f}", f"{row['Y']:.3f}", f"{row['Z']:.3f}")
            )
        suffix = "" if data.size <= limit else f" (affichage limité à {limit})"
        self.table_count.configure(text=f"{data.size} point(s){suffix}")

    def _fill_stats(self, data: XYZData) -> None:
        stats = data.statistics()
        lines = [f"  Fichier : {data.source.name}   |   Points : {data.size}", ""]
        lines.append(f"  {'Axe':<6}{'Min':>14}{'Max':>14}{'Moyenne':>14}{'Ecart-type':>14}")
        for _, row in stats.iterrows():
            lines.append(
                f"  {row['Axe']:<6}{row['Minimum']:>14.3f}{row['Maximum']:>14.3f}"
                f"{row['Moyenne']:>14.3f}{row['Ecart-type']:>14.3f}"
            )
        self.stats_box.configure(state="normal")
        self.stats_box.delete("1.0", "end")
        self.stats_box.insert("1.0", "\n".join(lines))
        self.stats_box.configure(state="disabled")

    def _run_async(self, work, on_done) -> None:
        def runner() -> None:
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                self.after(0, lambda e=exc: self._on_async_error(e))
                return
            self.after(0, lambda r=result: on_done(r))

        threading.Thread(target=runner, daemon=True).start()

    def _on_async_error(self, exc: Exception) -> None:
        self.progress.set(0)
        self._set_status("Une erreur est survenue.")
        messagebox.showerror("Erreur", f"{type(exc).__name__} : {exc}")

    def _output_dir(self) -> Path:
        stem = self.data.source.stem if self.data else "sortie"
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUTPUT_DIR / f"{safe}_{stamp}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def on_generate(self) -> None:
        if self.data is None:
            messagebox.showwarning("Aucune donnée", "Veuillez d'abord importer un fichier XYZ.")
            return
        opts = self._plot_options()
        out_dir = self._output_dir()
        data = self.data

        self.generate_btn.configure(state="disabled", text="Génération en cours...")
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self._set_status("Génération des figures en cours...")

        def done(results: list[FigureResult]) -> None:
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.progress.set(1)
            self.generate_btn.configure(state="normal", text="Générer les figures")
            self.figures = results
            self._render_gallery()
            self.figures_hint.configure(
                text=f"{len(results)} figure(s) générée(s) dans :\n{out_dir}"
            )
            self._set_status(f"{len(results)} figure(s) générées avec succès.")
            self.tabview.set("Figures")

        self._run_async(lambda: generate_all(data, out_dir, opts), done)

    def _render_gallery(self) -> None:
        for widget in self.gallery.winfo_children():
            widget.destroy()
        self._thumb_refs.clear()

        if not self.figures:
            ctk.CTkLabel(self.gallery, text="Aucune figure.").grid(row=0, column=0, padx=10, pady=10)
            return

        for index, figure in enumerate(self.figures):
            if not figure.path.exists():
                continue
            card = ctk.CTkFrame(self.gallery)
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=8, pady=8)
            card.grid_columnconfigure(0, weight=1)

            with Image.open(figure.path) as img:
                thumb = img.convert("RGB")
                thumb.thumbnail((420, 320))
                ctk_image = ctk.CTkImage(light_image=thumb.copy(), dark_image=thumb.copy(), size=thumb.size)
            self._thumb_refs.append(ctk_image)

            label = ctk.CTkLabel(card, text="", image=ctk_image)
            label.grid(row=0, column=0, padx=10, pady=(10, 4))

            ctk.CTkLabel(
                card, text=figure.title, font=ctk.CTkFont(weight="bold")
            ).grid(row=1, column=0, padx=10)

            buttons = ctk.CTkFrame(card, fg_color="transparent")
            buttons.grid(row=2, column=0, pady=(4, 10))
            ctk.CTkButton(
                buttons, text="Ouvrir", width=90, command=lambda p=figure.path: self._open_file(p)
            ).grid(row=0, column=0, padx=4)
            ctk.CTkButton(
                buttons,
                text="Dossier",
                width=90,
                fg_color="transparent",
                border_width=1,
                command=lambda p=figure.path: self._reveal_file(p),
            ).grid(row=0, column=1, padx=4)

    def on_preview(self) -> None:
        if self.data is None:
            messagebox.showwarning("Aucune donnée", "Veuillez d'abord importer un fichier XYZ.")
            return

        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        if self._interactive_window is not None and self._interactive_window.winfo_exists():
            self._interactive_window.destroy()

        window = ctk.CTkToplevel(self)
        window.title("Aperçu interactif 3D - rotation à la souris")
        window.geometry("980x760")
        self._interactive_window = window

        opts = self._plot_options(title=self.title_entry.get().strip() or "Nuage de points 3D")
        figure = build_3d_figure(self.data, opts)
        figure.set_size_inches(9, 6.5)

        canvas = FigureCanvasTkAgg(figure, master=window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        toolbar = NavigationToolbar2Tk(canvas, window)
        toolbar.update()
        toolbar.pack(fill="x")

        self._set_status("Aperçu 3D ouvert : cliquez-glissez pour faire tourner la figure.")

    def on_report(self) -> None:
        if self.data is None:
            messagebox.showwarning("Aucune donnée", "Veuillez d'abord importer un fichier XYZ.")
            return
        if not self.figures:
            messagebox.showwarning(
                "Aucune figure",
                "Veuillez d'abord générer les figures avant de créer le rapport.",
            )
            return

        default_name = f"rapport_{self.data.source.stem}.docx"
        out_path = filedialog.asksaveasfilename(
            title="Enregistrer le rapport Word",
            defaultextension=".docx",
            initialfile=default_name,
            filetypes=[("Document Word", "*.docx")],
            initialdir=str(OUTPUT_DIR),
        )
        if not out_path:
            return

        opts = ReportOptions(
            title=self.report_title.get().strip() or "Rapport d'analyse XYZ",
            author=self.report_author.get().strip(),
            subject=self.report_subject.get().strip() or "Visualisation 3D de données de points",
            include_table=bool(self.report_table_switch.get()),
        )
        data = self.data
        figures = list(self.figures)

        self.report_btn.configure(state="disabled", text="Création en cours...")
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self._set_status("Création du rapport Word...")

        def done(path: Path) -> None:
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.progress.set(1)
            self.report_btn.configure(state="normal", text="Générer le rapport Word")
            self.report_log.configure(state="normal")
            self.report_log.insert("end", f"Rapport créé : {path}\n")
            self.report_log.see("end")
            self.report_log.configure(state="disabled")
            self._set_status("Rapport Word généré.")
            if messagebox.askyesno("Rapport créé", f"Rapport enregistré :\n{path}\n\nOuvrir maintenant ?"):
                self._open_file(path)

        self._run_async(lambda: build_report(data, figures, out_path, opts), done)

    def on_open_output(self) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self._reveal_file(OUTPUT_DIR)

    def _open_file(self, path: Path) -> None:
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Ouverture impossible", str(exc))

    def _reveal_file(self, path: Path) -> None:
        try:
            if path.is_dir():
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                os.startfile(str(path.parent))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Ouverture impossible", str(exc))

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        fichier = tk.Menu(menubar, tearoff=0)
        fichier.add_command(label="Nouveau", accelerator="Ctrl+N", command=self._on_file_new)
        fichier.add_command(label="Ouvrir...", accelerator="Ctrl+O", command=self._on_file_open)
        fichier.add_separator()
        fichier.add_command(label="Enregistrer", accelerator="Ctrl+S", command=self._on_file_save)
        fichier.add_command(
            label="Enregistrer sous...",
            accelerator="Ctrl+Maj+S",
            command=self._on_file_save_as,
        )
        fichier.add_separator()
        fichier.add_command(label="Quitter", accelerator="Alt+F4", command=self._on_file_quit)
        menubar.add_cascade(label="Fichier", menu=fichier)

        self.configure(menu=menubar)
        self._menubar = menubar

        self.bind_all("<Control-n>", lambda _e: self._on_file_new())
        self.bind_all("<Control-o>", lambda _e: self._on_file_open())
        self.bind_all("<Control-s>", lambda _e: self._on_file_save())
        self.bind_all("<Control-Shift-S>", lambda _e: self._on_file_save_as())

    def _on_file_new(self) -> None:
        if self.data is not None and not messagebox.askyesno(
            "Nouveau projet", "Effacer les données et les figures actuelles ?"
        ):
            return
        self.data = None
        self.figures = []
        self.current_sheet = None
        self._save_path = None

        self.file_entry.configure(state="normal")
        self.file_entry.delete(0, "end")
        self.file_entry.configure(state="disabled")

        self.info_label.configure(text="Aucune donnée chargée.")
        self.sheet_menu.configure(values=["-"])
        self.sheet_menu.set("-")
        self.sheet_menu.configure(state="disabled")

        self.tree.delete(*self.tree.get_children())
        self.table_count.configure(text="0 point(s)")

        self.stats_box.configure(state="normal")
        self.stats_box.delete("1.0", "end")
        self.stats_box.insert("1.0", "Aucune donnée chargée.\n")
        self.stats_box.configure(state="disabled")

        self._render_gallery()
        self.figures_hint.configure(text="Aucune figure générée.")
        self._set_status("Nouveau projet. Importez un fichier de points XYZ.")

    def _on_file_open(self) -> None:
        self.on_import()

    def _save_to(self, path: Path) -> None:
        if self.data is None:
            messagebox.showwarning("Aucune donnée", "Aucune donnée à enregistrer.")
            return
        try:
            if path.suffix.lower() in (".xlsx", ".xlsm"):
                self.data.frame.to_excel(path, index=False)
            else:
                self.data.frame.to_csv(path, index=False, encoding="utf-8-sig")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Enregistrement impossible", str(exc))
            return
        self._set_status(f"Données enregistrées : {path}")

    def _on_file_save(self) -> None:
        if self.data is None:
            messagebox.showwarning("Aucune donnée", "Veuillez d'abord importer un fichier XYZ.")
            return
        if self._save_path is None:
            self._on_file_save_as()
            return
        self._save_to(self._save_path)

    def _on_file_save_as(self) -> None:
        if self.data is None:
            messagebox.showwarning("Aucune donnée", "Veuillez d'abord importer un fichier XYZ.")
            return
        default = f"{self.data.source.stem}_export.csv"
        out_path = filedialog.asksaveasfilename(
            title="Enregistrer les données sous",
            defaultextension=".csv",
            initialfile=default,
            filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx")],
            initialdir=str(OUTPUT_DIR),
        )
        if not out_path:
            return
        self._save_path = Path(out_path)
        self._save_to(self._save_path)

    def _on_file_quit(self) -> None:
        self.destroy()


def main() -> int:
    try:
        app = MK3DApp()
    except Exception as exc:  # noqa: BLE001
        print(f"Erreur au démarrage : {exc}", file=sys.stderr)
        raise
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
