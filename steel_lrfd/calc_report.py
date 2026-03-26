"""
HTML Calculation Report Generator
===================================
Generates a fully self-contained HTML calculation report (計算書)
for an AISC 360-16 LRFD beam-column design check.

Usage
-----
    from steel_lrfd.calc_report import generate_html_report
    generate_html_report(bc, load_cases, save_path="report.html")
"""

from __future__ import annotations

import base64
import io
import math
import os
import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core import BeamColumnLRFD, AppliedForces


# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px; color: #212121;
    background: #f5f5f5;
    padding: 24px;
}
.page {
    max-width: 960px; margin: 0 auto;
    background: #fff;
    padding: 40px 48px;
    box-shadow: 0 2px 8px rgba(0,0,0,.15);
}
h1 {
    font-size: 18px; font-weight: 700;
    border-bottom: 3px solid #1565C0;
    padding-bottom: 8px; margin-bottom: 16px;
    color: #1565C0;
}
h2 {
    font-size: 14px; font-weight: 700;
    margin: 24px 0 8px;
    padding: 4px 10px;
    background: #E3F2FD;
    border-left: 4px solid #1565C0;
    color: #0D47A1;
}
h3 {
    font-size: 13px; font-weight: 700;
    margin: 16px 0 6px;
    color: #37474F;
}
.meta {
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 4px 24px; margin-bottom: 20px;
}
.meta-row { display: contents; }
.meta-label { color: #546E7A; font-size: 12px; }
.meta-value { font-weight: 600; }

table {
    width: 100%; border-collapse: collapse;
    margin: 8px 0 16px;
    font-size: 12px;
}
th {
    background: #1565C0; color: #fff;
    padding: 6px 10px; text-align: left;
    font-weight: 600;
}
td {
    padding: 5px 10px;
    border-bottom: 1px solid #E0E0E0;
}
tr:nth-child(even) td { background: #F8F9FA; }
tr.highlight td { background: #FFF9C4; font-weight: 600; }

.formula {
    background: #F3F4F6;
    border: 1px solid #CFD8DC;
    border-radius: 4px;
    padding: 10px 14px;
    margin: 6px 0;
    font-family: "Courier New", monospace;
    font-size: 12px;
    line-height: 1.8;
}
.formula .var { color: #1565C0; font-style: italic; }
.formula .result { color: #C62828; font-weight: 700; }
.formula .note { color: #546E7A; font-size: 11px; }

.pass {
    display: inline-block;
    background: #E8F5E9; color: #2E7D32;
    border: 1px solid #A5D6A7;
    border-radius: 4px; padding: 3px 10px;
    font-weight: 700;
}
.fail {
    display: inline-block;
    background: #FBE9E7; color: #BF360C;
    border: 1px solid #FFAB91;
    border-radius: 4px; padding: 3px 10px;
    font-weight: 700;
}
.ir-bar-wrap {
    width: 160px; height: 12px;
    background: #E0E0E0; border-radius: 6px;
    display: inline-block; vertical-align: middle;
    overflow: hidden; margin-left: 8px;
}
.ir-bar {
    height: 100%; border-radius: 6px;
}
.section-divider {
    border: none; border-top: 1px solid #E0E0E0;
    margin: 20px 0;
}
.diagram { text-align: center; margin: 16px 0; }
.diagram img { max-width: 100%; border: 1px solid #E0E0E0; border-radius: 4px; }
footer {
    margin-top: 32px;
    padding-top: 12px;
    border-top: 1px solid #E0E0E0;
    font-size: 11px; color: #9E9E9E;
    text-align: center;
}
@media print {
    body { background: #fff; padding: 0; }
    .page { box-shadow: none; padding: 16px; }
}
"""


# ── helpers ───────────────────────────────────────────────────────────────────

def _fmt(v: float, dec: int = 2) -> str:
    return f"{v:,.{dec}f}"

def _pct(v: float) -> str:
    return f"{v*100:.1f}%"

def _sign_str(pu: float) -> str:
    return "Tension (T)" if pu >= 0 else "Compression (C)"

def _tag(passes: bool) -> str:
    return '<span class="pass">&#10003; PASS</span>' if passes else '<span class="fail">&#10007; FAIL</span>'

def _ir_bar(ir: float) -> str:
    pct = min(ir * 100, 100)
    color = "#2E7D32" if ir <= 1.0 else "#C62828"
    return (f'<span class="ir-bar-wrap"><span class="ir-bar" '
            f'style="width:{pct:.1f}%;background:{color}"></span></span>')

def _embed_png(path: str) -> str:
    """Read PNG from path and return base64 data URI."""
    try:
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        return f"data:image/png;base64,{b64}"
    except FileNotFoundError:
        return ""


# ── report builder ─────────────────────────────────────────────────────────────

def generate_html_report(
    bc: "BeamColumnLRFD",
    load_cases: "list[tuple[str, AppliedForces]] | None" = None,
    *,
    save_path: str = "calculation_report.html",
    diagram_png: str | None = "PM_interaction_diagram.png",
    project_name: str = "",
    engineer: str = "",
    checked_by: str = "",
) -> str:
    """
    Generate a self-contained HTML calculation report.

    Parameters
    ----------
    bc           : BeamColumnLRFD (already computed)
    load_cases   : list of (label, AppliedForces)
    save_path    : output HTML file path
    diagram_png  : path to P-M diagram PNG to embed (None = skip)
    project_name : optional project name for the header
    engineer     : designer name
    checked_by   : checker name
    """
    from .core import AppliedForces

    load_cases = load_cases or []
    sec   = bc.sec
    mat   = bc.mat
    col   = bc.col
    beam  = bc.beam
    c     = bc.compression
    t     = bc.tension
    fx    = bc.flexure_x
    fy    = bc.flexure_y

    parts: list[str] = []

    def w(html: str) -> None:
        parts.append(html)

    def row(label: str, *vals: str) -> str:
        tds = "".join(f"<td>{v}</td>" for v in vals)
        return f"<tr><td><b>{label}</b></td>{tds}</tr>"

    def frow(label: str, *vals: str, hl: bool = False) -> str:
        cls = ' class="highlight"' if hl else ""
        tds = "".join(f"<td>{v}</td>" for v in vals)
        return f"<tr{cls}><td>{label}</td>{tds}</tr>"

    # ── HTML header ───────────────────────────────────────────────────────────
    w(f"""<!DOCTYPE html><html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AISC LRFD Calculation Report – {sec.name}</title>
<style>{_CSS}</style>
</head>
<body><div class="page">
""")

    # ── title block ───────────────────────────────────────────────────────────
    w(f"""<h1>AISC 360-16 LRFD Steel Beam-Column Calculation Report<br>
<span style="font-size:13px;font-weight:400;color:#546E7A;">
鋼構梁柱設計計算書（公制 Metric Edition）</span></h1>
""")

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    w(f"""<div class="meta">
  <span class="meta-label">Project / 工程名稱</span>
  <span class="meta-value">{project_name or "—"}</span>
  <span class="meta-label">Section / 斷面</span>
  <span class="meta-value">{sec.name}  ({sec.category})</span>
  <span class="meta-label">Material / 材料</span>
  <span class="meta-value">Fy = {mat.Fy:.0f} MPa,  Fu = {mat.Fu:.0f} MPa,  E = {mat.E:.0f} MPa</span>
  <span class="meta-label">Date / 日期</span>
  <span class="meta-value">{now}</span>
  <span class="meta-label">Engineer / 設計者</span>
  <span class="meta-value">{engineer or "—"}</span>
  <span class="meta-label">Checked by / 審核者</span>
  <span class="meta-value">{checked_by or "—"}</span>
</div>
""")

    # ── 1. Section properties ─────────────────────────────────────────────────
    w('<h2>1. Section Properties  截面性質</h2>')
    w(f"""<p style="margin-bottom:8px">
Section: <b>{sec.name}</b> &nbsp;|&nbsp;
d = {sec.d:.0f} mm,  b<sub>f</sub> = {sec.bf:.0f} mm,
t<sub>w</sub> = {sec.tw} mm,  t<sub>f</sub> = {sec.tf} mm
</p>""")

    w("""<table>
<tr><th>Property</th><th>Symbol</th><th>Value</th><th>Unit</th></tr>""")
    props = [
        ("Cross-sectional area", "A",  f"{sec.A:,.1f}", "mm²"),
        ("Moment of inertia (strong)", "I<sub>x</sub>", f"{sec.Ix:.4e}", "mm⁴"),
        ("Elastic modulus (strong)",   "S<sub>x</sub>", f"{sec.Sx:,.0f}", "mm³"),
        ("Plastic modulus (strong)",   "Z<sub>x</sub>", f"{sec.Zx:,.0f}", "mm³"),
        ("Radius of gyration (strong)","r<sub>x</sub>", f"{sec.rx:.2f}", "mm"),
        ("Moment of inertia (weak)",   "I<sub>y</sub>", f"{sec.Iy:.4e}", "mm⁴"),
        ("Elastic modulus (weak)",     "S<sub>y</sub>", f"{sec.Sy:,.0f}", "mm³"),
        ("Plastic modulus (weak)",     "Z<sub>y</sub>", f"{sec.Zy:,.0f}", "mm³"),
        ("Radius of gyration (weak)",  "r<sub>y</sub>", f"{sec.ry:.2f}", "mm"),
        ("Torsion constant",           "J",   f"{sec.J:.4e}", "mm⁴"),
        ("Warping constant",           "C<sub>w</sub>", f"{sec.Cw:.4e}", "mm⁶"),
        ("Effective radius (LTB)",     "r<sub>ts</sub>", f"{sec.rts:.2f}", "mm"),
        ("Dist. between flange centroids", "h<sub>o</sub>", f"{sec.ho:.1f}", "mm"),
    ]
    for name, sym, val, unit in props:
        w(f"<tr><td>{name}</td><td><i>{sym}</i></td><td><b>{val}</b></td><td>{unit}</td></tr>")
    w("</table>")

    # ── 2. Design parameters ──────────────────────────────────────────────────
    w('<h2>2. Design Parameters  設計參數</h2>')
    w(f"""<div class="formula">
<span class="var">Kx</span> = {col.Kx},  Lx = {col.Lx/1000:.2f} m  →
<span class="var">KxLx</span> = {col.KxLx/1000:.3f} m = {col.KxLx:.0f} mm<br>
<span class="var">Ky</span> = {col.Ky},  Ly = {col.Ly/1000:.2f} m  →
<span class="var">KyLy</span> = {col.KyLy/1000:.3f} m = {col.KyLy:.0f} mm<br>
<span class="var">Lb</span> = {beam.Lb/1000:.3f} m = {beam.Lb:.0f} mm  (unbraced length for LTB)<br>
<span class="var">Cb</span> = {beam.Cb:.2f}  (moment gradient factor)
</div>""")

    # ── 3. Chapter E – Compression ────────────────────────────────────────────
    w('<h2>3. Chapter E – Compressive Strength  軸壓強度</h2>')
    w(f"""<div class="formula">
KL/r<sub>x</sub> = KxLx / r<sub>x</sub> = {col.KxLx:.0f} / {sec.rx:.2f}
  = <span class="var">{c.KL_r_x:.2f}</span><br>
KL/r<sub>y</sub> = KyLy / r<sub>y</sub> = {col.KyLy:.0f} / {sec.ry:.2f}
  = <span class="var">{c.KL_r_y:.2f}</span><br>
<b>KL/r (governs)</b> = max(KL/r<sub>x</sub>, KL/r<sub>y</sub>)
  = <span class="result">{c.KL_r:.2f}</span><br><br>

Limit &nbsp; 4.71√(E/Fy) = 4.71 × √({mat.E:.0f}/{mat.Fy:.0f})
  = <span class="var">{c.KL_r_limit:.2f}</span><br><br>

Elastic buckling stress (Eq. E3-4):<br>
&nbsp;&nbsp; Fe = π²E / (KL/r)² = π² × {mat.E:.0f} / {c.KL_r:.2f}²
  = <span class="var">{c.Fe:.2f} MPa</span><br><br>

{'KL/r ≤ limit → Inelastic/squash (Eq. E3-2)' if c.KL_r <= c.KL_r_limit else 'KL/r > limit → Elastic buckling (Eq. E3-3)'}<br>
{'&nbsp;&nbsp; Fcr = 0.658^(Fy/Fe) × Fy' if c.KL_r <= c.KL_r_limit else '&nbsp;&nbsp; Fcr = 0.877 × Fe'}<br>
&nbsp;&nbsp; Fcr = <span class="result">{c.Fcr:.2f} MPa</span>
&nbsp; [{c.buckling_mode}]<br><br>

Pn = Fcr × A = {c.Fcr:.2f} × {sec.A:,.0f} / 1000
  = <span class="result">{c.Pn:.2f} kN</span><br>
<b>φ<sub>c</sub>Pn</b> = {c.phi_c} × {c.Pn:.2f}
  = <span class="result">{c.phi_Pn:.2f} kN</span>
</div>""")

    # ── 4. Chapter D – Tension ────────────────────────────────────────────────
    w('<h2>4. Chapter D – Tensile Strength  軸拉強度</h2>')
    w(f"""<div class="formula">
Pnt = Fy × Ag = {mat.Fy:.0f} × {sec.A:,.0f} / 1000
  = <span class="result">{t.Pnt:.2f} kN</span> &nbsp; (gross section yielding)<br>
<b>φ<sub>t</sub>Pnt</b> = {t.phi_t} × {t.Pnt:.2f}
  = <span class="result">{t.phi_Pnt:.2f} kN</span>
</div>""")

    # ── 5. Chapter F – Strong-axis flexure ────────────────────────────────────
    w('<h2>5. Chapter F – Strong-Axis Flexural Strength  強軸彎矩強度</h2>')
    w(f"""<div class="formula">
Plastic moment:<br>
&nbsp;&nbsp; Mp = Fy × Zx = {mat.Fy:.0f} × {sec.Zx:,.0f} / 1e6
  = <span class="var">{fx.Mp:.2f} kN·m</span><br><br>

Lp (Eq. F2-5):<br>
&nbsp;&nbsp; Lp = 1.76 × r<sub>y</sub> × √(E/Fy)
  = 1.76 × {sec.ry:.2f} × √({mat.E:.0f}/{mat.Fy:.0f})
  = <span class="var">{fx.Lp/1000:.3f} m</span><br><br>

Lr (Eq. F2-6):<br>
&nbsp;&nbsp; rts = {sec.rts:.2f} mm<br>
&nbsp;&nbsp; Lr = <span class="var">{fx.Lr/1000:.3f} m</span><br><br>

Unbraced length: Lb = {beam.Lb/1000:.3f} m<br>
Lp = {fx.Lp/1000:.3f} m,  Lr = {fx.Lr/1000:.3f} m<br>
<b>LTB Zone: <span class="result">{fx.ltb_zone}</span></b><br><br>

{'Lb ≤ Lp → No LTB, Mn = Mp' if beam.Lb <= fx.Lp else
 ('Lp < Lb ≤ Lr → Inelastic LTB (Eq. F2-2)' if beam.Lb <= fx.Lr else
  'Lb > Lr → Elastic LTB (Eq. F2-3/F2-4)')}<br>
Mn  = <span class="result">{fx.Mn:.2f} kN·m</span><br>
<b>φ<sub>b</sub>Mnx</b> = {fx.phi_b} × {fx.Mn:.2f}
  = <span class="result">{fx.phi_Mn:.2f} kN·m</span>
</div>""")

    # ── 6. Chapter F – Weak-axis flexure ──────────────────────────────────────
    w('<h2>6. Chapter F – Weak-Axis Flexural Strength  弱軸彎矩強度</h2>')
    w(f"""<div class="formula">
Mp<sub>y</sub> = min(Fy·Zy, 1.6·Fy·Sy)<br>
&nbsp;&nbsp; = min({mat.Fy:.0f}×{sec.Zy:,.0f}, 1.6×{mat.Fy:.0f}×{sec.Sy:,.0f}) / 1e6<br>
&nbsp;&nbsp; = <span class="var">{fy.Mp:.2f} kN·m</span><br><br>

Weak-axis bending: No LTB → Mn<sub>y</sub> = Mp<sub>y</sub><br>
<b>φ<sub>b</sub>Mny</b> = {fy.phi_b} × {fy.Mn:.2f}
  = <span class="result">{fy.phi_Mn:.2f} kN·m</span>
</div>""")

    # ── 7. Strength summary table ─────────────────────────────────────────────
    w('<h2>7. Design Strength Summary  設計強度彙整</h2>')
    w("""<table>
<tr><th>Mode</th><th>Nominal Strength</th><th>phi Factor</th><th>Design Strength</th></tr>""")
    rows_s = [
        ("Compression  φ<sub>c</sub>Pn",  f"{c.Pn:.2f} kN",    f"φ<sub>c</sub> = {c.phi_c}", f"<b>{c.phi_Pn:.2f} kN</b>"),
        ("Tension  φ<sub>t</sub>Pnt",      f"{t.Pnt:.2f} kN",   f"φ<sub>t</sub> = {t.phi_t}", f"<b>{t.phi_Pnt:.2f} kN</b>"),
        ("Strong-axis Flexure  φ<sub>b</sub>Mnx", f"{fx.Mn:.2f} kN·m", f"φ<sub>b</sub> = {fx.phi_b}", f"<b>{fx.phi_Mn:.2f} kN·m</b>"),
        ("Weak-axis Flexure  φ<sub>b</sub>Mny",   f"{fy.Mn:.2f} kN·m", f"φ<sub>b</sub> = {fy.phi_b}", f"<b>{fy.phi_Mn:.2f} kN·m</b>"),
    ]
    for r_ in rows_s:
        w(f"<tr><td>{r_[0]}</td><td>{r_[1]}</td><td>{r_[2]}</td><td>{r_[3]}</td></tr>")
    w("</table>")

    # ── 8. Chapter H1 – Beam-column interaction ───────────────────────────────
    w('<h2>8. Chapter H1 – Beam-Column Interaction Check  梁柱互制檢核</h2>')

    if load_cases:
        results = [(lbl, f, bc.check(f)) for lbl, f in load_cases]

        # summary table
        w("""<table>
<tr>
  <th>#</th><th>Load Case</th>
  <th>Pu (kN)</th><th>Mux (kN·m)</th><th>Muy (kN·m)</th>
  <th>Type</th><th>Eq.</th>
  <th>IR</th><th>Utilization</th><th>Verdict</th>
</tr>""")
        for i, (lbl, f, r) in enumerate(results, 1):
            bar = _ir_bar(r.IR)
            w(f"""<tr>
<td>{i}</td><td><b>{lbl}</b></td>
<td>{f.Pu:+.1f}</td><td>{f.Mux:.2f}</td><td>{f.Muy:.2f}</td>
<td>{_sign_str(f.Pu)}</td><td>{r.equation}</td>
<td><b>{r.IR:.4f}</b> {bar}</td>
<td>{r.utilization_pct:.1f}%</td>
<td>{_tag(r.passes)}</td>
</tr>""")
        w("</table>")

        # detail per load case
        for i, (lbl, f, r) in enumerate(results, 1):
            w(f'<h3>{i}. Load Case: {lbl}</h3>')
            if r.equation == "H1-1a":
                eq_formula = (
                    f"|Pu|/φPn + (8/9)(|Mux|/φMnx + |Muy|/φMny) ≤ 1.0"
                    f"&nbsp;&nbsp; [|Pu/φPn| = {r.ratio_P:.4f} ≥ 0.20]"
                )
                calc = (f"{r.ratio_P:.4f} + (8/9)×({r.ratio_Mx:.4f} + {r.ratio_My:.4f})"
                        f" = <span class='result'>{r.IR:.4f}</span>")
            else:
                eq_formula = (
                    f"|Pu|/(2φPn) + |Mux|/φMnx + |Muy|/φMny ≤ 1.0"
                    f"&nbsp;&nbsp; [|Pu/φPn| = {r.ratio_P:.4f} &lt; 0.20]"
                )
                calc = (f"{r.ratio_P:.4f}/2 + {r.ratio_Mx:.4f} + {r.ratio_My:.4f}"
                        f" = <span class='result'>{r.IR:.4f}</span>")

            phi_pn_used = r.phi_Pn
            w(f"""<div class="formula">
Applied forces:<br>
&nbsp;&nbsp; Pu = {f.Pu:+.2f} kN ({_sign_str(f.Pu)}),
&nbsp; Mux = {f.Mux:.2f} kN·m,
&nbsp; Muy = {f.Muy:.2f} kN·m<br><br>
Design capacities used:<br>
&nbsp;&nbsp; φPn = {phi_pn_used:.2f} kN,
&nbsp; φMnx = {r.phi_Mn_x:.2f} kN·m,
&nbsp; φMny = {r.phi_Mn_y:.2f} kN·m<br><br>
Demand/capacity ratios:<br>
&nbsp;&nbsp; |Pu|/φPn   = {abs(f.Pu):.2f} / {phi_pn_used:.2f}
  = <span class="var">{r.ratio_P:.4f}</span><br>
&nbsp;&nbsp; |Mux|/φMnx = {abs(f.Mux):.2f} / {r.phi_Mn_x:.2f}
  = <span class="var">{r.ratio_Mx:.4f}</span><br>
&nbsp;&nbsp; |Muy|/φMny = {abs(f.Muy):.2f} / {r.phi_Mn_y:.2f}
  = <span class="var">{r.ratio_My:.4f}</span><br><br>
Governing equation: AISC <b>{r.equation}</b><br>
&nbsp;&nbsp; {eq_formula}<br>
&nbsp;&nbsp; IR = {calc}<br><br>
<b>Interaction Ratio (IR) = <span class="result">{r.IR:.4f}</span></b>
&nbsp;&nbsp; Utilization = {r.utilization_pct:.1f}%
&nbsp;&nbsp; {_tag(r.passes)}
</div>""")
    else:
        w("<p>No load cases provided.</p>")

    # ── 9. P-M diagram ────────────────────────────────────────────────────────
    if diagram_png:
        uri = _embed_png(diagram_png)
        if uri:
            w('<h2>9. P-M Interaction Diagram  軸力-彎矩互制圖</h2>')
            w(f'<div class="diagram"><img src="{uri}" alt="P-M Interaction Diagram"></div>')
        else:
            w(f'<h2>9. P-M Interaction Diagram</h2>'
              f'<p><i>(Diagram file not found: {diagram_png})</i></p>')

    # ── footer ────────────────────────────────────────────────────────────────
    w(f"""<footer>
Generated by AISC 360-16 LRFD Steel Beam-Column Calculator (Metric Edition)
&nbsp;|&nbsp; {now}
&nbsp;|&nbsp; Reference: AISC 360-16 Specification for Structural Steel Buildings
</footer>
</div></body></html>""")

    html = "\n".join(parts)
    out = save_path or "calculation_report.html"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"\n  Calculation report saved -> {out}")
    # Open in VS Code / browser
    abs_path = os.path.abspath(out)
    if os.system(f'code "{abs_path}" 2>/dev/null') != 0:
        print(f"  Open manually: {abs_path}")

    return out
