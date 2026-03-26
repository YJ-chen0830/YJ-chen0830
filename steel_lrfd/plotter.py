"""
P-M Interaction Diagram Plotter
================================
Plots the axial force – moment interaction envelope per AISC 360-16 H1-1,
showing both the **nominal** curve (without φ) and the **design** curve
(with φ) on the same figure, plus any applied load points.

Conventions
-----------
  P < 0  →  compression   (下方)
  P > 0  →  tension       (上方)
  M ≥ 0  →  moment magnitude  (右方)
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D

from .core import BeamColumnLRFD, AppliedForces, InteractionResult  # noqa: E402


# ── CJK font auto-detection ─────────────────────────────────────────────────
def _setup_cjk_font() -> None:
    """Try to configure a CJK-capable font; silently fall back if none found."""
    from matplotlib import font_manager as fm
    candidates = [
        "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
        "Noto Sans CJK TC", "Noto Sans CJK SC", "Noto Sans TC",
        "Microsoft JhengHei", "Microsoft YaHei",
        "PingFang TC", "PingFang SC",
        "AR PL UMing CN", "AR PL UKai CN",
        "Droid Sans Fallback",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            return
    # No CJK font found – use Unicode-safe ASCII fallback via axes text only
    plt.rcParams["axes.unicode_minus"] = False  # use ASCII hyphen for minus


_setup_cjk_font()
plt.rcParams["axes.unicode_minus"] = False   # avoid Unicode minus glyph warning


# ── colour palette ──────────────────────────────────────────────────────────
C_NOM   = "#1565C0"   # blue  – nominal curve
C_DES   = "#C62828"   # red   – design curve
C_FILL  = "#FFCDD2"   # light-red fill inside design envelope
C_SHADE = "#E3F2FD"   # light-blue shade between nominal and design
C_PASS  = "#2E7D32"   # green  – load point that passes
C_FAIL  = "#D84315"   # orange-red – load point that fails
C_ZONE  = "#757575"   # grey   – zone boundary line


# ── main entry point ────────────────────────────────────────────────────────

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

    Left panel  : nominal vs design curves + shaded φ-reduction zone
    Right panel : design curve only, H1-1a/H1-1b zone annotation,
                  applied load points with pass/fail colour

    Parameters
    ----------
    bc          : BeamColumnLRFD instance (already computed)
    load_cases  : list of (label, AppliedForces) – plotted on both panels
    n_pts       : curve resolution
    save_path   : file path to save figure (None → don't save)
    show        : whether to call plt.show()
    """
    # ── build curve arrays (kip-ft for moment) ──────────────────────────────
    P_nom, M_nom_in = bc.interaction_curve(n_pts=n_pts, with_phi=False)
    P_des, M_des_in = bc.interaction_curve(n_pts=n_pts, with_phi=True)

    P_nom = np.array(P_nom);  M_nom = np.array(M_nom_in) / 12.0
    P_des = np.array(P_des);  M_des = np.array(M_des_in) / 12.0

    # key anchor values (kip-ft)
    phi_cPn  = bc.compression.phi_Pn
    phi_tPnt = bc.tension.phi_Pnt
    phi_Mnx  = bc.flexure_x.phi_Mn  / 12.0
    Pn       = bc.compression.Pn
    Pnt      = bc.tension.Pnt
    Mnx      = bc.flexure_x.Mn      / 12.0

    # ── evaluate load-case results ───────────────────────────────────────────
    results: list[tuple[str, AppliedForces, InteractionResult]] = []
    if load_cases:
        for lbl, f in load_cases:
            results.append((lbl, f, bc.check(f)))

    # ── figure layout ────────────────────────────────────────────────────────
    fig, (ax_left, ax_right) = plt.subplots(
        1, 2, figsize=(14, 8),
        gridspec_kw={"wspace": 0.35},
    )

    sec  = bc.sec
    mat  = bc.mat
    beam = bc.beam
    col  = bc.col
    fig.suptitle(
        f"AISC 360-16 LRFD  軸力–彎矩互制圖  /  P-M Interaction Diagram\n"
        f"{sec.name}   Fy = {mat.Fy} ksi   "
        f"KL = {col.KyLy/12:.1f} ft   "
        f"Lb = {beam.Lb/12:.1f} ft   "
        f"Cb = {beam.Cb:.2f}",
        fontsize=12, fontweight="bold", y=0.98,
    )

    # ════════════════════════════════════════════════════════════════════════
    # LEFT PANEL – nominal vs design comparison
    # ════════════════════════════════════════════════════════════════════════
    _draw_left(ax_left, P_nom, M_nom, P_des, M_des,
               phi_cPn, phi_tPnt, phi_Mnx, Pn, Pnt, Mnx, results)

    # ════════════════════════════════════════════════════════════════════════
    # RIGHT PANEL – design curve + zone labels + load points
    # ════════════════════════════════════════════════════════════════════════
    _draw_right(ax_right, P_des, M_des,
                phi_cPn, phi_tPnt, phi_Mnx, results)

    # ── save & show ──────────────────────────────────────────────────────────
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  圖形已儲存 / Figure saved → {save_path}")

    if show:
        plt.show()

    return fig


