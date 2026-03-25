"""
Formatted text reports for AISC LRFD beam-column check results.
All moments printed in kip-ft; internal calculations remain kip-in.
"""

from __future__ import annotations

from .core import BeamColumnLRFD, AppliedForces, InteractionResult


# ── helpers ────────────────────────────────────────────────────────────────

SEP  = "=" * 64
SEP2 = "-" * 64
KIN_TO_KFT = 1.0 / 12.0

def _kft(kip_in: float) -> float:
    return kip_in * KIN_TO_KFT

def _sign(v: float, pos: str = "T", neg: str = "C") -> str:
    return pos if v >= 0 else neg


# ── section + strength summary ─────────────────────────────────────────────

def print_member_summary(bc: BeamColumnLRFD) -> None:
    sec, mat, col, beam = bc.sec, bc.mat, bc.col, bc.beam
    c  = bc.compression
    t  = bc.tension
    fx = bc.flexure_x
    fy = bc.flexure_y

    print(SEP)
    print("  AISC 360-16 LRFD  鋼梁柱設計報告")
    print("  Steel Beam-Column Design Report")
    print(SEP)

    # ── Section
    print(f"\n截面 / Section            : {sec.name}")
    print(f"材料 / Material            : Fy = {mat.Fy} ksi "
          f"({mat.Fy*6.895:.0f} MPa),  E = {mat.E:,} ksi")

    # ── Section props
    print(f"\n{'截面性質 / Section Properties':}")
    print(f"  A  = {sec.A:.2f} in²")
    print(f"  Ix = {sec.Ix:.1f} in⁴   Sx = {sec.Sx:.1f} in³   Zx = {sec.Zx:.1f} in³   rx = {sec.rx:.3f} in")
    print(f"  Iy = {sec.Iy:.1f} in⁴   Sy = {sec.Sy:.1f} in³   Zy = {sec.Zy:.1f} in³   ry = {sec.ry:.3f} in")
    print(f"  J  = {sec.J:.3f} in⁴   Cw = {sec.Cw:.0f} in⁶")

    # ── Parameters
    print(f"\n{'計算參數 / Design Parameters':}")
    print(f"  KxLx = {col.Kx}×{col.Lx/12:.2f} ft = {col.KxLx:.1f} in   "
          f"KyLy = {col.Ky}×{col.Ly/12:.2f} ft = {col.KyLy:.1f} in")
    print(f"  Lb   = {beam.Lb/12:.2f} ft = {beam.Lb:.1f} in   Cb = {beam.Cb:.2f}")

    # ── Compression
    print(f"\n{'[Chapter E] 軸壓強度 / Compressive Strength':}")
    print(f"  KL/rx = {c.KL_r_x:.2f}   KL/ry = {c.KL_r_y:.2f}   "
          f"控制 KL/r = {c.KL_r:.2f}  (限制值 {c.KL_r_limit:.2f})")
    print(f"  Fe  = {c.Fe:.2f} ksi   Fcr = {c.Fcr:.2f} ksi   [{c.buckling_mode}]")
    print(f"  Pn  = {c.Pn:.2f} kips              (標稱 Nominal)")
    print(f"  φcPn = {c.phi_Pn:.2f} kips   φc = {c.phi_c}  (設計 Design)")

    # ── Tension
    print(f"\n{'[Chapter D] 軸拉強度 / Tensile Strength':}")
    print(f"  Pnt  = {t.Pnt:.2f} kips              (標稱 Nominal)")
    print(f"  φtPnt = {t.phi_Pnt:.2f} kips   φt = {t.phi_t}  (設計 Design)")

    # ── Flexure x
    print(f"\n{'[Chapter F] 強軸彎矩 / Strong-Axis Flexural Strength':}")
    print(f"  Lp = {fx.Lp/12:.2f} ft   Lr = {fx.Lr/12:.2f} ft   Lb = {beam.Lb/12:.2f} ft")
    print(f"  LTB 區域 : {fx.ltb_zone}")
    print(f"  Mp  = {_kft(fx.Mp):.2f} kip-ft              (塑性彎矩)")
    print(f"  Mn  = {_kft(fx.Mn):.2f} kip-ft              (標稱 Nominal)")
    print(f"  φbMnx = {_kft(fx.phi_Mn):.2f} kip-ft   φb = {fx.phi_b}  (設計 Design)")

    # ── Flexure y
    print(f"\n{'[Chapter F] 弱軸彎矩 / Weak-Axis Flexural Strength':}")
    print(f"  LTB 區域 : {fy.ltb_zone}")
    print(f"  Mp_y  = {_kft(fy.Mp):.2f} kip-ft")
    print(f"  φbMny = {_kft(fy.phi_Mn):.2f} kip-ft   φb = {fy.phi_b}  (設計 Design)")


