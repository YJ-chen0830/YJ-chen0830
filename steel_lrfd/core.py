"""
AISC 360-16 LRFD Steel Beam-Column Core Calculation Engine
===========================================================
Reference: AISC 360-16 "Specification for Structural Steel Buildings"

Chapters used:
  D  – Tension members
  E  – Compression members (columns)
  F  – Flexural members (beams)
  H1 – Members subject to combined axial & flexure (beam-columns)

Unit system
-----------
  Section properties : mm, mm², mm⁴, mm³
  Stresses (Fy, E…)  : MPa  (= N/mm²)
  Member lengths      : mm   (user helpers accept metres)
  Force output        : kN   (= N ÷ 1 000)
  Moment output       : kN·m (= N·mm ÷ 1 000 000)
  User force input    : kN and kN·m
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .sections_db import HSection


# ---------------------------------------------------------------------------
# Data containers – input
# ---------------------------------------------------------------------------

@dataclass
class Material:
    Fy: float = 355.0      # Yield stress         (MPa)  SS490 / SM490
    Fu: float = 490.0      # Ultimate stress      (MPa)
    E:  float = 200_000.0  # Elastic modulus      (MPa)
    G:  float = 77_000.0   # Shear modulus        (MPa)


@dataclass
class ColumnParams:
    """Effective-length parameters for column buckling (lengths stored in mm)."""
    Kx: float = 1.0
    Ky: float = 1.0
    Lx: float = 0.0   # mm
    Ly: float = 0.0   # mm

    @classmethod
    def from_m(cls, Kx: float, Lx_m: float,
               Ky: float, Ly_m: float) -> "ColumnParams":
        """Convenience constructor – supply lengths in metres."""
        return cls(Kx=Kx, Lx=Lx_m * 1_000.0, Ky=Ky, Ly=Ly_m * 1_000.0)

    @property
    def KxLx(self) -> float:
        return self.Kx * self.Lx

    @property
    def KyLy(self) -> float:
        return self.Ky * self.Ly


@dataclass
class BeamParams:
    """Lateral-torsional buckling parameters (Lb stored in mm)."""
    Lb: float = 0.0    # mm
    Cb: float = 1.0

    @classmethod
    def from_m(cls, Lb_m: float, Cb: float = 1.0) -> "BeamParams":
        """Convenience constructor – supply Lb in metres."""
        return cls(Lb=Lb_m * 1_000.0, Cb=Cb)


@dataclass
class AppliedForces:
    """
    Required (factored) forces on the member.
      Pu  : kN    (+ = tension,  − = compression)
      Mux : kN·m  (strong axis)
      Muy : kN·m  (weak axis)
    """
    Pu:  float = 0.0
    Mux: float = 0.0
    Muy: float = 0.0

    @classmethod
    def from_kN(cls, Pu: float, Mux: float, Muy: float = 0.0) -> "AppliedForces":
        return cls(Pu=Pu, Mux=Mux, Muy=Muy)


# ---------------------------------------------------------------------------
# Data containers – results
# ---------------------------------------------------------------------------

@dataclass
class CompressionResult:
    """Chapter E output.  Forces in kN, stresses in MPa."""
    KL_r_x:     float
    KL_r_y:     float
    KL_r:       float
    KL_r_limit: float
    Fe:         float   # MPa
    Fcr:        float   # MPa
    Pn:         float   # kN
    phi_c:      float = 0.90
    buckling_mode: str = ""

    @property
    def phi_Pn(self) -> float:
        return self.phi_c * self.Pn


@dataclass
class TensionResult:
    """Chapter D output.  Forces in kN."""
    Pnt:   float    # kN
    phi_t: float = 0.90

    @property
    def phi_Pnt(self) -> float:
        return self.phi_t * self.Pnt


@dataclass
class FlexureResult:
    """Chapter F output.  Moments in kN·m, lengths in mm."""
    axis:     Literal["x", "y"]
    Mp:       float   # kN·m
    Mn:       float   # kN·m
    phi_b:    float = 0.90
    ltb_zone: str   = ""
    Lp:       float = 0.0   # mm
    Lr:       float = 0.0   # mm

    @property
    def phi_Mn(self) -> float:
        return self.phi_b * self.Mn


@dataclass
class InteractionResult:
    """Chapter H1 output."""
    Pu:      float   # kN
    Mux:     float   # kN·m
    Muy:     float   # kN·m
    phi_Pn:  float   # kN
    phi_Mn_x: float  # kN·m
    phi_Mn_y: float  # kN·m
    ratio_P:  float
    ratio_Mx: float
    ratio_My: float
    equation: str    # "H1-1a" or "H1-1b"
    IR:       float

    @property
    def passes(self) -> bool:
        return self.IR <= 1.0

    @property
    def utilization_pct(self) -> float:
        return self.IR * 100.0


# ---------------------------------------------------------------------------
# Core calculator
# ---------------------------------------------------------------------------

_N_TO_KN    = 1e-3          # N  → kN
_NMM_TO_KNM = 1e-6          # N·mm → kN·m


class BeamColumnLRFD:
    """
    AISC 360-16 LRFD beam-column calculator (metric edition).

    Parameters
    ----------
    section  : HSection     – cross-section from metric database
    material : Material     – steel grade (MPa)
    col      : ColumnParams – KL in mm
    beam     : BeamParams   – Lb in mm, Cb
    """

    PHI_C = 0.90
    PHI_T = 0.90
    PHI_B = 0.90

    def __init__(
        self,
        section:  HSection,
        material: Material      | None = None,
        col:      ColumnParams  | None = None,
        beam:     BeamParams    | None = None,
    ) -> None:
        self.sec  = section
        self.mat  = material or Material()
        self.col  = col  or ColumnParams()
        self.beam = beam or BeamParams()

        self.compression: CompressionResult = self._calc_compression()
        self.tension:     TensionResult     = self._calc_tension()
        self.flexure_x:   FlexureResult     = self._calc_flexure_strong()
        self.flexure_y:   FlexureResult     = self._calc_flexure_weak()

    # ------------------------------------------------------------------
    # Chapter E – Compression
    # ------------------------------------------------------------------

    def _calc_compression(self) -> CompressionResult:
        sec, mat, col = self.sec, self.mat, self.col
        E, Fy = mat.E, mat.Fy

        KL_r_x = col.KxLx / sec.rx if sec.rx > 0 else 0.0
        KL_r_y = col.KyLy / sec.ry if sec.ry > 0 else 0.0
        KL_r   = max(KL_r_x, KL_r_y)

        # Eq. E3-4: 4.71√(E/Fy)
        KL_r_limit = 4.71 * math.sqrt(E / Fy)

        # Elastic buckling stress (MPa)
        Fe = (math.pi**2 * E) / KL_r**2 if KL_r > 0 else 1e12

        if KL_r <= KL_r_limit:
            Fcr  = (0.658 ** (Fy / Fe)) * Fy
            mode = "非彈性挫屈 Inelastic buckling" if KL_r > 0 else "全斷面降伏 Squash"
        else:
            Fcr  = 0.877 * Fe
            mode = "彈性挫屈 Elastic buckling"

        Pn_kN = Fcr * sec.A * _N_TO_KN   # [MPa=N/mm²] × [mm²] / 1000 = kN
        return CompressionResult(
            KL_r_x=KL_r_x, KL_r_y=KL_r_y, KL_r=KL_r,
            KL_r_limit=KL_r_limit, Fe=Fe, Fcr=Fcr, Pn=Pn_kN,
            phi_c=self.PHI_C, buckling_mode=mode,
        )

    # ------------------------------------------------------------------
    # Chapter D – Tension
    # ------------------------------------------------------------------

    def _calc_tension(self) -> TensionResult:
        Pnt_kN = self.mat.Fy * self.sec.A * _N_TO_KN
        return TensionResult(Pnt=Pnt_kN, phi_t=self.PHI_T)

    # ------------------------------------------------------------------
    # Chapter F – Strong-axis flexure
    # ------------------------------------------------------------------

    def _calc_flexure_strong(self) -> FlexureResult:
        sec, mat, beam = self.sec, self.mat, self.beam
        E, Fy = mat.E, mat.Fy
        Lb, Cb = beam.Lb, beam.Cb

        # Plastic moment [N·mm] → kN·m
        Mp_kNm = Fy * sec.Zx * _NMM_TO_KNM

        # Lp  Eq. F2-5
        Lp = 1.76 * sec.ry * math.sqrt(E / Fy)

        # rts
        rts = sec.rts if sec.rts > 0 else math.sqrt(
            math.sqrt(sec.Iy * sec.Cw) / sec.Sx
        )

        c = 1.0  # doubly symmetric I-section

        # Lr  Eq. F2-6
        J_term = (sec.J * c) / (sec.Sx * sec.ho)
        inner  = J_term + math.sqrt(J_term**2 + 6.76 * (0.7 * Fy / E)**2)
        Lr     = 1.95 * rts * (E / (0.7 * Fy)) * math.sqrt(inner)

        if Lb <= Lp:
            Mn_kNm = Mp_kNm
            zone   = "塑性彎矩 Plastic (No LTB)"

        elif Lb <= Lr:
            # Eq. F2-2: inelastic LTB
            Mn_Nmm = Cb * (
                Fy * sec.Zx
                - (Fy * sec.Zx - 0.7 * Fy * sec.Sx) * (Lb - Lp) / (Lr - Lp)
            )
            Mn_kNm = min(Mn_Nmm * _NMM_TO_KNM, Mp_kNm)
            zone   = "非彈性側扭挫屈 Inelastic LTB"

        else:
            # Eq. F2-3/F2-4: elastic LTB
            Fcr_ltb = ((Cb * math.pi**2 * E) / (Lb / rts)**2) * math.sqrt(
                1.0 + 0.078 * (sec.J * c) / (sec.Sx * sec.ho) * (Lb / rts)**2
            )
            Mn_kNm = min(Fcr_ltb * sec.Sx * _NMM_TO_KNM, Mp_kNm)
            zone   = "彈性側扭挫屈 Elastic LTB"

        return FlexureResult(
            axis="x", Mp=Mp_kNm, Mn=Mn_kNm, phi_b=self.PHI_B,
            ltb_zone=zone, Lp=Lp, Lr=Lr,
        )

    # ------------------------------------------------------------------
    # Chapter F – Weak-axis flexure
    # ------------------------------------------------------------------

    def _calc_flexure_weak(self) -> FlexureResult:
        sec, mat = self.sec, self.mat
        Fy = mat.Fy
        Mp_y = min(Fy * sec.Zy, 1.6 * Fy * sec.Sy) * _NMM_TO_KNM
        return FlexureResult(
            axis="y", Mp=Mp_y, Mn=Mp_y, phi_b=self.PHI_B,
            ltb_zone="無 LTB (弱軸 Weak axis)",
        )

    # ------------------------------------------------------------------
    # Chapter H1 – Combined loading
    # ------------------------------------------------------------------

    def check(self, forces: AppliedForces) -> InteractionResult:
        """
        Evaluate AISC H1-1a / H1-1b interaction equations.
        All forces in kN / kN·m.
        """
        Pu, Mux, Muy = forces.Pu, forces.Mux, forces.Muy

        phi_Pc  = self.compression.phi_Pn  if Pu <= 0 else self.tension.phi_Pnt
        phi_Mnx = self.flexure_x.phi_Mn
        phi_Mny = self.flexure_y.phi_Mn

        ratio_P  = abs(Pu)  / phi_Pc   if phi_Pc  > 0 else 0.0
        ratio_Mx = abs(Mux) / phi_Mnx  if phi_Mnx > 0 else 0.0
        ratio_My = abs(Muy) / phi_Mny  if phi_Mny > 0 else 0.0

        if ratio_P >= 0.20:           # H1-1a
            IR  = ratio_P + (8.0 / 9.0) * (ratio_Mx + ratio_My)
            eqn = "H1-1a"
        else:                         # H1-1b
            IR  = ratio_P / 2.0 + (ratio_Mx + ratio_My)
            eqn = "H1-1b"

        return InteractionResult(
            Pu=Pu, Mux=Mux, Muy=Muy,
            phi_Pn=phi_Pc, phi_Mn_x=phi_Mnx, phi_Mn_y=phi_Mny,
            ratio_P=ratio_P, ratio_Mx=ratio_Mx, ratio_My=ratio_My,
            equation=eqn, IR=IR,
        )

    # ------------------------------------------------------------------
    # P-M interaction curve
    # ------------------------------------------------------------------

    def interaction_curve(
        self, n_pts: int = 300, with_phi: bool = True
    ) -> tuple[list[float], list[float]]:
        """
        Return (P_list [kN], M_list [kN·m]) tracing the H1-1 boundary.
        P < 0 → compression,  P > 0 → tension,  M ≥ 0
        """
        if with_phi:
            Pc = self.compression.phi_Pn
            Pt = self.tension.phi_Pnt
            Mc = self.flexure_x.phi_Mn
        else:
            Pc = self.compression.Pn
            Pt = self.tension.Pnt
            Mc = self.flexure_x.Mn

        P_vals, M_vals = [], []

        # Compression side  (P: −Pc → 0)
        for P in [-Pc + i * Pc / (n_pts // 2) for i in range(n_pts // 2 + 1)]:
            rP = abs(P) / Pc if Pc > 0 else 0.0
            M  = Mc * (1.0 - rP) * (9.0 / 8.0) if rP >= 0.2 else Mc * (1.0 - rP / 2.0)
            P_vals.append(P);  M_vals.append(max(0.0, min(M, Mc)))

        # Tension side  (P: 0 → +Pt)
        for P in [i * Pt / (n_pts // 2) for i in range(1, n_pts // 2 + 1)]:
            rP = P / Pt if Pt > 0 else 0.0
            M  = Mc * (1.0 - rP) * (9.0 / 8.0) if rP >= 0.2 else Mc * (1.0 - rP / 2.0)
            P_vals.append(P);  M_vals.append(max(0.0, min(M, Mc)))

        return P_vals, M_vals
