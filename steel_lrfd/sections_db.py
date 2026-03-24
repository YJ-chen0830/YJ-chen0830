"""
AISC W-Section Properties Database
Units: inches (in), square inches (in²), inches^4 (in⁴), etc.
Source: AISC Steel Construction Manual, 16th Edition
"""

from dataclasses import dataclass


@dataclass
class WSection:
    name: str
    A: float    # Cross-sectional area (in²)
    d: float    # Depth (in)
    tw: float   # Web thickness (in)
    bf: float   # Flange width (in)
    tf: float   # Flange thickness (in)
    Ix: float   # Moment of inertia, strong axis (in⁴)
    Sx: float   # Elastic section modulus, strong axis (in³)
    Zx: float   # Plastic section modulus, strong axis (in³)
    rx: float   # Radius of gyration, strong axis (in)
    Iy: float   # Moment of inertia, weak axis (in⁴)
    Sy: float   # Elastic section modulus, weak axis (in³)
    Zy: float   # Plastic section modulus, weak axis (in³)
    ry: float   # Radius of gyration, weak axis (in)
    J: float    # Torsional constant (in⁴)
    Cw: float   # Warping constant (in⁶)
    rts: float  # Effective radius of gyration for LTB (in)
    ho: float   # Distance between flange centroids (in)


