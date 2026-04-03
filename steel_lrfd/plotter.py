"""
P-M Interaction Diagram Plotter
================================
Plots the axial force-moment interaction envelope per AISC 360-16 H1-1,
showing both the nominal curve (without φ) and the design curve (with φ)
on the same figure, plus any applied load points.

Display convention (Y-axis flipped for engineering intuition)
-------------------------------------------------------------
  Y > 0  →  compression  (top)
  Y < 0  →  tension      (bottom)
  X >= 0  →  moment magnitude
"""

from __future__ import annotations

import os as _os

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D

from .core import BeamColumnLRFD, AppliedForces, InteractionResult  # noqa: E402

# Use a font that reliably renders Greek letters (φ) and arrows (↑↓)
# but avoid CJK requirements by keeping all chart text in English.
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.family"] = "DejaVu Sans"

# Detect headless environment (Codespaces, SSH, CI …)
_HEADLESS = (
    not _os.environ.get("DISPLAY")
    and _os.environ.get("TERM_PROGRAM") != "vscode-terminal"
)

# ── colour palette ──────────────────────────────────────────────────────────
C_NOM   = "#1565C0"   # blue        – nominal curve
C_DES   = "#C62828"   # red         – design curve
C_FILL  = "#FFCDD2"   # light red   – inside design envelope
C_SHADE = "#E3F2FD"   # light blue  – between nominal and design
C_PASS  = "#2E7D32"   # green       – passing load point
C_FAIL  = "#D84315"   # orange-red  – failing load point
C_ZONE  = "#757575"   # grey        – zone boundary


def _flip(P_arr):
    """Negate P so compression (P<0 internally) plots at top (Y>0)."""
    return -np.asarray(P_arr)


# ── main entry point ─────────────────────────────────────────────────────────

def plot_pm_diagram(
    bc: BeamColumnLRFD,
    load_cases: list[tuple[str, AppliedForces]] | None = None,
    *,
    n_pts: int = 400,
    save_path: str | None = "PM_interaction_diagram.png",
    show: bool = True,
) -> plt.Figure:
    """
    Draw a two-panel P-M interaction diagram.

    Left  : nominal vs design curves + shaded φ-reduction zone
    Right : design curve, H1-1a/H1-1b zone lines, load-point check markers
    """
    # ── build curve arrays ───────────────────────────────────────────────────
    P_nom_raw, M_nom_raw = bc.interaction_curve(n_pts=n_pts, with_phi=False)
    P_des_raw, M_des_raw = bc.interaction_curve(n_pts=n_pts, with_phi=True)

    P_nom = _flip(P_nom_raw);  M_nom = np.array(M_nom_raw)
    P_des = _flip(P_des_raw);  M_des = np.array(M_des_raw)

    phi_cPn  = bc.compression.phi_Pn   # kN  (positive magnitude)
    phi_tPnt = bc.tension.phi_Pnt      # kN  (positive magnitude)
    phi_Mnx  = bc.flexure_x.phi_Mn    # kN·m
    Pn       = bc.compression.Pn      # kN
    Pnt      = bc.tension.Pnt         # kN
    Mnx      = bc.flexure_x.Mn        # kN·m

    # ── evaluate load cases ──────────────────────────────────────────────────
    results: list[tuple[str, AppliedForces, InteractionResult]] = []
    if load_cases:
        for lbl, f in load_cases:
            results.append((lbl, f, bc.check(f)))

    # ── figure ───────────────────────────────────────────────────────────────
    fig, (ax_left, ax_right) = plt.subplots(
        1, 2, figsize=(14, 8),
        gridspec_kw={"wspace": 0.35},
    )

    sec  = bc.sec
    mat  = bc.mat
    beam = bc.beam
    col  = bc.col
    fig.suptitle(
        f"AISC 360-16 LRFD   P-M Interaction Diagram\n"
        f"{sec.name}   Fy = {mat.Fy} MPa   "
        f"KL = {col.KyLy/1000:.1f} m   "
        f"Lb = {beam.Lb/1000:.1f} m   "
        f"Cb = {beam.Cb:.2f}",
        fontsize=12, fontweight="bold", y=0.98,
    )

    _draw_left(ax_left, P_nom, M_nom, P_des, M_des,
               phi_cPn, phi_tPnt, phi_Mnx, Pn, Pnt, Mnx, results)

    _draw_right(ax_right, P_des, M_des,
                phi_cPn, phi_tPnt, phi_Mnx, results)

    # ── save ─────────────────────────────────────────────────────────────────
    out = save_path or "PM_interaction_diagram.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"\n  Figure saved -> {out}")

    if show and not _HEADLESS:
        plt.show()
    else:
        _path = _os.path.abspath(out)
        print(f"  Open in VS Code: code \"{_path}\"")
        if _os.system(f'code "{_path}" 2>/dev/null') != 0:
            print(f"  (Click {_os.path.basename(out)} in the Explorer panel)")
        plt.close(fig)

    return fig


