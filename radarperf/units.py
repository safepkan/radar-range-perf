"""Physical constants and unit-conversion helpers.

Everything in :mod:`radarperf` is stored internally in SI units (watts,
metres, hertz, square metres, kelvin, seconds).  Decibels appear only at the
boundaries -- when a user supplies a gain/loss/power figure or when a result is
formatted for reading.  The helpers below are the single place those
conversions live so the rest of the code never sprinkles ``10 ** (x / 10)``
around.

All conversion helpers accept either Python floats or NumPy arrays and return
the same shape, so they can be used transparently inside vectorised sweeps.
"""

from __future__ import annotations

from typing import TypeVar, Union, cast

import numpy as np
import numpy.typing as npt

#: Speed of light in vacuum [m/s].
SPEED_OF_LIGHT: float = 299_792_458.0

#: Boltzmann constant [J/K].
BOLTZMANN: float = 1.380649e-23

#: IEEE reference ("standard") temperature used with noise figure [K].
REFERENCE_TEMPERATURE: float = 290.0

#: Convenience: thermal noise power spectral density k * T0 [W/Hz] at T0.
THERMAL_NOISE_PSD: float = BOLTZMANN * REFERENCE_TEMPERATURE

FloatOrArray = Union[float, npt.NDArray[np.float64]]
_T = TypeVar("_T", float, npt.NDArray[np.float64])


def db_to_linear(value_db: _T) -> _T:
    """Convert a power ratio expressed in decibels to a linear ratio."""
    ratio = 10.0 ** (np.asarray(value_db, dtype=float) / 10.0)
    return cast(_T, ratio)  # type: ignore[redundant-cast]


def linear_to_db(value_linear: _T) -> _T:
    """Convert a linear power ratio to decibels.

    Non-positive inputs map to ``-inf`` rather than raising, which keeps
    vectorised sweeps over regions of zero signal well behaved.
    """
    arr = np.asarray(value_linear, dtype=float)
    with np.errstate(divide="ignore"):
        out = 10.0 * np.log10(arr)
    return cast(_T, out)  # type: ignore[redundant-cast]


def dbm_to_watt(power_dbm: _T) -> _T:
    """Convert power in dBm to watts."""
    watts = 10.0 ** (np.asarray(power_dbm, dtype=float) / 10.0) / 1000.0
    return cast(_T, watts)  # type: ignore[redundant-cast]


def watt_to_dbm(power_w: _T) -> _T:
    """Convert power in watts to dBm."""
    arr = np.asarray(power_w, dtype=float)
    with np.errstate(divide="ignore"):
        out = 10.0 * np.log10(arr * 1000.0)
    return cast(_T, out)  # type: ignore[redundant-cast]


def dbi_to_linear(gain_dbi: _T) -> _T:
    """Convert an antenna gain in dBi to a linear gain (alias of dB->linear)."""
    return db_to_linear(gain_dbi)