# ── left panel ───────────────────────────────────────────────────────────────

def _draw_left(ax, P_nom, M_nom, P_des, M_des,
               phi_cPn, phi_tPnt, phi_Mnx,
               Pn, Pnt, Mnx, results):

    # shaded regions
    ax.fill_betweenx(P_des, M_des, M_nom,
                     alpha=0.25, color=C_SHADE, zorder=1,
                     label="φ 折減區 / φ-reduction zone")
    ax.fill_betweenx(P_des, 0, M_des,
                     alpha=0.18, color=C_FILL, zorder=1,
                     label="安全域 / Safe region (design)")

    # curves
    ax.plot(M_nom, P_nom, color=C_NOM, lw=2.2, ls="--", zorder=3,
            label=f"標稱強度 (Nominal, no φ)\n"
                  f"  Pn = {Pn:.0f} k,  Mn = {Mnx:.0f} k-ft")
    ax.plot(M_des, P_des, color=C_DES, lw=2.5, zorder=3,
            label=f"設計強度 (Design, with φ)\n"
                  f"  φPn = {phi_cPn:.0f} k,  φMn = {phi_Mnx:.0f} k-ft")

    # anchor point labels
    _annotate(ax, 0, -phi_cPn, f"φcPn\n{phi_cPn:.0f} k",
              C_DES, dx=phi_Mnx*0.12, dy=phi_cPn*0.08)
    _annotate(ax, 0, -Pn,       f"Pn\n{Pn:.0f} k",
              C_NOM, dx=phi_Mnx*0.12, dy=-Pn*0.08)
    _annotate(ax, phi_Mnx, 0,  f"φMnx\n{phi_Mnx:.0f} k-ft",
              C_DES, dx=0, dy=phi_cPn*0.12)
    _annotate(ax, Mnx, 0,      f"Mnx\n{Mnx:.0f} k-ft",
              C_NOM, dx=0, dy=-phi_cPn*0.12)

    # load points
    for lbl, f, r in results:
        _plot_point(ax, abs(f.Mux)/12, f.Pu, lbl, r.passes, r.IR)

    _finish_axes(ax,
                 title="① 標稱 vs 設計強度包絡線\n   Nominal vs Design Envelope",
                 M_max=max(M_nom.max(), M_des.max()),
                 P_min=min(P_nom.min(), P_des.min()),
                 P_max=max(P_nom.max(), P_des.max()))


# ── right panel ──────────────────────────────────────────────────────────────