# ── left panel ────────────────────────────────────────────────────────────────

def _draw_left(ax, P_nom, M_nom, P_des, M_des,
               phi_cPn, phi_tPnt, phi_Mnx,
               Pn, Pnt, Mnx, results):

    ax.fill_betweenx(P_des, M_des, M_nom,
                     alpha=0.25, color=C_SHADE, zorder=1,
                     label="phi-reduction zone")
    ax.fill_betweenx(P_des, 0, M_des,
                     alpha=0.18, color=C_FILL, zorder=1,
                     label="Safe region (design)")

    ax.plot(M_nom, P_nom, color=C_NOM, lw=2.2, ls="--", zorder=3,
            label=f"Nominal (no phi)\n"
                  f"  Pn = {Pn:.0f} kN,  Mn = {Mnx:.0f} kN·m")
    ax.plot(M_des, P_des, color=C_DES, lw=2.5, zorder=3,
            label=f"Design (with phi)\n"
                  f"  phiPn = {phi_cPn:.0f} kN,  phiMn = {phi_Mnx:.0f} kN·m")

    _annotate(ax, 0,  phi_cPn,  f"phicPn\n{phi_cPn:.0f} kN",
              C_DES, dx=phi_Mnx*0.12, dy= phi_cPn*0.08)
    _annotate(ax, 0,  Pn,       f"Pn\n{Pn:.0f} kN",
              C_NOM, dx=phi_Mnx*0.12, dy=-Pn*0.08)
    _annotate(ax, 0, -phi_tPnt, f"phitPnt\n{phi_tPnt:.0f} kN",
              C_DES, dx=phi_Mnx*0.12, dy=-phi_tPnt*0.08)
    _annotate(ax, phi_Mnx, 0,   f"phiMnx\n{phi_Mnx:.0f} kN·m",
              C_DES, dx=0, dy=phi_cPn*0.12)
    _annotate(ax, Mnx, 0,       f"Mnx\n{Mnx:.0f} kN·m",
              C_NOM, dx=0, dy=-phi_cPn*0.12)

    for lbl, f, r in results:
        _plot_point(ax, abs(f.Mux), -f.Pu, lbl, r.passes, r.IR)

    _finish_axes(ax,
                 title="(1) Nominal vs Design Envelope",
                 M_max=max(M_nom.max(), M_des.max()),
                 P_min=min(P_nom.min(), P_des.min()),
                 P_max=max(P_nom.max(), P_des.max()))


# ── right panel ───────────────────────────────────────────────────────────────

