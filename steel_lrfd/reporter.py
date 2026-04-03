"""
Formatted text report for AISC LRFD beam-column check results (metric).
Forces in kN, moments in kN·m, stresses in MPa, lengths in mm / m.
"""

from __future__ import annotations

from .core import BeamColumnLRFD, AppliedForces, InteractionResult

SEP  = "=" * 66
SEP2 = "-" * 66


def _sign(v: float) -> str:
    return "拉 T" if v >= 0 else "壓 C"


# ── section + strength summary ────────────────────────────────────────────────

def print_member_summary(bc: BeamColumnLRFD) -> None:
    sec, mat, col, beam = bc.sec, bc.mat, bc.col, bc.beam
    c  = bc.compression
    t  = bc.tension
    fx = bc.flexure_x
    fy = bc.flexure_y

    print(SEP)
    print("  AISC 360-16 LRFD  鋼梁柱設計報告")
    print("  Steel Beam-Column Design Report  (公制 Metric)")
    print(SEP)

    print(f"\n截面 / Section  : {sec.name}  ({sec.category})")
    print(f"材料 / Material : Fy = {mat.Fy:.0f} MPa,  Fu = {mat.Fu:.0f} MPa,  E = {mat.E:.0f} MPa")

    print(f"\n截面性質 / Section Properties (mm, mm², mm⁴, mm³)")
    print(f"  d={sec.d:.0f}  bf={sec.bf:.0f}  tw={sec.tw}  tf={sec.tf}  (mm)")
    print(f"  A  = {sec.A:,.0f} mm²  ({sec.A/100:.1f} cm²)")
    print(f"  Ix = {sec.Ix:.3e} mm⁴   Sx = {sec.Sx:,.0f} mm³   Zx = {sec.Zx:,.0f} mm³")
    print(f"  rx = {sec.rx:.1f} mm")
    print(f"  Iy = {sec.Iy:.3e} mm⁴   Sy = {sec.Sy:,.0f} mm³   Zy = {sec.Zy:,.0f} mm³")
    print(f"  ry = {sec.ry:.1f} mm")
    print(f"  J  = {sec.J:.3e} mm⁴   Cw = {sec.Cw:.3e} mm⁶")

    print(f"\n計算參數 / Design Parameters")
    print(f"  KxLx = {col.Kx}×{col.Lx/1000:.2f} m = {col.KxLx:.0f} mm   "
          f"KyLy = {col.Ky}×{col.Ly/1000:.2f} m = {col.KyLy:.0f} mm")
    print(f"  Lb   = {beam.Lb/1000:.2f} m = {beam.Lb:.0f} mm   Cb = {beam.Cb:.2f}")

    print(f"\n[Chapter E] 軸壓強度 / Compressive Strength")
    print(f"  KL/rx = {c.KL_r_x:.2f}   KL/ry = {c.KL_r_y:.2f}   "
          f"控制 KL/r = {c.KL_r:.2f}  (限制 4.71√(E/Fy) = {c.KL_r_limit:.2f})")
    print(f"  Fe  = {c.Fe:.2f} MPa   Fcr = {c.Fcr:.2f} MPa   [{c.buckling_mode}]")
    print(f"  Pn  = {c.Pn:.2f} kN              (標稱 Nominal)")
    print(f"  φcPn = {c.phi_Pn:.2f} kN   φc = {c.phi_c}  (設計 Design)")

    print(f"\n[Chapter D] 軸拉強度 / Tensile Strength")
    print(f"  Pnt  = {t.Pnt:.2f} kN              (標稱 Nominal)")
    print(f"  φtPnt = {t.phi_Pnt:.2f} kN   φt = {t.phi_t}  (設計 Design)")

    print(f"\n[Chapter F] 強軸彎矩 / Strong-Axis Flexural Strength")
    print(f"  Lp = {fx.Lp/1000:.3f} m   Lr = {fx.Lr/1000:.3f} m   Lb = {beam.Lb/1000:.3f} m")
    print(f"  LTB 區域 : {fx.ltb_zone}")
    print(f"  Mp  = {fx.Mp:.2f} kN·m              (塑性彎矩)")
    print(f"  Mn  = {fx.Mn:.2f} kN·m              (標稱 Nominal)")
    print(f"  φbMnx = {fx.phi_Mn:.2f} kN·m   φb = {fx.phi_b}  (設計 Design)")

    print(f"\n[Chapter F] 弱軸彎矩 / Weak-Axis Flexural Strength")
    print(f"  LTB 區域 : {fy.ltb_zone}")
    print(f"  Mp_y  = {fy.Mp:.2f} kN·m")
    print(f"  φbMny = {fy.phi_Mn:.2f} kN·m   φb = {fy.phi_b}  (設計 Design)")