def _draw_right(ax, P_des, M_des,
                phi_cPn, phi_tPnt, phi_Mnx, results):

    # envelope fill + curve
    ax.fill_betweenx(P_des, 0, M_des, alpha=0.12, color=C_DES, zorder=1)
    ax.plot(M_des, P_des, color=C_DES, lw=2.5, zorder=3,
            label="設計強度包絡線 / Design envelope")

    # ── H1-1a / H1-1b boundary line at |P|/φcPn = 0.20 ─────────────────────
    P_boundary = -0.20 * phi_cPn          # compression side  (P < 0)
    P_boundary_t = 0.20 * phi_tPnt        # tension side
    x_max = M_des.max() * 1.05

    ax.axhline(P_boundary,   color=C_ZONE, lw=1.2, ls=":",  zorder=2)
    ax.axhline(P_boundary_t, color=C_ZONE, lw=1.2, ls=":",  zorder=2)

    ax.text(x_max * 0.55, P_boundary * 1.10,
            "H1-1a  |Pu/φcPn| ≥ 0.20",
            fontsize=7.5, color=C_ZONE, va="center")
    ax.text(x_max * 0.55, (P_boundary + P_boundary_t) * 0.5 - phi_cPn*0.04,
            "H1-1b  |Pu/φcPn| < 0.20",
            fontsize=7.5, color=C_ZONE, va="center")
    ax.text(x_max * 0.55, P_boundary_t * 1.10,
            "H1-1a  |Pu/φtPnt| ≥ 0.20",
            fontsize=7.5, color=C_ZONE, va="center")

    # ── key anchor annotations ────────────────────────────────────────────────
    _annotate(ax, 0, -phi_cPn, f"φcPn\n{phi_cPn:.0f} k",
              C_DES, dx=phi_Mnx*0.15, dy=phi_cPn*0.06)
    _annotate(ax, 0,  phi_tPnt, f"φtPnt\n{phi_tPnt:.0f} k",
              C_DES, dx=phi_Mnx*0.15, dy=-phi_tPnt*0.06)
    _annotate(ax, phi_Mnx, 0,  f"φMnx\n{phi_Mnx:.0f} k-ft",
              C_DES, dx=0, dy=phi_cPn*0.10)

    # ── load points ───────────────────────────────────────────────────────────
    legend_extra = []
    for i, (lbl, f, r) in enumerate(results):
        col = C_PASS if r.passes else C_FAIL
        marker = "D" if i == 0 else "o"
        ax.scatter(abs(f.Mux)/12, f.Pu,
                   color=col, s=110, marker=marker,
                   edgecolors="white", lw=1.0, zorder=5)
        # small IR label beside each point
        ax.annotate(
            f" {lbl}\n IR={r.IR:.3f} {'OK' if r.passes else 'NG'}",
            xy=(abs(f.Mux)/12, f.Pu),
            fontsize=7.5, color=col,
            xytext=(6, 4), textcoords="offset points",
        )
        legend_extra.append(
            Line2D([0], [0], marker=marker, color="w",
                   markerfacecolor=col, markersize=8,
                   label=f"{lbl}  IR={r.IR:.3f} {'OK' if r.passes else 'NG'}")
        )

    ax.legend(handles=[
        Line2D([0],[0], color=C_DES, lw=2.5, label="設計包絡線 Design envelope"),
        *legend_extra,
    ], fontsize=7.5, loc="upper right", framealpha=0.9)

    _finish_axes(ax,
                 title="② 設計強度包絡線 + 外力檢核點\n   Design Envelope + Load Check Points",
                 M_max=M_des.max(),
                 P_min=P_des.min(),
                 P_max=P_des.max(),
                 legend=False)


# ── shared helpers ────────────────────────────────────────────────────────────

def _annotate(ax, x, y, text, color, dx=0, dy=0):
    ax.annotate(
        text, xy=(x, y),
        xytext=(x + dx, y + dy),
        fontsize=7.5, color=color, ha="left", va="center",
        arrowprops=dict(arrowstyle="-", color=color, lw=0.8),
        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=color, alpha=0.8),
    )


def _plot_point(ax, Mx, Pu, label, passes, IR):
    col = C_PASS if passes else C_FAIL
    ax.scatter(Mx, Pu, color=col, s=90, zorder=5,
               edgecolors="white", lw=0.8)
    ax.annotate(f" {label}\n IR={IR:.3f}",
                xy=(Mx, Pu), fontsize=7, color=col,
                xytext=(5, 3), textcoords="offset points")


def _finish_axes(ax, title, M_max, P_min, P_max, legend=True):
    # zero axes
    ax.axhline(0, color="black", lw=0.7, alpha=0.4)
    ax.axvline(0, color="black", lw=0.7, alpha=0.4)

    # padding
    pad_x = M_max * 0.10
    pad_y = (P_max - P_min) * 0.08
    ax.set_xlim(-pad_x * 0.2, M_max + pad_x)
    ax.set_ylim(P_min - pad_y, P_max + pad_y)

    ax.set_xlabel("彎矩 Mu  (kN·m)", fontsize=10)
    ax.set_ylabel("軸力 Pu  (kN)\n← 壓力 C            拉力 T →", fontsize=10)
    ax.set_title(title, fontsize=9.5, pad=8)
    ax.grid(True, alpha=0.25, lw=0.6)
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, which="minor", alpha=0.10, lw=0.4)

    if legend:
        ax.legend(fontsize=7.5, loc="upper right", framealpha=0.9)
