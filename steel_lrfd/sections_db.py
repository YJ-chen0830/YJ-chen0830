"""
Metric H-Section Properties Database
======================================
Sections follow JIS G 3192 / CNS standard naming convention:
  H-d × bf × tw × tf   (e.g., H300×300×10×15)

All properties computed from basic plate dimensions (no fillet contribution).
Units: mm, mm², mm⁴, mm³

Categories
----------
  HW  寬翼緣 H 型鋼 (Wide-flange,  bf ≈ d)
  HN  中翼緣 H 型鋼 (Medium-flange, bf ≈ d/2)
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class HSection:
    name: str
    category: str   # "HW" or "HN"
    d:   float      # Total depth          (mm)
    bf:  float      # Flange width         (mm)
    tw:  float      # Web thickness        (mm)
    tf:  float      # Flange thickness     (mm)
    # ── computed properties (all in mm) ──────────────────────
    A:   float = 0.0   # Cross-sectional area  (mm²)
    Ix:  float = 0.0   # Moment of inertia, x  (mm⁴)
    Sx:  float = 0.0   # Elastic modulus, x    (mm³)
    Zx:  float = 0.0   # Plastic modulus, x    (mm³)
    rx:  float = 0.0   # Radius of gyration, x (mm)
    Iy:  float = 0.0   # Moment of inertia, y  (mm⁴)
    Sy:  float = 0.0   # Elastic modulus, y    (mm³)
    Zy:  float = 0.0   # Plastic modulus, y    (mm³)
    ry:  float = 0.0   # Radius of gyration, y (mm)
    J:   float = 0.0   # Torsion constant      (mm⁴)
    Cw:  float = 0.0   # Warping constant      (mm⁶)
    rts: float = 0.0   # Effective rg for LTB  (mm)
    ho:  float = 0.0   # Flange centroid dist  (mm)

    def __post_init__(self) -> None:
        if self.A == 0.0:
            self._compute()

    def _compute(self) -> None:
        d, bf, tw, tf = self.d, self.bf, self.tw, self.tf
        hw = d - 2 * tf

        # ── area ──────────────────────────────────────────────
        self.A = 2 * bf * tf + hw * tw

        # ── strong axis ───────────────────────────────────────
        self.Ix = (bf * d**3 - (bf - tw) * hw**3) / 12
        self.Sx = self.Ix / (d / 2)
        self.Zx = bf * tf * (d - tf) + tw * hw**2 / 4
        self.rx = math.sqrt(self.Ix / self.A)

        # ── weak axis ─────────────────────────────────────────
        self.Iy = (2 * tf * bf**3 + hw * tw**3) / 12
        self.Sy = self.Iy / (bf / 2)
        self.Zy = tf * bf**2 / 2 + hw * tw**2 / 4
        self.ry = math.sqrt(self.Iy / self.A)

        # ── torsion (thin-plate approx, no fillet) ────────────
        self.J = (2 * bf * tf**3 + hw * tw**3) / 3

        # ── warping ───────────────────────────────────────────
        self.ho = d - tf                          # flange centroid distance
        self.Cw = self.Iy * self.ho**2 / 4

        # ── rts (AISC F2) ─────────────────────────────────────
        rts_sq = math.sqrt(self.Iy * self.Cw) / self.Sx
        self.rts = math.sqrt(rts_sq)


def _h(cat: str, d: float, bf: float, tw: float, tf: float) -> HSection:
    """Factory shorthand."""
    name = f"H{int(d)}x{int(bf)}x{_fmt(tw)}x{int(tf)}"
    return HSection(name=name, category=cat, d=d, bf=bf, tw=tw, tf=tf)


def _fmt(v: float) -> str:
    return str(int(v)) if v == int(v) else str(v)


# ── section database ──────────────────────────────────────────────────────────
# fmt: off
H_SECTIONS: dict[str, HSection] = {}

_raw: list[tuple[str, float, float, float, float]] = [
    # cat   d     bf     tw    tf
    # ── HW 寬翼緣 ─────────────────────────────────────────────
    ("HW", 100,  100,   6.0,   8.0),
    ("HW", 125,  125,   6.5,   9.0),
    ("HW", 150,  150,   7.0,  10.0),
    ("HW", 175,  175,   7.5,  11.0),
    ("HW", 200,  200,   8.0,  12.0),
    ("HW", 250,  250,   9.0,  14.0),
    ("HW", 300,  300,  10.0,  15.0),
    ("HW", 350,  350,  12.0,  19.0),
    ("HW", 400,  400,  13.0,  21.0),
    ("HW", 450,  450,  14.0,  23.0),
    ("HW", 500,  500,  15.0,  25.0),
    ("HW", 600,  600,  16.0,  28.0),
    # ── HN 中翼緣 ─────────────────────────────────────────────
    ("HN", 150,  100,   6.0,   9.0),
    ("HN", 200,  100,   5.5,   8.0),
    ("HN", 250,  125,   6.0,   9.0),
    ("HN", 300,  150,   6.5,   9.0),
    ("HN", 350,  175,   7.0,  11.0),
    ("HN", 400,  200,   8.0,  13.0),
    ("HN", 450,  200,   9.0,  14.0),
    ("HN", 500,  200,  10.0,  16.0),
    ("HN", 600,  200,  11.0,  17.0),
    ("HN", 700,  300,  13.0,  24.0),
    ("HN", 800,  300,  14.0,  26.0),
    ("HN", 900,  300,  16.0,  28.0),
]
# fmt: on

for _cat, _d, _bf, _tw, _tf in _raw:
    _sec = _h(_cat, _d, _bf, _tw, _tf)
    H_SECTIONS[_sec.name] = _sec


# ── public helpers ────────────────────────────────────────────────────────────

def get_section(name: str) -> HSection:
    """
    Look up a section by name, tolerant of '×' vs 'x' and spaces.
    Examples: 'H300x300x10x15', 'H300×300×10×15', 'h300x300x10x15'
    """
    key = name.strip().upper().replace("×", "X").replace(" ", "").replace("-", "")
    # normalise float dimensions: '6.5' stays, '.5' stays
    for k, v in H_SECTIONS.items():
        if k.upper().replace("×", "X") == key:
            return v
    available = ", ".join(H_SECTIONS.keys())
    raise KeyError(f"Section '{name}' not found.\nAvailable: {available}")


def list_sections() -> list[str]:
    return list(H_SECTIONS.keys())


def list_sections_by_category(cat: str) -> list[str]:
    return [k for k, v in H_SECTIONS.items() if v.category == cat.upper()]
