"""
AISC LRFD Steel Beam-Column Core Calculation Engine
====================================================
Reference: AISC 360-16 "Specification for Structural Steel Buildings"

Chapters used:
  D  – Tension members
  E  – Compression members (columns)
  F  – Flexural members (beams)
  H1 – Members subject to combined axial & flexure (beam-columns)

Units: US customary  →  kips, inches, ksi
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from .sections_db import WSection


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class Material:
    Fy: float = 50.0     # Yield stress (ksi)
    Fu: float = 65.0     # Ultimate stress (ksi)
    E: float  = 29000.0  # Elastic modulus (ksi)
    G: float  = 11200.0  # Shear modulus (ksi)


@dataclass
class ColumnParams:
    """Effective length parameters for column buckling."""
    Kx: float = 1.0   # Effective length factor, strong axis
    Ky: float = 1.0   # Effective length factor, weak axis
    Lx: float = 0.0   # Unbraced length, strong axis (in)  [set via ft property]
    Ly: float = 0.0   # Unbraced length, weak axis  (in)

    @classmethod
    def from_ft(cls, Kx: float, Lx_ft: float, Ky: float, Ly_ft: float) -> "ColumnParams":
        return cls(Kx=Kx, Lx=Lx_ft * 12.0, Ky=Ky, Ly=Ly_ft * 12.0)

    @property
    def KxLx(self) -> float:
        return self.Kx * self.Lx

    @property
    def KyLy(self) -> float:
        return self.Ky * self.Ly


@dataclass
class BeamParams:
    """Lateral-torsional buckling parameters."""
    Lb: float = 0.0    # Unbraced length (in)
    Cb: float = 1.0    # LTB modification factor (conservative = 1.0)

    @classmethod
    def from_ft(cls, Lb_ft: float, Cb: float = 1.0) -> "BeamParams":
        return cls(Lb=Lb_ft * 12.0, Cb=Cb)


@dataclass
class AppliedForces:
    """Required (factored) forces on the member."""
    Pu: float = 0.0   # Axial force (kips):  + tension / − compression
    Mux: float = 0.0  # Required moment, strong axis (kip-in)
    Muy: float = 0.0  # Required moment, weak axis   (kip-in)

    @classmethod
    def from_kip_ft(cls, Pu: float, Mux_ft: float, Muy_ft: float = 0.0) -> "AppliedForces":
        return cls(Pu=Pu, Mux=Mux_ft * 12.0, Muy=Muy_ft * 12.0)


# ---------------------------------------------------------------------------
# Strength result containers
# ---------------------------------------------------------------------------

@dataclass
class CompressionResult:
    """Output of Chapter E calculation."""
    KL_r_x: float       # Slenderness ratio, strong axis
    KL_r_y: float       # Slenderness ratio, weak axis
    KL_r: float         # Governing (max) slenderness ratio
    KL_r_limit: float   # 4.71 * sqrt(E/Fy)
    Fe: float           # Elastic buckling stress (ksi)
    Fcr: float          # Critical stress (ksi)
    Pn: float           # Nominal compressive strength (kips)
    phi_c: float = 0.90
    buckling_mode: str = ""

    @property
    def phi_Pn(self) -> float:
        return self.phi_c * self.Pn


@dataclass
class TensionResult:
    """Output of Chapter D calculation (yielding on gross section only)."""
    Pnt: float          # Nominal tensile strength (kips)
    phi_t: float = 0.90

    @property
    def phi_Pnt(self) -> float:
        return self.phi_t * self.Pnt


@dataclass
class FlexureResult:
    """Output of Chapter F calculation for one bending axis."""
    axis: Literal["x", "y"]
    Mp: float           # Plastic moment (kip-in)
    Mn: float           # Nominal moment strength (kip-in)
    phi_b: float = 0.90
    ltb_zone: str = ""  # "Plastic", "Inelastic LTB", "Elastic LTB"
    Lp: float = 0.0     # Lp (in) – strong axis only
    Lr: float = 0.0     # Lr (in) – strong axis only

    @property
    def phi_Mn(self) -> float:
        return self.phi_b * self.Mn


@dataclass
class InteractionResult:
    """Output of Chapter H1 interaction check."""
    Pu: float
    Mux: float
    Muy: float
    phi_Pn: float           # Used capacity (compression or tension)
    phi_Mn_x: float
    phi_Mn_y: float
    ratio_P: float          # |Pu| / phi_Pn
    ratio_Mx: float         # |Mux| / phi_Mnx
    ratio_My: float         # |Muy| / phi_Mny
    equation: str           # "H1-1a" or "H1-1b"
    IR: float               # Interaction ratio  (must be ≤ 1.0)

    @property
    def passes(self) -> bool:
        return self.IR <= 1.0

    @property
    def utilization_pct(self) -> float:
        return self.IR * 100.0


# ---------------------------------------------------------------------------
# Core calculator
# ---------------------------------------------------------------------------

class BeamColumnLRFD:
    """
    AISC 360-16 LRFD beam-column calculator.

    Parameters
    ----------
    section  : WSection – cross-section from the database
    material : Material – steel grade properties
    col      : ColumnParams – KL parameters for axial compression
    beam     : BeamParams  – unbraced length & Cb for flexure
    """

    # LRFD resistance factors (AISC Table B3.1)
    PHI_C = 0.90   # Compression
    PHI_T = 0.90   # Tension (yielding)
    PHI_B = 0.90   # Flexure

    def __init__(
        self,
        section: WSection,
        material: Material | None = None,
        col: ColumnParams | None = None,
        beam: BeamParams | None = None,
    ) -> None:
        self.sec = section
        self.mat = material or Material()
        self.col = col or ColumnParams()
        self.beam = beam or BeamParams()

        # Compute all strengths on construction
        self.compression: CompressionResult = self._calc_compression()
        self.tension: TensionResult         = self._calc_tension()
        self.flexure_x: FlexureResult       = self._calc_flexure_strong()
        self.flexure_y: FlexureResult       = self._calc_flexure_weak()

    # ------------------------------------------------------------------
    # Chapter E – Compression
    # ------------------------------------------------------------------

    def _calc_compression(self) -> CompressionResult:
        sec, mat, col = self.sec, self.mat, self.col
        E, Fy = mat.E, mat.Fy

        KL_r_x = col.KxLx / sec.rx if sec.rx > 0 else 0.0
        KL_r_y = col.KyLy / sec.ry if sec.ry > 0 else 0.0
        KL_r   = max(KL_r_x, KL_r_y)

        # Eq. E3-4: limiting slenderness
        KL_r_limit = 4.71 * math.sqrt(E / Fy)

        # Eq. E3-4: elastic buckling stress
        Fe = (math.pi**2 * E) / (KL_r**2) if KL_r > 0 else 1e9

        # Eq. E3-2 or E3-3
        if KL_r <= KL_r_limit:
            Fcr  = (0.658 ** (Fy / Fe)) * Fy
            mode = "Inelastic flexural buckling" if KL_r > 0 else "Squash (KL=0)"
        else:
            Fcr  = 0.877 * Fe
            mode = "Elastic flexural buckling"

        Pn = Fcr * sec.A
        return CompressionResult(
            KL_r_x=KL_r_x, KL_r_y=KL_r_y, KL_r=KL_r,
            KL_r_limit=KL_r_limit, Fe=Fe, Fcr=Fcr, Pn=Pn,
            phi_c=self.PHI_C, buckling_mode=mode,
        )

    # ------------------------------------------------------------------
    # Chapter D – Tension (yielding on gross section)
    # ------------------------------------------------------------------

    def _calc_tension(self) -> TensionResult:
        Pnt = self.mat.Fy * self.sec.A
        return TensionResult(Pnt=Pnt, phi_t=self.PHI_T)

    # ------------------------------------------------------------------
    # Chapter F – Flexure, strong axis (doubly symmetric I-sections)
    # ------------------------------------------------------------------

    def _calc_flexure_strong(self) -> FlexureResult:
        sec, mat, beam = self.sec, self.mat, self.beam
        E, Fy = mat.E, mat.Fy
        Lb, Cb = beam.Lb, beam.Cb

        # Plastic moment  Eq. F2-1
        Mp = Fy * sec.Zx

        # ------ Limiting unbraced lengths ------
        # Eq. F2-5:  Lp
        Lp = 1.76 * sec.ry * math.sqrt(E / Fy)

        # rts  (use database value if available, else estimate)
        rts = sec.rts if sec.rts > 0 else math.sqrt(math.sqrt(sec.Iy * sec.Cw) / sec.Sx)

        c = 1.0  # doubly symmetric I-section (AISC F2)

        # Eq. F2-6:  Lr
        J_term = (sec.J * c) / (sec.Sx * sec.ho)
        inner  = J_term + math.sqrt(J_term**2 + 6.76 * (0.7 * Fy / E)**2)
        Lr     = 1.95 * rts * (E / (0.7 * Fy)) * math.sqrt(inner)

        # ------ Nominal moment ------
        if Lb <= Lp:
            # Eq. F2-1: full plastic – no LTB
            Mn   = Mp
            zone = "Plastic (No LTB)"

        elif Lb <= Lr:
            # Eq. F2-2: inelastic LTB
            Mn   = Cb * (Mp - (Mp - 0.7 * Fy * sec.Sx) * (Lb - Lp) / (Lr - Lp))
            Mn   = min(Mn, Mp)
            zone = "Inelastic LTB"

        else:
            # Eq. F2-3/F2-4: elastic LTB
            Fcr  = ((Cb * math.pi**2 * E) / (Lb / rts)**2) * math.sqrt(
                1.0 + 0.078 * (sec.J * c) / (sec.Sx * sec.ho) * (Lb / rts)**2
            )
            Mn   = min(Fcr * sec.Sx, Mp)
            zone = "Elastic LTB"

        return FlexureResult(
            axis="x", Mp=Mp, Mn=Mn, phi_b=self.PHI_B,
            ltb_zone=zone, Lp=Lp, Lr=Lr,
        )

    # ------------------------------------------------------------------
    # Chapter F – Flexure, weak axis
    # ------------------------------------------------------------------

    def _calc_flexure_weak(self) -> FlexureResult:
        sec, mat = self.sec, self.mat
        Fy = mat.Fy
        # Eq. F6-1: plastic moment (weak axis LTB doesn't apply to I-sections)
        Mp_y = min(Fy * sec.Zy, 1.6 * Fy * sec.Sy)
        return FlexureResult(axis="y", Mp=Mp_y, Mn=Mp_y, phi_b=self.PHI_B, ltb_zone="No LTB (weak axis)")

    # ------------------------------------------------------------------
    # Chapter H1 – Combined loading (interaction equations)
    # ------------------------------------------------------------------

    def check(self, forces: AppliedForces) -> InteractionResult:
        """
        Evaluate AISC H1-1a / H1-1b interaction equations.

        forces.Pu > 0 → tension member capacity used
        forces.Pu < 0 → compression member capacity used
        forces.Pu = 0 → bending only (H1-1b controls)
        """
        Pu, Mux, Muy = forces.Pu, forces.Mux, forces.Muy

        # Governing axial capacity
        if Pu <= 0.0:
            phi_Pc = self.compression.phi_Pn   # compression governs
        else:
            phi_Pc = self.tension.phi_Pnt      # tension governs

        phi_Mnx = self.flexure_x.phi_Mn
        phi_Mny = self.flexure_y.phi_Mn

        ratio_P  = abs(Pu)  / phi_Pc   if phi_Pc  > 0 else 0.0
        ratio_Mx = abs(Mux) / phi_Mnx  if phi_Mnx > 0 else 0.0
        ratio_My = abs(Muy) / phi_Mny  if phi_Mny > 0 else 0.0

        # Eq. H1-1a (|Pu|/φPc ≥ 0.2)
        if ratio_P >= 0.20:
            IR  = ratio_P + (8.0 / 9.0) * (ratio_Mx + ratio_My)
            eqn = "H1-1a"
        # Eq. H1-1b (|Pu|/φPc < 0.2)
        else:
            IR  = ratio_P / 2.0 + (ratio_Mx + ratio_My)
            eqn = "H1-1b"

        return InteractionResult(
            Pu=Pu, Mux=Mux, Muy=Muy,
            phi_Pn=phi_Pc, phi_Mn_x=phi_Mnx, phi_Mn_y=phi_Mny,
            ratio_P=ratio_P, ratio_Mx=ratio_Mx, ratio_My=ratio_My,
            equation=eqn, IR=IR,
        )

    # ------------------------------------------------------------------
    # Interaction curve data (for P-M diagram)
    # ------------------------------------------------------------------

    def interaction_curve(
        self, n_pts: int = 300, with_phi: bool = True
    ) -> tuple[list[float], list[float]]:
        """
        Return (P_list, M_list) points tracing the full H1-1 boundary.

        Sign convention:
            P < 0  →  compression
            P > 0  →  tension
            M ≥ 0  (moment magnitude)
        """
        if with_phi:
            Pc = self.compression.phi_Pn    # max compression capacity (positive value)
            Pt = self.tension.phi_Pnt       # max tension capacity
            Mc = self.flexure_x.phi_Mn      # max moment capacity
        else:
            Pc = self.compression.Pn
            Pt = self.tension.Pnt
            Mc = self.flexure_x.Mn

        P_vals, M_vals = [], []

        # --- Compression side  (P: -Pc → 0) ---
        for P in [-Pc + i * Pc / (n_pts // 2) for i in range(n_pts // 2 + 1)]:
            rP = abs(P) / Pc if Pc > 0 else 0.0
            if rP >= 0.20:
                M = Mc * (1.0 - rP) * (9.0 / 8.0)
            else:
                M = Mc * (1.0 - rP / 2.0)
            P_vals.append(P)
            M_vals.append(max(0.0, min(M, Mc)))

        # --- Tension side  (P: 0 → +Pt) ---
        for P in [i * Pt / (n_pts // 2) for i in range(1, n_pts // 2 + 1)]:
            rP = P / Pt if Pt > 0 else 0.0
            if rP >= 0.20:
                M = Mc * (1.0 - rP) * (9.0 / 8.0)
            else:
                M = Mc * (1.0 - rP / 2.0)
            P_vals.append(P)
            M_vals.append(max(0.0, min(M, Mc)))

        return P_vals, M_vals
