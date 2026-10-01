"""ITU-R propagation models behind :mod:`radarperf.environment`.

* :func:`gaseous_specific_attenuation_db_per_km` -- ITU-R P.676-13 (08/2022),
  Annex 1: line-by-line specific attenuation of dry air and water vapour,
  equations (1)-(9) with the spectroscopic data of Tables 1 and 2.
* :func:`rain_coefficients` -- ITU-R P.838-3 (03/2005): the coefficients ``k``
  and ``alpha`` of the rain power law ``gamma_R = k R**alpha``, equations
  (2)-(5) with the constants of Tables 1-4.

The tests check both against values published by the ITU: the P.676-13
validation examples and P.838-3 Table 5.  Frequencies are in hertz here and
converted to the recommendations' gigahertz internally.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np

# P.676-13 Annex 1, Table 1 (oxygen) and Table 2 (water vapour; the last row is
# the 1780 GHz pseudo-line representing the wet continuum).
_OXYGEN_LINES: Final[tuple[tuple[float, ...], ...]] = (
    # f0 [GHz], a1, a2, a3, a4, a5, a6
    (50.474214, 0.975, 9.651, 6.69, 0.0, 2.566, 6.85),
    (50.987745, 2.529, 8.653, 7.17, 0.0, 2.246, 6.8),
    (51.50336, 6.193, 7.709, 7.64, 0.0, 1.947, 6.729),
    (52.021429, 14.32, 6.819, 8.11, 0.0, 1.667, 6.64),
    (52.542418, 31.24, 5.983, 8.58, 0.0, 1.388, 6.526),
    (53.066934, 64.29, 5.201, 9.06, 0.0, 1.349, 6.206),
    (53.595775, 124.6, 4.474, 9.55, 0.0, 2.227, 5.085),
    (54.130025, 227.3, 3.8, 9.96, 0.0, 3.17, 3.75),
    (54.67118, 389.7, 3.182, 10.37, 0.0, 3.558, 2.654),
    (55.221384, 627.1, 2.618, 10.89, 0.0, 2.56, 2.952),
    (55.783815, 945.3, 2.109, 11.34, 0.0, -1.172, 6.135),
    (56.264774, 543.4, 0.014, 17.03, 0.0, 3.525, -0.978),
    (56.363399, 1331.8, 1.654, 11.89, 0.0, -2.378, 6.547),
    (56.968211, 1746.6, 1.255, 12.23, 0.0, -3.545, 6.451),
    (57.612486, 2120.1, 0.91, 12.62, 0.0, -5.416, 6.056),
    (58.323877, 2363.7, 0.621, 12.95, 0.0, -1.932, 0.436),
    (58.446588, 1442.1, 0.083, 14.91, 0.0, 6.768, -1.273),
    (59.164204, 2379.9, 0.387, 13.53, 0.0, -6.561, 2.309),
    (59.590983, 2090.7, 0.207, 14.08, 0.0, 6.957, -0.776),
    (60.306056, 2103.4, 0.207, 14.15, 0.0, -6.395, 0.699),
    (60.434778, 2438.0, 0.386, 13.39, 0.0, 6.342, -2.825),
    (61.150562, 2479.5, 0.621, 12.92, 0.0, 1.014, -0.584),
    (61.800158, 2275.9, 0.91, 12.63, 0.0, 5.014, -6.619),
    (62.41122, 1915.4, 1.255, 12.17, 0.0, 3.029, -6.759),
    (62.486253, 1503.0, 0.083, 15.13, 0.0, -4.499, 0.844),
    (62.997984, 1490.2, 1.654, 11.74, 0.0, 1.856, -6.675),
    (63.568526, 1078.0, 2.108, 11.34, 0.0, 0.658, -6.139),
    (64.127775, 728.7, 2.617, 10.88, 0.0, -3.036, -2.895),
    (64.67891, 461.3, 3.181, 10.38, 0.0, -3.968, -2.59),
    (65.224078, 274.0, 3.8, 9.96, 0.0, -3.528, -3.68),
    (65.764779, 153.0, 4.473, 9.55, 0.0, -2.548, -5.002),
    (66.302096, 80.4, 5.2, 9.06, 0.0, -1.66, -6.091),
    (66.836834, 39.8, 5.982, 8.58, 0.0, -1.68, -6.393),
    (67.369601, 18.56, 6.818, 8.11, 0.0, -1.956, -6.475),
    (67.900868, 8.172, 7.708, 7.64, 0.0, -2.216, -6.545),
    (68.431006, 3.397, 8.652, 7.17, 0.0, -2.492, -6.6),
    (68.960312, 1.334, 9.65, 6.69, 0.0, -2.773, -6.65),
    (118.750334, 940.3, 0.01, 16.64, 0.0, -0.439, 0.079),
    (368.498246, 67.4, 0.048, 16.4, 0.0, 0.0, 0.0),
    (424.76302, 637.7, 0.044, 16.4, 0.0, 0.0, 0.0),
    (487.249273, 237.4, 0.049, 16.0, 0.0, 0.0, 0.0),
    (715.392902, 98.1, 0.145, 16.0, 0.0, 0.0, 0.0),
    (773.83949, 572.3, 0.141, 16.2, 0.0, 0.0, 0.0),
    (834.145546, 183.1, 0.145, 14.7, 0.0, 0.0, 0.0),
)
_WATER_VAPOUR_LINES: Final[tuple[tuple[float, ...], ...]] = (
    # f0 [GHz], b1, b2, b3, b4, b5, b6
    (22.23508, 0.1079, 2.144, 26.38, 0.76, 5.087, 1.0),
    (67.80396, 0.0011, 8.732, 28.58, 0.69, 4.93, 0.82),
    (119.99594, 0.0007, 8.353, 29.48, 0.7, 4.78, 0.79),
    (183.310087, 2.273, 0.668, 29.06, 0.77, 5.022, 0.85),
    (321.22563, 0.047, 6.179, 24.04, 0.67, 4.398, 0.54),
    (325.152888, 1.514, 1.541, 28.23, 0.64, 4.893, 0.74),
    (336.227764, 0.001, 9.825, 26.93, 0.69, 4.74, 0.61),
    (380.197353, 11.67, 1.048, 28.11, 0.54, 5.063, 0.89),
    (390.134508, 0.0045, 7.347, 21.52, 0.63, 4.81, 0.55),
    (437.346667, 0.0632, 5.048, 18.45, 0.6, 4.23, 0.48),
    (439.150807, 0.9098, 3.595, 20.07, 0.63, 4.483, 0.52),
    (443.018343, 0.192, 5.048, 15.55, 0.6, 5.083, 0.5),
    (448.001085, 10.41, 1.405, 25.64, 0.66, 5.028, 0.67),
    (470.888999, 0.3254, 3.597, 21.34, 0.66, 4.506, 0.65),
    (474.689092, 1.26, 2.379, 23.2, 0.65, 4.804, 0.64),
    (488.490108, 0.2529, 2.852, 25.86, 0.69, 5.201, 0.72),
    (503.568532, 0.0372, 6.731, 16.12, 0.61, 3.98, 0.43),
    (504.482692, 0.0124, 6.731, 16.12, 0.61, 4.01, 0.45),
    (547.67644, 0.9785, 0.158, 26.0, 0.7, 4.5, 1.0),
    (552.02096, 0.184, 0.158, 26.0, 0.7, 4.5, 1.0),
    (556.935985, 497.0, 0.159, 30.86, 0.69, 4.552, 1.0),
    (620.700807, 5.015, 2.391, 24.38, 0.71, 4.856, 0.68),
    (645.766085, 0.0067, 8.633, 18.0, 0.6, 4.0, 0.5),
    (658.00528, 0.2732, 7.816, 32.1, 0.69, 4.14, 1.0),
    (752.033113, 243.4, 0.396, 30.86, 0.68, 4.352, 0.84),
    (841.051732, 0.0134, 8.177, 15.9, 0.33, 5.76, 0.45),
    (859.965698, 0.1325, 8.055, 30.6, 0.68, 4.09, 0.84),
    (899.303175, 0.0547, 7.914, 29.85, 0.68, 4.53, 0.9),
    (902.611085, 0.0386, 8.429, 28.65, 0.7, 5.1, 0.95),
    (906.205957, 0.1836, 5.11, 24.08, 0.7, 4.7, 0.53),
    (916.171582, 8.4, 1.441, 26.73, 0.7, 5.15, 0.78),
    (923.112692, 0.0079, 10.293, 29.0, 0.7, 5.0, 0.8),
    (970.315022, 9.009, 1.919, 25.5, 0.64, 4.94, 0.67),
    (987.926764, 134.6, 0.257, 29.85, 0.68, 4.55, 0.9),
    (1780.0, 17506.0, 0.952, 196.3, 2.0, 24.15, 5.0),
)

_OXYGEN = np.array(_OXYGEN_LINES)
_WATER_VAPOUR = np.array(_WATER_VAPOUR_LINES)


def gaseous_specific_attenuation_db_per_km(
    frequency_hz: float,
    *,
    temperature_c: float = 15.0,
    pressure_hpa: float = 1013.25,
    water_vapour_density_g_m3: float = 7.5,
) -> tuple[float, float]:
    """Dry-air and water-vapour specific attenuation [dB/km], ITU-R P.676-13.

    Annex 1, equations (1)-(9).  ``pressure_hpa`` is the total barometric
    pressure; the dry-air pressure is that minus the water-vapour partial
    pressure of equation (4).  The defaults are the recommendation's standard
    sea-level conditions (15 degC, 7.5 g/m^3).  Valid from 1 to 1000 GHz.
    Returns ``(oxygen, water_vapour)``; their sum is the total.
    """
    f = frequency_hz / 1.0e9
    if not 1.0 <= f <= 1000.0:
        raise ValueError("P.676-13 Annex 1 covers 1-1000 GHz")
    if water_vapour_density_g_m3 < 0.0 or pressure_hpa <= 0.0:
        raise ValueError("pressure must be positive and vapour density non-negative")
    temperature_k = temperature_c + 273.15
    theta = 300.0 / temperature_k
    e = water_vapour_density_g_m3 * temperature_k / 216.7  # (4)
    p = pressure_hpa - e
    if p <= 0.0:
        raise ValueError("water-vapour pressure exceeds the total pressure")

    f0, a1, a2, a3, a4, a5, a6 = _OXYGEN.T
    strength = a1 * 1e-7 * p * theta**3 * np.exp(a2 * (1.0 - theta))  # (3)
    width = a3 * 1e-4 * (p * theta ** (0.8 - a4) + 1.1 * e * theta)  # (6a)
    width = np.sqrt(width**2 + 2.25e-6)  # (6b), Zeeman splitting
    delta = (a5 + a6 * theta) * 1e-4 * (p + e) * theta**0.8  # (7)
    shape = _line_shape(f, f0, width, delta)
    d = 5.6e-4 * (p + e) * theta**0.8  # (9)
    debye = (
        f
        * p
        * theta**2
        * (
            6.14e-5 / (d * (1.0 + (f / d) ** 2))
            + 1.4e-12 * p * theta**1.5 / (1.0 + 1.9e-5 * f**1.5)
        )
    )  # (8)
    oxygen = 0.1820 * f * (float(np.sum(strength * shape)) + debye)  # (1), (2a)

    f0, b1, b2, b3, b4, b5, b6 = _WATER_VAPOUR.T
    strength = b1 * 1e-1 * e * theta**3.5 * np.exp(b2 * (1.0 - theta))  # (3)
    width = b3 * 1e-4 * (p * theta**b4 + b5 * e * theta**b6)  # (6a)
    width = 0.535 * width + np.sqrt(
        0.217 * width**2 + 2.1316e-12 * f0**2 / theta
    )  # (6b), Doppler broadening
    shape = _line_shape(f, f0, width, 0.0)
    water_vapour = 0.1820 * f * float(np.sum(strength * shape))  # (1), (2b)
    return oxygen, water_vapour


def _line_shape(
    f: float, f0: np.ndarray, width: np.ndarray, delta: np.ndarray | float
) -> np.ndarray:
    """Line-shape factor, P.676-13 equation (5)."""
    return np.asarray(
        f
        / f0
        * (
            (width - delta * (f0 - f)) / ((f0 - f) ** 2 + width**2)
            + (width - delta * (f0 + f)) / ((f0 + f) ** 2 + width**2)
        )
    )


# P.838-3 Tables 1-4: (a_j, b_j, c_j) rows, then (m, c).
_K_H: Final = (
    (
        (-5.33980, -0.10008, 1.13098),
        (-0.35351, 1.26970, 0.45400),
        (-0.23789, 0.86036, 0.15354),
        (-0.94158, 0.64552, 0.16817),
    ),
    (-0.18961, 0.71147),
)
_K_V: Final = (
    (
        (-3.80595, 0.56934, 0.81061),
        (-3.44965, -0.22911, 0.51059),
        (-0.39902, 0.73042, 0.11899),
        (0.50167, 1.07319, 0.27195),
    ),
    (-0.16398, 0.63297),
)
_ALPHA_H: Final = (
    (
        (-0.14318, 1.82442, -0.55187),
        (0.29591, 0.77564, 0.19822),
        (0.32177, 0.63773, 0.13164),
        (-5.37610, -0.96230, 1.47828),
        (16.1721, -3.29980, 3.43990),
    ),
    (0.67849, -1.95537),
)
_ALPHA_V: Final = (
    (
        (-0.07771, 2.33840, -0.76284),
        (0.56727, 0.95545, 0.54039),
        (-0.20238, 1.14520, 0.26809),
        (-48.2991, 0.791669, 0.116226),
        (48.5833, 0.791459, 0.116479),
    ),
    (-0.053739, 0.83433),
)


def rain_coefficients(
    frequency_hz: float,
    *,
    polarization_tilt_deg: float = 0.0,
    elevation_deg: float = 0.0,
) -> tuple[float, float]:
    """Rain power-law coefficients ``(k, alpha)``, ITU-R P.838-3.

    Equations (2)-(5): ``polarization_tilt_deg`` is 0 for horizontal, 90 for
    vertical and 45 for circular polarization; ``elevation_deg`` is the path
    elevation.  The specific attenuation is ``k * R**alpha`` dB/km for a rain
    rate ``R`` in mm/h.  Valid from 1 to 1000 GHz.
    """
    f = frequency_hz / 1.0e9
    if not 1.0 <= f <= 1000.0:
        raise ValueError("P.838-3 covers 1-1000 GHz")
    log_f = math.log10(f)

    def fit(
        table: tuple[tuple[tuple[float, float, float], ...], tuple[float, float]],
    ) -> float:
        rows, (m, c) = table
        return (
            sum(a * math.exp(-(((log_f - b) / cc) ** 2)) for a, b, cc in rows)
            + m * log_f
            + c
        )

    k_h = 10.0 ** fit(_K_H)  # (2)
    k_v = 10.0 ** fit(_K_V)
    alpha_h = fit(_ALPHA_H)  # (3)
    alpha_v = fit(_ALPHA_V)
    weight = math.cos(math.radians(elevation_deg)) ** 2 * math.cos(
        math.radians(2.0 * polarization_tilt_deg)
    )
    k = (k_h + k_v + (k_h - k_v) * weight) / 2.0  # (4)
    k_alpha_h, k_alpha_v = k_h * alpha_h, k_v * alpha_v
    alpha = (k_alpha_h + k_alpha_v + (k_alpha_h - k_alpha_v) * weight) / (2 * k)  # (5)
    return k, alpha