# ── single load-case check ─────────────────────────────────────────────────

def print_check(bc: BeamColumnLRFD,
                forces: AppliedForces,
                label: str = "") -> InteractionResult:
    """
    Run and print one AISC H1-1 interaction check.
    Returns the InteractionResult for further use.
    """
    res = bc.check(forces)

    header = f"  梁柱互制檢核 / Beam-Column Interaction Check"
    if label:
        header += f"  ── {label}"

    print(f"\n{SEP2}")
    print(header)
    print(SEP2)

    # Forces
    ax_type = _sign(forces.Pu, "拉 T", "壓 C")
    print(f"  外力 / Applied Forces:")
    print(f"    Pu  = {forces.Pu:+.2f} kips  ({ax_type})")
    print(f"    Mux = {_kft(forces.Mux):.2f} kip-ft  "
          f"({forces.Mux:.1f} kip-in)")
    if forces.Muy != 0:
        print(f"    Muy = {_kft(forces.Muy):.2f} kip-ft  "
              f"({forces.Muy:.1f} kip-in)")

    # Capacities
    print(f"\n  設計強度 / Design Strengths:")
    print(f"    φPn   = {res.phi_Pn:.2f} kips")
    print(f"    φbMnx = {_kft(res.phi_Mn_x):.2f} kip-ft")
    if forces.Muy != 0:
        print(f"    φbMny = {_kft(res.phi_Mn_y):.2f} kip-ft")

    # Ratios
    print(f"\n  強度比值 / Demand-to-Capacity Ratios:")
    print(f"    |Pu| / φPn   = {res.ratio_P:.4f}")
    print(f"    |Mux| / φMnx = {res.ratio_Mx:.4f}")
    if forces.Muy != 0:
        print(f"    |Muy| / φMny = {res.ratio_My:.4f}")

    # Governing equation
    if res.equation == "H1-1a":
        eq_str = ("Pu/φcPn + (8/9)(Mux/φbMnx + Muy/φbMny) ≤ 1.0  "
                  "[|Pu|/φcPn ≥ 0.2]")
    else:
        eq_str = ("Pu/(2φcPn) + Mux/φbMnx + Muy/φbMny ≤ 1.0  "
                  "[|Pu|/φcPn < 0.2]")

    print(f"\n  控制公式 / Governing Equation: AISC {res.equation}")
    print(f"    {eq_str}")

    # Result
    ir_bar = _utilization_bar(res.IR)
    status = "PASS ✓  符合規範" if res.passes else "FAIL ✗  不符規範"
    print(f"\n  互制比 / Interaction Ratio (IR) = {res.IR:.4f}")
    print(f"  利用率 / Utilization  = {res.utilization_pct:.1f}%  {ir_bar}")
    print(f"\n  ► {status}")

    return res


# ── multiple load-case table ───────────────────────────────────────────────

def print_load_cases(
    bc: BeamColumnLRFD,
    cases: list[tuple[str, AppliedForces]],
) -> list[InteractionResult]:
    """
    Print a summary table then detail blocks for every load case.
    Returns list of InteractionResult.
    """
    results = [bc.check(f) for _, f in cases]

    # ── Summary table
    print(f"\n{SEP}")
    print("  載重組合彙整表 / Load Case Summary Table")
    print(SEP)
    hdr = f"  {'#':>2}  {'Label':<16}  {'Pu (k)':>8}  {'Mux (k-ft)':>10}  "
    hdr += f"{'Eq.':>6}  {'IR':>6}  {'判定':>8}"
    print(hdr)
    print("  " + "-" * 62)
    for i, ((lbl, f), r) in enumerate(zip(cases, results), 1):
        tag = "PASS ✓" if r.passes else "FAIL ✗"
        print(f"  {i:>2}  {lbl:<16}  {f.Pu:>8.1f}  "
              f"{_kft(f.Mux):>10.1f}  "
              f"{r.equation:>6}  {r.IR:>6.4f}  {tag:>8}")

    # ── Detail per case
    for lbl, f in cases:
        print_check(bc, f, label=lbl)

    return results


# ── helpers ────────────────────────────────────────────────────────────────

def _utilization_bar(ir: float, width: int = 20) -> str:
    """ASCII progress bar for utilization ratio."""
    filled = min(int(ir * width), width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}]"
