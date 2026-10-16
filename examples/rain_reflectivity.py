"""Print the tables of docs/rain_clutter.md: rain's reflectivity at 77 GHz.

Usage:
    venv/bin/python examples/rain_reflectivity.py
"""

from __future__ import annotations

import cmath
import math

from radarperf.itu import rain_coefficients
from radarperf.rain import rain_scattering, water_permittivity

FREQUENCY_HZ = 77e9
TEMPERATURE_C = 10.0
RAIN_RATES = (1.0, 2.0, 5.0, 10.0, 20.0, 25.0, 50.0, 100.0)


def scientific(value: float) -> str:
    """``1.05 × 10⁻⁴`` for 1.05e-4."""
    exponent = math.floor(math.log10(value))
    superscript = str(exponent).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
    return f"{value / 10.0**exponent:.2f} × 10{superscript}"


def main() -> None:
    eps = water_permittivity(FREQUENCY_HZ, TEMPERATURE_C)
    m = cmath.sqrt(eps)
    k2 = abs((eps - 1.0) / (eps + 2.0)) ** 2
    eps_3 = water_permittivity(3e9, TEMPERATURE_C)
    k2_3 = abs((eps_3 - 1.0) / (eps_3 + 2.0)) ** 2
    print(f"Water at {TEMPERATURE_C:g} C, {FREQUENCY_HZ / 1e9:g} GHz:")
    print(f"  eps = {eps.real:.2f} + {eps.imag:.2f}i, m = {m.real:.2f} + {m.imag:.2f}i")
    print(f"  |K|^2 = {k2:.3f} (at 3 GHz: {k2_3:.3f})")
    print()
    print("| Rain rate | eta | 10 log10 eta | Z_e | 200 R^1.6 | 130 R^0.65 |")
    print("|---:|---:|---:|---:|---:|---:|")
    rows = [
        rain_scattering(r, FREQUENCY_HZ, temperature_c=TEMPERATURE_C)
        for r in RAIN_RATES
    ]
    for s in rows:
        r = s.rain_rate_mm_per_hr
        print(
            f"| {r:g} mm/h | {scientific(s.volume_reflectivity_per_m)} m⁻¹"
            f" | {s.volume_reflectivity_db:.1f} dB"
            f" | {s.equivalent_reflectivity_dbz:.1f} dBZ"
            f" | {10 * math.log10(200 * r**1.6):.1f} dBZ"
            f" | {10 * math.log10(130 * r**0.65):.1f} dBZ |"
        )
    print()
    k, alpha = rain_coefficients(FREQUENCY_HZ)
    print(
        "| Rain rate | Attenuation, Mie | P.838-3 | Fall speed, mean | RMS | Water flux |"
    )
    print("|---:|---:|---:|---:|---:|---:|")
    for s in rows:
        r = s.rain_rate_mm_per_hr
        print(
            f"| {r:g} mm/h | {s.specific_attenuation_db_per_km:.2f} dB/km"
            f" | {k * r**alpha:.2f} dB/km"
            f" | {s.mean_fall_speed_mps:.2f} m/s | {s.rms_fall_speed_mps:.2f} m/s"
            f" | {s.water_flux_mm_per_hr:.3g} mm/h |"
        )
    print()
    print("Change in 10 log10 eta from 10 C:")
    for t in (0.0, 20.0):
        changes = [
            rain_scattering(r, FREQUENCY_HZ, temperature_c=t).volume_reflectivity_db
            - s.volume_reflectivity_db
            for r, s in zip(RAIN_RATES, rows)
        ]
        print(f"  {t:g} C: {min(changes):+.2f} to {max(changes):+.2f} dB")
    for f in (76e9, 81e9):
        s = rain_scattering(10.0, f, temperature_c=TEMPERATURE_C)
        print(f"  at {f / 1e9:g} GHz, 10 mm/h: {s.volume_reflectivity_db:.2f} dB")


if __name__ == "__main__":
    main()
