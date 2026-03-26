"""
AISC LRFD 鋼梁柱設計檢核程式（公制版）
Steel Beam-Column LRFD Check – Metric Edition

Usage
-----
互動式輸入：
    python run_check.py

執行內建範例：
    python run_check.py --example            (含 P-M 互制圖)
    python run_check.py --example --no-plot  (純文字報表)

程式呼叫：
    from run_check import run_design_check
    run_design_check(...)
"""

from __future__ import annotations

from steel_lrfd import (
    get_section, list_sections, list_sections_by_category,
    Material, ColumnParams, BeamParams, AppliedForces,
    BeamColumnLRFD, plot_pm_diagram,
)
from steel_lrfd.reporter import print_member_summary, print_load_cases


# ─────────────────────────────────────────────────────────────────────────────
# Programmatic API
# ─────────────────────────────────────────────────────────────────────────────

def run_design_check(
    section_name: str,
    Fy: float,
    Kx: float, Lx_m: float,
    Ky: float, Ly_m: float,
    Lb_m: float, Cb: float,
    load_cases: list[tuple[str, float, float, float]],
    *,
    Fu: float = 490.0,
    E:  float = 200_000.0,
    plot: bool = False,
    save_path: str | None = "PM_interaction_diagram.png",
) -> None:
    """
    Run a full AISC LRFD beam-column check and print the report.

    Parameters
    ----------
    section_name : str   e.g. "H300x300x10x15"
    Fy, Fu, E    : float 材料強度 (MPa)
    Kx, Lx_m    : float 強軸有效長度因子 K 與無側撐長度 (m)
    Ky, Ly_m    : float 弱軸有效長度因子 K 與無側撐長度 (m)
    Lb_m, Cb    : float LTB 無側撐長度 (m) 與修正因子
    load_cases   : list of (label, Pu_kN, Mux_kNm, Muy_kNm)
                   Pu > 0 = 拉力(T),  Pu < 0 = 壓力(C)
    """
    sec  = get_section(section_name)
    mat  = Material(Fy=Fy, Fu=Fu, E=E)
    col  = ColumnParams.from_m(Kx=Kx, Lx_m=Lx_m, Ky=Ky, Ly_m=Ly_m)
    beam = BeamParams.from_m(Lb_m=Lb_m, Cb=Cb)
    bc   = BeamColumnLRFD(sec, mat, col, beam)

    print_member_summary(bc)

    cases: list[tuple[str, AppliedForces]] = [
        (lbl, AppliedForces(Pu=Pu, Mux=Mux, Muy=Muy))
        for lbl, Pu, Mux, Muy in load_cases
    ]
    print_load_cases(bc, cases)

    if plot:
        plot_pm_diagram(bc, cases, save_path=save_path, show=True)


# ─────────────────────────────────────────────────────────────────────────────
# Interactive CLI
# ─────────────────────────────────────────────────────────────────────────────

def _ask(prompt: str, default, cast=float):
    raw = input(f"  {prompt} [{default}]: ").strip()
    return cast(raw) if raw else cast(default)


def interactive_check() -> None:
    print("\n" + "=" * 66)
    print("  AISC LRFD 鋼梁柱互動式設計檢核（公制）")
    print("  Interactive Steel Beam-Column Design Check – Metric")
    print("=" * 66)

    # ── Section
    print("\n可用截面 / Available sections:")
    for cat in ("HW", "HN"):
        secs = list_sections_by_category(cat)
        print(f"  {cat}: {', '.join(secs)}")

    raw = input("\n  輸入截面名稱 / Enter section name [H300x300x10x15]: ").strip()
    sec_name = raw if raw else "H300x300x10x15"

    # ── Material
    print("\n--- 材料參數 / Material (MPa) ---")
    Fy = _ask("Fy (MPa)", 355)
    Fu = _ask("Fu (MPa)", 490)
    E  = _ask("E  (MPa)", 200000)

    # ── Geometry
    print("\n--- 幾何參數 / Geometry ---")
    Kx    = _ask("Kx (強軸有效長度因子)", 1.0)
    Lx_m  = _ask("Lx (m, 強軸無側撐長)", 5.0)
    Ky    = _ask("Ky (弱軸有效長度因子)", 1.0)
    Ly_m  = _ask("Ly (m, 弱軸無側撐長)", 5.0)
    Lb_m  = _ask("Lb (m, 側扭挫屈無側撐長)", Ly_m)
    Cb    = _ask("Cb (LTB 修正因子, 1.0=保守)", 1.0)

    # ── Load cases
    print("\n--- 外力組合 / Load Cases ---")
    print("  Pu > 0 = 拉力(T),  Pu < 0 = 壓力(C)")
    print("  輸入空白標籤結束\n")

    load_cases: list[tuple[str, float, float, float]] = []
    idx = 1
    while True:
        lbl = input(f"  載重組合 {idx} 名稱 (Enter=結束): ").strip()
        if not lbl:
            if not load_cases:
                print("  (使用預設載重組合)")
                load_cases = [
                    ("1.2D+1.6L",  -2000,  300,  0),
                    ("1.2D+1.6L+W",-1200,  420,  0),
                    ("0.9D+1.0W",   -500,  500,  0),
                    ("拉力組合",     800,  200,  0),
                ]
            break
        Pu  = _ask("  Pu  (kN)", -1000.0)
        Mux = _ask("  Mux (kN·m, 強軸)", 300.0)
        Muy = _ask("  Muy (kN·m, 弱軸, 可為0)", 0.0)
        load_cases.append((lbl, Pu, Mux, Muy))
        idx += 1

    do_plot = input("\n  繪製 P-M 互制圖？[Y/n]: ").strip().lower()
    run_design_check(
        section_name=sec_name,
        Fy=Fy, Fu=Fu, E=E,
        Kx=Kx, Lx_m=Lx_m,
        Ky=Ky, Ly_m=Ly_m,
        Lb_m=Lb_m, Cb=Cb,
        load_cases=load_cases,
        plot=(do_plot != "n"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Preset example – H300×300×10×15, Fy=355 MPa, KL=5 m
# ─────────────────────────────────────────────────────────────────────────────

def run_example(plot: bool = True) -> None:
    run_design_check(
        section_name = "H300x300x10x15",
        Fy=355, Fu=490, E=200_000,
        Kx=1.0, Lx_m=5.0,
        Ky=1.0, Ly_m=5.0,
        Lb_m=3.0, Cb=1.0,
        load_cases=[
            # (label,       Pu kN,  Mux kN·m,  Muy kN·m)
            ("1.2D+1.6L",  -2000,    280,        0),
            ("1.2D+1.6L+W",-1200,    420,        0),
            ("0.9D+1.0W",   -500,    500,        0),
            ("拉力組合",      800,    200,        0),
        ],
        plot=plot,
    )


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if "--example" in sys.argv:
        run_example(plot="--no-plot" not in sys.argv)
    else:
        try:
            interactive_check()
        except (KeyboardInterrupt, EOFError):
            print("\n\n(已取消 / Cancelled)")