def _draw_right(ax, P_des, M_des, phi_cPn, phi_tPnt, phi_Mnx, results):

    ax.fill_betweenx(P_des, 0, M_des, alpha=0.12, color=C_DES, zorder=1)
    ax.plot(M_des, P_des, color=C_DES, lw=2.5, zorder=3,
            label="Design envelope")

    # H1-1a / H1-1b zone boundary lines
    P_bc =  0.20 * phi_cPn    # compression boundary (display +)
    P_bt = -0.20 * phi_tPnt   # tension boundary (display -)
    x_max = M_des.max() * 1.05

    ax.axhline(P_bc, color=C_ZONE, lw=1.2, ls=":", zorder=2)
    ax.axhline(P_bt, color=C_ZONE, lw=1.2, ls=":", zorder=2)

    ax.text(x_max * 0.50, P_bc * 1.12,
            "H1-1a  |Pu/phicPn| >= 0.20",
            fontsize=7.5, color=C_ZONE, va="center")
    ax.text(x_max * 0.50, (P_bc + P_bt) * 0.5,
            "H1-1b  |Pu/phiPn| < 0.20",
            fontsize=7.5, color=C_ZONE, va="center")
    ax.text(x_max * 0.50, P_bt * 1.12,
            "H1-1a  |Pu/phitPnt| >= 0.20",
            fontsize=7.5, color=C_ZONE, va="center")

    _annotate(ax, 0,  phi_cPn,  f"phicPn\n{phi_cPn:.0f} kN",
              C_DES, dx=phi_Mnx*0.15, dy= phi_cPn*0.06)
    _annotate(ax, 0, -phi_tPnt, f"phitPnt\n{phi_tPnt:.0f} kN",
              C_DES, dx=phi_Mnx*0.15, dy=-phi_tPnt*0.06)
    _annotate(ax, phi_Mnx, 0,   f"phiMnx\n{phi_Mnx:.0f} kN·m",
              C_DES, dx=0, dy=phi_cPn*0.10)

    legend_extra = []
    for i, (lbl, f, r) in enumerate(results):
        c = C_PASS if r.passes else C_FAIL
        marker = "D" if i == 0 else "o"
        P_display = -f.Pu
        ax.scatter(abs(f.Mux), P_display,
                   color=c, s=110, marker=marker,
                   edgecolors="white", lw=1.0, zorder=5)
        ax.annotate(
            f" {lbl}\n IR={r.IR:.3f} {'OK' if r.passes else 'NG'}",
            xy=(abs(f.Mux), P_display),
            fontsize=7.5, color=c,
            xytext=(6, 4), textcoords="offset points",
        )
        legend_extra.append(
            Line2D([0], [0], marker=marker, color="w",
                   markerfacecolor=c, markersize=8,
                   label=f"{lbl}  IR={r.IR:.3f} {'OK' if r.passes else 'NG'}")
        )

    ax.legend(handles=[
        Line2D([0], [0], color=C_DES, lw=2.5, label="Design envelope"),
        *legend_extra,
    ], fontsize=7.5, loc="upper right", framealpha=0.9)

    _finish_axes(ax,
                 title="(2) Design Envelope + Load Check Points",
                 M_max=M_des.max(),
                 P_min=P_des.min(),
                 P_max=P_des.max(),
                 legend=False)


# ── shared helpers ─────────────────────────────────────────────────────────────

def _annotate(ax, x, y, text, color, dx=0, dy=0):
    ax.annotate(
        text, xy=(x, y),
        xytext=(x + dx, y + dy),
        fontsize=7.5, color=color, ha="left", va="center",
        arrowprops=dict(arrowstyle="-", color=color, lw=0.8),
        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=color, alpha=0.8),
    )


def _plot_point(ax, Mx, Pu_display, label, passes, IR):
    c = C_PASS if passes else C_FAIL
    ax.scatter(Mx, Pu_display, color=c, s=90, zorder=5,
               edgecolors="white", lw=0.8)
    ax.annotate(f" {label}\n IR={IR:.3f}",
                xy=(Mx, Pu_display), fontsize=7, color=c,
                xytext=(5, 3), textcoords="offset points")


def _finish_axes(ax, title, M_max, P_min, P_max, legend=True):
    ax.axhline(0, color="black", lw=0.7, alpha=0.4)
    ax.axvline(0, color="black", lw=0.7, alpha=0.4)

    pad_x = M_max * 0.10
    pad_y = (P_max - P_min) * 0.08
    ax.set_xlim(-pad_x * 0.2, M_max + pad_x)
    ax.set_ylim(P_min - pad_y, P_max + pad_y)

    ax.set_xlabel("Moment Mu  (kN·m)", fontsize=10)
    ax.set_ylabel("Axial Force Pu  (kN)\nCompression C (+)  |  Tension T (-)",
                  fontsize=10)
    ax.set_title(title, fontsize=10, pad=8)
    ax.grid(True, alpha=0.25, lw=0.6)
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, which="minor", alpha=0.10, lw=0.4)

    if legend:
        ax.legend(fontsize=7.5, loc="upper right", framealpha=0.9)
