"""Antenna (element) models of increasing sophistication.

* :class:`ConstantGainAntenna` -- just a boresight gain. The simplest useful
  model; you still supply beamwidths so clutter cell sizing works.
* :class:`GaussianBeamAntenna` -- a separable parabolic-in-dB main beam derived
  from the azimuth/elevation 3 dB beamwidths, with a sidelobe floor.
* :class:`PatternCutAntenna` -- separable azimuth and elevation cuts, each given
  as tabulated gain-vs-angle (exactly what the Huber+Suhner SENCITY datasheets
  plot).
* :class:`PatternUVAntenna` -- a full gain map over (azimuth, elevation),
  bilinearly interpolated, for when the complete pattern is available.

All report *element* gain; coherent array gain is handled in the processing
model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, cast

import numpy as np
import numpy.typing as npt
from scipy.interpolate import RegularGridInterpolator

from .units import FloatOrArray


@dataclass(frozen=True)
class ConstantGainAntenna:
    """Isotropic-within-the-beam model: boresight gain in every direction."""

    boresight_gain_dbi: float
    beamwidth_az_deg: float = 90.0
    beamwidth_el_deg: float = 90.0

    def gain_dbi(
        self, azimuth_deg: FloatOrArray, elevation_deg: FloatOrArray
    ) -> FloatOrArray:
        return self.boresight_gain_dbi


@dataclass(frozen=True)
class GaussianBeamAntenna:
    """Separable main beam: ``-12 (theta / HPBW)^2`` dB on each axis.

    Down 3 dB at the half-beamwidth on each axis, clamped to ``sidelobe_floor``.
    A pragmatic stand-in when only the beamwidths and peak gain are known.
    """

    boresight_gain_dbi: float
    beamwidth_az_deg: float
    beamwidth_el_deg: float
    sidelobe_floor_dbi: float = -30.0

    def gain_dbi(
        self, azimuth_deg: FloatOrArray, elevation_deg: FloatOrArray
    ) -> FloatOrArray:
        az = np.asarray(azimuth_deg, dtype=float)
        el = np.asarray(elevation_deg, dtype=float)
        roll_off = (
            12.0 * (az / self.beamwidth_az_deg) ** 2
            + 12.0 * (el / self.beamwidth_el_deg) ** 2
        )
        gain = np.maximum(self.boresight_gain_dbi - roll_off, self.sidelobe_floor_dbi)
        return cast(FloatOrArray, gain)


@dataclass(frozen=True)
class PatternCutAntenna:
    """Separable antenna built from azimuth and elevation pattern cuts.

    Parameters
    ----------
    boresight_gain_dbi:
        Peak gain [dBi].
    az_angles_deg, az_relative_db:
        Azimuth cut: angles and *relative* gain (dB below peak, <= 0) at those
        angles.  Linearly interpolated; clamped to the endpoints outside range.
    el_angles_deg, el_relative_db:
        Elevation cut, same convention.

    The total gain is ``peak + rel_az(az) + rel_el(el)`` -- a separability
    assumption that is good near boresight and a reasonable engineering
    approximation elsewhere.
    """

    boresight_gain_dbi: float
    az_angles_deg: npt.NDArray[np.float64]
    az_relative_db: npt.NDArray[np.float64]
    el_angles_deg: npt.NDArray[np.float64]
    el_relative_db: npt.NDArray[np.float64]
    beamwidth_az_deg: float = float("nan")
    beamwidth_el_deg: float = float("nan")

    @classmethod
    def from_cuts(
        cls,
        boresight_gain_dbi: float,
        az_cut: Sequence[tuple[float, float]],
        el_cut: Sequence[tuple[float, float]],
    ) -> "PatternCutAntenna":
        """Build from ``[(angle_deg, relative_db), ...]`` cut definitions."""
        az = np.array(sorted(az_cut), dtype=float)
        el = np.array(sorted(el_cut), dtype=float)
        return cls(
            boresight_gain_dbi=boresight_gain_dbi,
            az_angles_deg=az[:, 0],
            az_relative_db=az[:, 1],
            el_angles_deg=el[:, 0],
            el_relative_db=el[:, 1],
            beamwidth_az_deg=_estimate_beamwidth(az[:, 0], az[:, 1]),
            beamwidth_el_deg=_estimate_beamwidth(el[:, 0], el[:, 1]),
        )

    def gain_dbi(
        self, azimuth_deg: FloatOrArray, elevation_deg: FloatOrArray
    ) -> FloatOrArray:
        rel_az = np.interp(azimuth_deg, self.az_angles_deg, self.az_relative_db)
        rel_el = np.interp(elevation_deg, self.el_angles_deg, self.el_relative_db)
        return cast(FloatOrArray, self.boresight_gain_dbi + rel_az + rel_el)


class PatternUVAntenna:
    """Full 2-D gain pattern over (azimuth, elevation), bilinearly interpolated.

    Parameters
    ----------
    azimuth_grid_deg, elevation_grid_deg:
        Strictly increasing 1-D grids.
    gain_grid_dbi:
        ``(len(az), len(el))`` array of gains [dBi].
    """

    def __init__(
        self,
        azimuth_grid_deg: npt.NDArray[np.float64],
        elevation_grid_deg: npt.NDArray[np.float64],
        gain_grid_dbi: npt.NDArray[np.float64],
    ) -> None:
        self._az = np.asarray(azimuth_grid_deg, dtype=float)
        self._el = np.asarray(elevation_grid_deg, dtype=float)
        self._gain = np.asarray(gain_grid_dbi, dtype=float)
        if self._gain.shape != (self._az.size, self._el.size):
            raise ValueError("gain_grid_dbi shape must be (n_az, n_el)")
        self._interp = RegularGridInterpolator(
            (self._az, self._el),
            self._gain,
            method="linear",
            bounds_error=False,
            fill_value=None,  # clamp to nearest edge instead of NaN
        )
        self.boresight_gain_dbi = float(self._gain.max())
        self.beamwidth_az_deg = _estimate_beamwidth(
            self._az, self._gain[:, int(np.argmin(np.abs(self._el)))]
        )
        self.beamwidth_el_deg = _estimate_beamwidth(
            self._el, self._gain[int(np.argmin(np.abs(self._az))), :]
        )

    def gain_dbi(
        self, azimuth_deg: FloatOrArray, elevation_deg: FloatOrArray
    ) -> FloatOrArray:
        az, el = np.broadcast_arrays(
            np.asarray(azimuth_deg, dtype=float),
            np.asarray(elevation_deg, dtype=float),
        )
        points = np.column_stack([az.ravel(), el.ravel()])
        values = np.asarray(self._interp(points), dtype=float).reshape(az.shape)
        return float(values) if values.ndim == 0 else cast(FloatOrArray, values)


def _estimate_beamwidth(
    angles_deg: npt.NDArray[np.float64], gain_db: npt.NDArray[np.float64]
) -> float:
    """Estimate the 3 dB beamwidth from a cut (peak-relative or absolute dB)."""
    rel = gain_db - gain_db.max()
    above = angles_deg[rel >= -3.0]
    if above.size < 2:
        return float("nan")
    return float(above.max() - above.min())
