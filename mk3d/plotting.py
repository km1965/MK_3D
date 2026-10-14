"""Génération des figures 3D et des projections 2D à partir des points XYZ."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from .data_loader import XYZData, split_label_level

BACKGROUND_LIGHT = "#f5f6fa"
BACKGROUND_DARK = "#1b1b25"
GRID_LIGHT = "#c8ccd8"
GRID_DARK = "#3a3a48"


@dataclass
class PlotOptions:
    title: str = "Nuage de points 3D (XYZ)"
    marker_size: int = 20
    cmap: str = "viridis"
    dpi: int = 150
    show_grid: bool = True
    invert_z: bool = False
    dark_mode: bool = False
    export_2d: bool = True
    projection_name: str = "3D"
    link_by_label: bool = False
    link_color: str = "#ff6b35"
    link_width: float = 1.4
    link_alpha: float = 0.7
    link_style: str = "-"
    # Faces de talus (polygones fermés reliant les profils bas et haut)
    materialize_talus: bool = False
    close_base: bool = False
    face_fill: bool = True
    face_color: str = "#3ba7ff"
    face_alpha: float = 0.22
    face_edge_color: str = "#1f6fb2"
    face_edge_width: float = 1.4
    base_color: str = "#8e6bd6"


@dataclass
class FigureResult:
    key: str
    title: str
    caption: str
    path: Path
    kind: str
    selected: bool = field(default=True)


def _window_titles(opts: PlotOptions) -> tuple[str, str]:
    if opts.dark_mode:
        return BACKGROUND_DARK, "#e8e8f0"
    return "#ffffff", "#1a1a22"


def _style_axes(ax, opts: PlotOptions) -> None:
    bg, fg = _window_titles(opts)
    ax.set_facecolor(bg)
    ax.tick_params(colors=fg, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(GRID_DARK if opts.dark_mode else GRID_LIGHT)


def _style_axes3d(ax, opts: PlotOptions) -> None:
    bg, fg = _window_titles(opts)
    ax.set_facecolor(bg)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.set_pane_color((0, 0, 0, 0))
        axis.line.set_color(GRID_DARK if opts.dark_mode else GRID_LIGHT)
    ax.tick_params(colors=fg, labelsize=8)
    if opts.show_grid:
        ax.grid(True, color=GRID_DARK if opts.dark_mode else GRID_LIGHT, alpha=0.5)
    else:
        ax.grid(False)


def _equalise_3d(ax, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> None:
    span = max(x.max() - x.min(), y.max() - y.min(), z.max() - z.min())
    half = span / 2.0 if span > 0 else 1.0
    for axis, values, setter in (
        ("x", x, ax.set_xlim),
        ("y", y, ax.set_ylim),
        ("z", z, ax.set_zlim),
    ):
        mid = (values.max() + values.min()) / 2.0
        setter(mid - half, mid + half)


def _draw_label_links(ax, data: XYZData, opts: PlotOptions) -> None:
    if not opts.link_by_label or not data.has_labels:
        return
    labels = data.labels
    x, y, z = data.x, data.y, data.z
    for lbl, mask in labels.groupby(labels).groups.items():
        if str(lbl).strip() == "" or len(mask) < 2:
            continue
        idx = list(mask)
        ax.plot(
            x[idx],
            y[idx],
            z[idx],
            linestyle=opts.link_style,
            linewidth=opts.link_width,
            color=opts.link_color,
            alpha=opts.link_alpha,
            zorder=1,
        )


def _draw_label_links2d(ax, data: XYZData, opts: PlotOptions, h_axis: int, v_axis: int) -> None:
    if not opts.link_by_label or not data.has_labels:
        return
    labels = data.labels
    vals = (data.x, data.y, data.z)
    h, v = vals[h_axis], vals[v_axis]
    for lbl, mask in labels.groupby(labels).groups.items():
        if str(lbl).strip() == "" or len(mask) < 2:
            continue
        idx = list(mask)
        ax.plot(
            h[idx],
            v[idx],
            linestyle=opts.link_style,
            linewidth=opts.link_width,
            color=opts.link_color,
            alpha=opts.link_alpha,
            zorder=1,
        )


def _new_figure(opts: PlotOptions):
    bg, _ = _window_titles(opts)
    fig = plt.figure(figsize=(10, 7.5), dpi=opts.dpi, facecolor=bg)
    return fig


def _save(fig, path: Path, opts: PlotOptions) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=opts.dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _profile_direction(xy: np.ndarray) -> np.ndarray:
    """Direction principale (dans le plan XY) d'un nuage de points."""
    if len(xy) < 2:
        return np.array([1.0, 0.0])
    centred = xy - xy.mean(axis=0)
    cov = np.cov(centred.T)
    if not np.all(np.isfinite(cov)):
        return np.array([1.0, 0.0])
    values, vectors = np.linalg.eigh(cov)
    direction = vectors[:, int(np.argmax(values))]
    norm = np.linalg.norm(direction)
    if norm == 0:
        return np.array([1.0, 0.0])
    return direction / norm


