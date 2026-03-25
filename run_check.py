"""
AISC LRFD 鋼梁柱設計檢核程式
Steel Beam-Column LRFD Check – interactive entry point

Usage
-----
直接執行本檔案，依提示輸入截面、幾何參數與外力組合：
    python run_check.py

或在其他腳本中直接呼叫：
    from run_check import run_design_check
    run_design_check(...)
"""

from __future__ import annotations

from steel_lrfd import (
    get_section, list_sections,
    Material, ColumnParams, BeamParams, AppliedForces,
    BeamColumnLRFD,
)
from steel_lrfd.reporter import print_member_summary, print_load_cases


# ─────────────────────────────────────────────────────────────────────────────
# Programmatic API
# ─────────────────────────────────────────────────────────────────────────────

def run_design_check(
    section_name: str,
    Fy: float,
    Kx: float, Lx_ft: float,
    Ky: float, Ly_ft: float,
    Lb_ft: float, Cb: float,
    load_cases: list[tuple[str, float, float, float]],
    *,
    Fu: float = 65.0,
    E: float = 29000.0,
) -> None:
    """
    Run a full AISC LRFD beam-column check and print the report.

    Parameters
    ----------
    section_name : str
        W-section name, e.g. "W14x82"
    Fy, Fu, E    : float
        Steel material properties (ksi)
    Kx, Lx_ft   : float
        Effective length factor and unbraced length (ft), strong axis
    Ky, Ly_ft   : float
        Effective length factor and unbraced length (ft), weak axis
    Lb_ft, Cb   : float
        Unbraced length for LTB (ft) and Cb factor
    load_cases   : list of (label, Pu_kips, Mux_kip_ft, Muy_kip_ft)
        Pu > 0 = tension,  Pu < 0 = compression
    """
    sec  = get_section(section_name)
    mat  = Material(Fy=Fy, Fu=Fu, E=E)
    col  = ColumnParams.from_ft(Kx=Kx, Lx_ft=Lx_ft, Ky=Ky, Ly_ft=Ly_ft)
    beam = BeamParams.from_ft(Lb_ft=Lb_ft, Cb=Cb)
    bc   = BeamColumnLRFD(sec, mat, col, beam)

    print_member_summary(bc)

    cases: list[tuple[str, AppliedForces]] = [
        (lbl, AppliedForces.from_kip_ft(Pu, Mux, Muy))
        for lbl, Pu, Mux, Muy in load_cases
    ]
    print_load_cases(bc, cases)


# ─────────────────────────────────────────────────────────────────────────────
# Interactive CLI
# ─────────────────────────────────────────────────────────────────────────────

def _ask(prompt: str, default, cast=float):
    raw = input(f"  {prompt} [{default}]: ").strip()
    return cast(raw) if raw else cast(default)


def interactive_check() -> None:
    print("\n" + "=" * 64)
    print("  AISC LRFD 鋼梁柱互動式設計檢核")
    print("  Interactive Steel Beam-Column Design Check")
    print("=" * 64)

    # ── Section selection
    print("\n可用截面 / Available sections:")
    secs = list_sections()
    for i, s in enumerate(secs, 1):
        print(f"  {i:>2}. {s}")

    raw = input("\n  輸入截面名稱 / Enter section name [W14x82]: ").strip()
    sec_name = raw if raw else "W14x82"

    # ── Material
    print("\n--- 材料參數 / Material ---")
    Fy = _ask("Fy (ksi)", 50)
    Fu = _ask("Fu (ksi)", 65)
    E  = _ask("E  (ksi)", 29000)

    # ── Geometry
    print("\n--- 幾何參數 / Geometry ---")
    Kx    = _ask("Kx (強軸有效長度因子 strong-axis K)", 1.0)
    Lx_ft = _ask("Lx (ft, 強軸無側撐長 strong-axis unbraced length)", 15.0)
    Ky    = _ask("Ky (弱軸有效長度因子 weak-axis K)", 1.0)
    Ly_ft = _ask("Ly (ft, 弱軸無側撐長 weak-axis unbraced length)", 15.0)
    Lb_ft = _ask("Lb (ft, 側扭挫屈無側撐長 LTB unbraced length)", Ly_ft)
    Cb    = _ask("Cb (LTB 修正因子 modification factor, 1.0=保守)", 1.0)

    # ── Load cases
    print("\n--- 外力組合 / Load Cases ---")
    print("  Pu > 0 = 拉力(Tension),  Pu < 0 = 壓力(Compression)")
    print("  輸入空白標籤結束 / Enter blank label to finish\n")

    load_cases: list[tuple[str, float, float, float]] = []
    idx = 1
    while True:
        lbl = input(f"  載重組合 {idx} 名稱 / Label (Enter=done): ").strip()
        if not lbl:
            if not load_cases:
                print("  (使用預設載重組合 / Using default load cases)")
                load_cases = [
                    ("DL+LL (案例1)",  -500.0,  180.0,  0.0),
                    ("DL+LL (案例2)",  -300.0,  280.0,  0.0),
                    ("DL+LL+W (案例3)", -150.0, 320.0,  0.0),
                    ("拉力+彎矩",        200.0,  160.0,  0.0),
                ]
            break
        Pu  = _ask(f"  Pu  (kips)", -300.0)
        Mux = _ask(f"  Mux (kip-ft, 強軸)", 200.0)
        Muy = _ask(f"  Muy (kip-ft, 弱軸, 可為0)", 0.0)
        load_cases.append((lbl, Pu, Mux, Muy))
        idx += 1

    run_design_check(
        section_name=sec_name,
        Fy=Fy, Fu=Fu, E=E,
        Kx=Kx, Lx_ft=Lx_ft,
        Ky=Ky, Ly_ft=Ly_ft,
        Lb_ft=Lb_ft, Cb=Cb,
        load_cases=load_cases,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Preset example (run without interaction)
# ─────────────────────────────────────────────────────────────────────────────

def run_example() -> None:
    """Demonstrate programmatic API with W14x82 example."""
    run_design_check(
        section_name = "W14x82",
        Fy=50, Fu=65, E=29000,
        Kx=1.0, Lx_ft=15.0,
        Ky=1.0, Ly_ft=15.0,
        Lb_ft=10.0, Cb=1.0,
        load_cases=[
            # (label,          Pu kips,  Mux kip-ft,  Muy kip-ft)
            ("1.2D+1.6L (壓+彎)", -500,     208.3,        0.0),
            ("1.2D+1.6L+W",       -300,     291.7,        0.0),
            ("0.9D+1.0W",         -100,     316.7,        0.0),
            ("拉力組合",           +200,     166.7,        0.0),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if "--example" in sys.argv:
        run_example()
    else:
        try:
            interactive_check()
        except (KeyboardInterrupt, EOFError):
            print("\n\n(已取消 / Cancelled)")