# ── single load-case check ────────────────────────────────────────────────────

def print_check(bc: BeamColumnLRFD,
                forces: AppliedForces,
                label: str = "") -> InteractionResult:
    res = bc.check(forces)

    hdr = "  梁柱互制檢核 / Beam-Column Interaction Check"
    if label:
        hdr += f"  ── {label}"

    print(f"\n{SEP2}")
    print(hdr)
    print(SEP2)

    print(f"  外力 / Applied Forces:")
    print(f"    Pu  = {forces.Pu:+.2f} kN  ({_sign(forces.Pu)})")
    print(f"    Mux = {forces.Mux:.2f} kN·m  (強軸 Strong axis)")
    if forces.Muy != 0:
        print(f"    Muy = {forces.Muy:.2f} kN·m  (弱軸 Weak axis)")

    print(f"\n  設計強度 / Design Strengths:")
    print(f"    φPn   = {res.phi_Pn:.2f} kN")
    print(f"    φbMnx = {res.phi_Mn_x:.2f} kN·m")
    if forces.Muy != 0:
        print(f"    φbMny = {res.phi_Mn_y:.2f} kN·m")

    print(f"\n  強度比值 / Demand-to-Capacity Ratios:")
    print(f"    |Pu|  / φPn   = {res.ratio_P:.4f}")
    print(f"    |Mux| / φMnx = {res.ratio_Mx:.4f}")
    if forces.Muy != 0:
        print(f"    |Muy| / φMny = {res.ratio_My:.4f}")

    if res.equation == "H1-1a":
        eq_str = "Pu/φcPn + (8/9)(Mux/φbMnx + Muy/φbMny) ≤ 1.0  [|Pu/φcPn| ≥ 0.2]"
    else:
        eq_str = "Pu/(2φcPn) + Mux/φbMnx + Muy/φbMny ≤ 1.0  [|Pu/φcPn| < 0.2]"

    print(f"\n  控制公式 / Governing Equation: AISC {res.equation}")
    print(f"    {eq_str}")

    status = "PASS ✓  符合規範" if res.passes else "FAIL ✗  不符規範"
    bar = _bar(res.IR)
    print(f"\n  互制比 / Interaction Ratio (IR) = {res.IR:.4f}")
    print(f"  利用率 / Utilization  = {res.utilization_pct:.1f}%  {bar}")
    print(f"\n  ► {status}")

    return res


# ── multiple load-case table ──────────────────────────────────────────────────

def print_load_cases(
    bc: BeamColumnLRFD,
    cases: list[tuple[str, AppliedForces]],
) -> list[InteractionResult]:
    results = [bc.check(f) for _, f in cases]

    print(f"\n{SEP}")
    print("  載重組合彙整表 / Load Case Summary Table")
    print(SEP)
    print(f"  {'#':>2}  {'Label':<18}  {'Pu (kN)':>9}  {'Mux (kN·m)':>11}  "
          f"{'Eq.':>6}  {'IR':>6}  {'判定':>8}")
    print("  " + "-" * 64)
    for i, ((lbl, f), r) in enumerate(zip(cases, results), 1):
        tag = "PASS ✓" if r.passes else "FAIL ✗"
        print(f"  {i:>2}  {lbl:<18}  {f.Pu:>9.1f}  {f.Mux:>11.2f}  "
              f"{r.equation:>6}  {r.IR:>6.4f}  {tag:>8}")

    for lbl, f in cases:
        print_check(bc, f, label=lbl)

    return results


def _bar(ir: float, width: int = 20) -> str:
    filled = min(int(ir * width), width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"