def _order_profile(profile: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Trie un profil (Nx3) le long de la direction principale."""
    projection = profile[:, :2] @ direction
    return profile[np.argsort(projection)]


def _resample_profile(profile: np.ndarray, count: int) -> np.ndarray:
    """Ré-échantillonne un profil ordonné (Nx3) sur ``count`` points
    régulièrement espacés le long de la courbe."""
    if len(profile) == count:
        return profile
    if len(profile) < 2:
        return np.repeat(profile[:1], count, axis=0)
    segments = np.linalg.norm(np.diff(profile, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(segments)])
    if cumulative[-1] <= 0:
        return np.repeat(profile[:1], count, axis=0)
    params = cumulative / cumulative[-1]
    targets = np.linspace(0.0, 1.0, count)
    out = np.empty((count, 3))
    for k in range(3):
        out[:, k] = np.interp(targets, params, profile[:, k])
    return out


def _talus_faces(data: XYZData) -> list[tuple[str, np.ndarray]]:
    """Détecte les talus et renvoie, pour chacun, son polygone fermé (Nx3).

    Un talus est identifié par un « côté » possédant à la fois un profil bas
    et un profil haut (mots-clés : bas/pied et haut/crête/sommet...).
    """
    if not data.has_labels:
        return []

    frame = data.frame
    xs = frame["X"].to_numpy(dtype=float)
    ys = frame["Y"].to_numpy(dtype=float)
    zs = frame["Z"].to_numpy(dtype=float)
    labels = data.labels.to_numpy()

    sides: dict[str, dict[str, list[int]]] = {}
    for index, label in enumerate(labels):
        side, level = split_label_level(label)
        if not side or level is None:
            continue
        sides.setdefault(side, {"bas": [], "haut": []})[level].append(index)

    faces: list[tuple[str, np.ndarray]] = []
    for side, groups in sorted(sides.items()):
        low_idx = groups["bas"]
        high_idx = groups["haut"]
        if len(low_idx) < 2 or len(high_idx) < 2:
            continue

        low_pts = np.column_stack([xs[low_idx], ys[low_idx], zs[low_idx]])
        high_pts = np.column_stack([xs[high_idx], ys[high_idx], zs[high_idx]])
        direction = _profile_direction(np.vstack([low_pts[:, :2], high_pts[:, :2]]))

        low = _order_profile(low_pts, direction)
        high = _order_profile(high_pts, direction)

        count = max(len(low), len(high))
        low = _resample_profile(low, count)
        high = _resample_profile(high, count)

        polygon = np.vstack([low, high[::-1]])
        faces.append((side, polygon))

    return faces


def _talus_low_profile(data: XYZData, side: str) -> np.ndarray:
    """Extrait le profil bas trié d'un côté donné."""
    frame = data.frame
    xs = frame["X"].to_numpy(dtype=float)
    ys = frame["Y"].to_numpy(dtype=float)
    zs = frame["Z"].to_numpy(dtype=float)
    labels = data.labels.to_numpy()
    indices = [
        i for i, label in enumerate(labels)
        if split_label_level(label) == (side, "bas")
    ]
    pts = np.column_stack([xs[indices], ys[indices], zs[indices]])
    if len(pts) < 2:
        return pts
    return _order_profile(pts, _profile_direction(pts[:, :2]))


def _close_base_loop(low_profiles: list[np.ndarray]) -> np.ndarray | None:
    """Relie les profils bas par leurs extrémités les plus proches pour
    former une boucle fermée matérialisant la surface de base."""
    if len(low_profiles) < 2:
        return None
    remaining = [np.asarray(p, dtype=float) for p in low_profiles]
    loop: list[np.ndarray] = list(remaining.pop(0))
    while remaining:
        last = loop[-1]
        best: tuple[float, int, np.ndarray] | None = None
        for index, profile in enumerate(remaining):
            d_start = float(np.linalg.norm(profile[0] - last))
            d_end = float(np.linalg.norm(profile[-1] - last))
            if d_end < d_start:
                sequence, distance = profile[::-1], d_end
            else:
                sequence, distance = profile, d_start
            if best is None or distance < best[0]:
                best = (distance, index, sequence)
        assert best is not None
        _, index, sequence = best
        loop.extend(list(sequence))
        remaining.pop(index)
    return np.asarray(loop)


def _draw_talus_faces(ax, data: XYZData, opts: PlotOptions) -> None:
    if not opts.materialize_talus:
        return
    faces = _talus_faces(data)
    if not faces:
        return

    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    for _side, polygon in faces:
        closed = np.vstack([polygon, polygon[:1]])
        if opts.face_fill:
            collection = Poly3DCollection(
                [polygon],
                facecolor=opts.face_color,
                edgecolor=opts.face_edge_color,
                linewidths=opts.face_edge_width,
                alpha=opts.face_alpha,
                zorder=1,
            )
            ax.add_collection3d(collection)
        else:
            ax.plot(
                closed[:, 0], closed[:, 1], closed[:, 2],
                color=opts.face_edge_color, linewidth=opts.face_edge_width, zorder=2,
            )

    if opts.close_base:
        loop = _close_base_loop([_talus_low_profile(data, side) for side, _poly in faces])
        if loop is not None and len(loop) >= 3:
            if opts.face_fill:
                collection = Poly3DCollection(
                    [loop],
                    facecolor=opts.base_color,
                    edgecolor=opts.base_color,
                    linewidths=opts.face_edge_width,
                    alpha=opts.face_alpha * 0.9,
                    zorder=1,
                )
                ax.add_collection3d(collection)
            else:
                closed = np.vstack([loop, loop[:1]])
                ax.plot(
                    closed[:, 0], closed[:, 1], closed[:, 2],
                    color=opts.base_color, linewidth=opts.face_edge_width, zorder=2,
                )


def _draw_talus_faces2d(ax, data: XYZData, opts: PlotOptions, h_axis: int, v_axis: int) -> None:
    if not opts.materialize_talus:
        return
    faces = _talus_faces(data)
    if not faces:
        return

    for _side, polygon in faces:
        ph = polygon[:, h_axis]
        pv = polygon[:, v_axis]
        if opts.face_fill:
            ax.fill(
                ph, pv,
                facecolor=opts.face_color,
                edgecolor=opts.face_edge_color,
                linewidth=opts.face_edge_width,
                alpha=opts.face_alpha,
                zorder=1,
            )
        else:
            ax.plot(
                np.append(ph, ph[0]), np.append(pv, pv[0]),
                color=opts.face_edge_color, linewidth=opts.face_edge_width, zorder=2,
            )

    if opts.close_base:
        loop = _close_base_loop([_talus_low_profile(data, side) for side, _poly in faces])
        if loop is not None and len(loop) >= 3:
            lh = loop[:, h_axis]
            lv = loop[:, v_axis]
            if opts.face_fill:
                ax.fill(
                    lh, lv,
                    facecolor=opts.base_color,
                    edgecolor=opts.base_color,
                    linewidth=opts.face_edge_width,
                    alpha=opts.face_alpha * 0.9,
                    zorder=1,
                )
            else:
                ax.plot(
                    np.append(lh, lh[0]), np.append(lv, lv[0]),
                    color=opts.base_color, linewidth=opts.face_edge_width, zorder=2,
                )


def build_3d_figure(data: XYZData, opts: PlotOptions):
    """Construit la figure 3D (sans l'enregistrer) pour affichage interactif."""
    x, y, z = data.x, data.y, data.z
    fig = _new_figure(opts)
    ax = fig.add_subplot(111, projection="3d")
    _style_axes3d(ax, opts)

    sc = ax.scatter(
        x,
        y,
        z,
        c=z,
        cmap=opts.cmap,
        s=opts.marker_size,
        alpha=0.85,
        edgecolors="none",
    )
    cbar = fig.colorbar(sc, ax=ax, shrink=0.62, pad=0.09)
    cbar.set_label("Altitude Z", color=_window_titles(opts)[1], fontsize=9)
    cbar.ax.tick_params(colors=_window_titles(opts)[1], labelsize=8)

    ax.set_xlabel("X", fontsize=10)
    ax.set_ylabel("Y", fontsize=10)
    ax.set_zlabel("Z", fontsize=10)
    ax.set_title(opts.title, fontsize=13, fontweight="bold", pad=14)
    ax.view_init(elev=22, azim=-58)
    if opts.invert_z:
        ax.invert_zaxis()
    _equalise_3d(ax, x, y, z)
    _draw_label_links(ax, data, opts)
    _draw_talus_faces(ax, data, opts)
    return fig


def plot_3d(data: XYZData, out_path: Path, opts: PlotOptions) -> FigureResult:
    fig = build_3d_figure(data, opts)
    out_path = Path(out_path)
    _save(fig, out_path, opts)
    caption = (
        f"Figure 1 - Nuage de points 3D ({data.size} points) - "
        f"coloration selon l'altitude Z."
    )
    return FigureResult("3d", "Nuage de points 3D", caption, out_path, "3d")



def _plot_projection(
    data: XYZData,
    out_path: Path,
    opts: PlotOptions,
    h_axis: int,
    v_axis: int,
    index: int,
) -> FigureResult:
    labels = ("X", "Y", "Z")
    values = (data.x, data.y, data.z)
    h, v = values[h_axis], values[v_axis]
    h_label, v_label = labels[h_axis], labels[v_axis]

    fig, ax = plt.subplots(figsize=(9, 6.5), dpi=opts.dpi, facecolor=_window_titles(opts)[0])
    _style_axes(ax, opts)
    sc = ax.scatter(
        h,
        v,
        c=data.z,
        cmap=opts.cmap,
        s=max(opts.marker_size - 6, 6),
        alpha=0.85,
        edgecolors="none",
    )
    cbar = fig.colorbar(sc, ax=ax, shrink=0.85, pad=0.03)
    cbar.set_label("Z", color=_window_titles(opts)[1], fontsize=9)
    cbar.ax.tick_params(colors=_window_titles(opts)[1], labelsize=8)

    ax.set_xlabel(f"{h_label} (m)", fontsize=10)
    ax.set_ylabel(f"{v_label} (m)", fontsize=10)
    ax.set_title(f"Projection {h_label}-{v_label} - {opts.title}", fontsize=12, fontweight="bold")
    if opts.show_grid:
        ax.grid(True, linestyle=":", alpha=0.5, color=GRID_DARK if opts.dark_mode else GRID_LIGHT)
    ax.set_aspect("equal", adjustable="datalim")

    _draw_label_links2d(ax, data, opts, h_axis, v_axis)
    _draw_talus_faces2d(ax, data, opts, h_axis, v_axis)

    out_path = Path(out_path)
    _save(fig, out_path, opts)
    caption = f"Figure {index} - Projection dans le plan {h_label}-{v_label} ({data.size} points)."
    return FigureResult(
        f"{h_label.lower()}{v_label.lower()}",
        f"Projection {h_label}-{v_label}",
        caption,
        out_path,
        "2d",
    )


def plot_projections_grid(data: XYZData, out_path: Path, opts: PlotOptions) -> FigureResult:
    x, y, z = data.x, data.y, data.z
    bg, fg = _window_titles(opts)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.6), dpi=opts.dpi, facecolor=bg)

    pairs = (
        (x, y, "X", "Y", 0, 1),
        (x, z, "X", "Z", 0, 2),
        (y, z, "Y", "Z", 1, 2),
    )
    for ax, (h, v, hl, vl, h_axis, v_axis) in zip(axes, pairs):
        _style_axes(ax, opts)
        sc = ax.scatter(h, v, c=z, cmap=opts.cmap, s=max(opts.marker_size - 8, 5), alpha=0.85)
        ax.set_xlabel(f"{hl} (m)", fontsize=9)
        ax.set_ylabel(f"{vl} (m)", fontsize=9)
        ax.set_title(f"{hl} - {vl}", fontsize=11, fontweight="bold")
        ax.set_aspect("equal", adjustable="datalim")
        if opts.show_grid:
            ax.grid(True, linestyle=":", alpha=0.5, color=GRID_DARK if opts.dark_mode else GRID_LIGHT)
        # liens
        if opts.link_by_label and data.has_labels:
            labels = data.labels
            vals_h, vals_v = h, v
            for lbl, mask in labels.groupby(labels).groups.items():
                if str(lbl).strip() == "" or len(mask) < 2:
                    continue
                idx = list(mask)
                ax.plot(vals_h[idx], vals_v[idx], linestyle=opts.link_style, linewidth=opts.link_width, color=opts.link_color, alpha=opts.link_alpha, zorder=1)
        _draw_talus_faces2d(ax, data, opts, h_axis, v_axis)
    fig.colorbar(sc, ax=axes, shrink=0.8, pad=0.02).set_label(
        "Z", color=fg, fontsize=9
    )
    fig.suptitle(f"Projections orthogonales - {opts.title}", fontsize=13, fontweight="bold")

    out_path = Path(out_path)
    _save(fig, out_path, opts)
    caption = "Figure - Ensemble des projections orthogonales X-Y, X-Z et Y-Z."
    return FigureResult("grid", "Projections 2D (X-Y, X-Z, Y-Z)", caption, out_path, "2d")


def generate_all(data: XYZData, out_dir: str | Path, opts: PlotOptions) -> list[FigureResult]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[FigureResult] = [plot_3d(data, out_dir / "03_nuage_3d.png", opts)]
    if opts.export_2d:
        results.append(_plot_projection(data, out_dir / "01_projection_xy.png", opts, 0, 1, 2))
        results.append(_plot_projection(data, out_dir / "02_projection_xz.png", opts, 0, 2, 3))
        results.append(_plot_projection(data, out_dir / "03_projection_yz.png", opts, 1, 2, 4))
        results.append(plot_projections_grid(data, out_dir / "00_projections_2d.png", opts))
    return results