# fmt: off
W_SECTIONS: dict[str, WSection] = {
    # ----- W8 series -----
    "W8x31":  WSection("W8x31",  9.13, 8.00, 0.285, 8.000, 0.435, 110,   27.5, 30.4,  3.47, 37.1, 9.27, 14.1, 2.02, 0.536,   530,  2.10, 7.57),
    "W8x40":  WSection("W8x40",  11.7, 8.25, 0.360, 8.070, 0.560, 146,   35.5, 39.8,  3.53, 49.1, 12.2, 18.5, 2.04, 0.980,   710,  2.16, 7.69),
    "W8x48":  WSection("W8x48",  14.1, 8.50, 0.400, 8.110, 0.685, 184,   43.3, 49.0,  3.61, 60.9, 15.0, 22.9, 2.08, 1.96,    959,  2.23, 7.82),
    # ----- W10 series -----
    "W10x49": WSection("W10x49", 14.4, 9.98, 0.340, 10.00, 0.560, 272,   54.6, 60.4,  4.35, 93.4, 18.7, 28.3, 2.54, 1.39,   2070,  2.65, 9.42),
    "W10x60": WSection("W10x60", 17.6, 10.2, 0.420, 10.08, 0.680, 341,   66.7, 74.6,  4.39, 116,  23.0, 34.9, 2.57, 2.48,   2600,  2.70, 9.52),
    "W10x77": WSection("W10x77", 22.6, 10.6, 0.530, 10.19, 0.870, 455,   85.9, 97.6,  4.49, 154,  30.1, 45.9, 2.60, 4.49,   3560,  2.76, 9.73),
    # ----- W12 series -----
    "W12x53": WSection("W12x53", 15.6, 12.1, 0.345,  9.995, 0.575, 425,  70.6, 77.9,  5.23, 95.8, 19.2, 29.1, 2.48, 1.58,   3160,  2.59, 11.5),
    "W12x72": WSection("W12x72", 21.1, 12.3, 0.430, 12.04,  0.670, 597,  97.4, 108,   5.31, 195,  32.4, 49.2, 3.04, 3.04,   5990,  3.18, 11.7),
    "W12x96": WSection("W12x96", 28.2, 12.7, 0.550, 12.16,  0.900, 833,  131,  147,   5.44, 270,  44.4, 67.5, 3.09, 6.85,   8420,  3.26, 11.8),
    # ----- W14 series -----
    "W14x48": WSection("W14x48", 14.1, 13.8, 0.340,  8.031, 0.595, 484,  70.2, 78.4,  5.85, 51.4, 12.8, 19.6, 1.91, 1.45,   3950,  2.01, 13.2),
    "W14x61": WSection("W14x61", 17.9, 13.9, 0.375,  9.995, 0.645, 640,  92.1, 102,   5.98, 107,  21.5, 32.8, 2.45, 2.19,   7190,  2.56, 13.3),
    "W14x82": WSection("W14x82", 24.0, 14.3, 0.510, 10.130, 0.855, 882,  123,  139,   6.05, 148,  29.3, 44.8, 2.48, 5.07,   9760,  2.60, 13.4),
    "W14x109": WSection("W14x109",32.0, 14.3, 0.525, 14.605, 0.860,1240,  173,  192,   6.22, 447,  61.2, 92.7, 3.73, 6.60,  25900,  3.89, 13.5),
    "W14x132": WSection("W14x132",38.8, 14.7, 0.645, 14.725, 1.030,1530,  209,  234,   6.28, 548,  74.5, 113,  3.76, 12.3,  31900,  3.93, 13.7),
    # ----- W16 series -----
    "W16x67": WSection("W16x67", 19.7, 16.3, 0.395, 10.235, 0.665, 954,  117,  130,   6.96, 119,  23.2, 35.5, 2.46, 2.39,  10400,  2.57, 15.6),
    "W16x89": WSection("W16x89", 26.2, 16.8, 0.525, 10.365, 0.875,1300,  155,  175,   7.05, 163,  31.4, 48.1, 2.49, 5.45,  14500,  2.61, 15.9),
    # ----- W18 series -----
    "W18x76": WSection("W18x76", 22.3, 18.2, 0.425, 11.035, 0.680,1330,  146,  163,   7.73, 152,  27.6, 42.2, 2.61, 2.68,  17700,  2.72, 17.5),
    "W18x97": WSection("W18x97", 28.5, 18.6, 0.535, 11.145, 0.870,1750,  188,  211,   7.82, 201,  36.1, 55.3, 2.65, 5.86,  23800,  2.77, 17.7),
    "W18x119": WSection("W18x119",35.1,18.97,0.655, 11.265, 1.060,2190,  231,  262,   7.90, 253,  44.9, 69.1, 2.69, 10.6,  30200,  2.82, 17.9),
    # ----- W21 series -----
    "W21x68": WSection("W21x68", 20.0, 21.1, 0.430,  8.270, 0.685,1480,  140,  160,   8.60, 64.7, 15.7, 24.4, 1.80, 2.45,  13300,  1.92, 20.4),
    "W21x93": WSection("W21x93", 27.3, 21.6, 0.580,  8.420, 0.930,2070,  192,  221,   8.70, 92.9, 22.1, 34.7, 1.84, 7.00,  20200,  1.97, 20.7),
    # ----- W24 series -----
    "W24x76": WSection("W24x76", 22.4, 23.9, 0.440,  8.990, 0.680,2100,  176,  200,   9.69, 82.5, 18.4, 28.6, 1.92, 2.68,  18400,  2.03, 23.2),
    "W24x104": WSection("W24x104",30.6, 24.1, 0.500, 12.750, 0.750,3100,  258,  289,  10.1,  259,  40.7, 62.4, 2.91, 5.61,  48100,  3.02, 23.4),
    # ----- W27 series -----
    "W27x94": WSection("W27x94", 27.7, 26.9, 0.490, 9.990, 0.745, 3270,  243,  278,  10.9,  124,  24.8, 38.8, 2.12, 3.77,  29500,  2.22, 26.2),
    # ----- W33 series -----
    "W33x130": WSection("W33x130",38.3, 33.1, 0.580, 11.510, 0.855,6710,  406,  467,  13.2,  218,  37.9, 58.4, 2.39, 9.56,  65900,  2.52, 32.2),
}
# fmt: on


def get_section(name: str) -> WSection:
    """Return section by name, case-insensitive."""
    key = name.upper().replace(" ", "")
    for k, v in W_SECTIONS.items():
        if k.upper().replace(" ", "") == key:
            return v
    available = ", ".join(W_SECTIONS.keys())
    raise KeyError(f"Section '{name}' not found. Available: {available}")


def list_sections() -> list[str]:
    return list(W_SECTIONS.keys())
