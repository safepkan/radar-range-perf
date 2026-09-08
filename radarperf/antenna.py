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
* :class:`UniformRectangularApertureAntenna` -- the analytical sinc pattern of
  a uniformly illuminated continuous rectangular aperture.
* :class:`RectangularArrayAntenna` -- a uniformly spaced rectangular aperture
  with arbitrary complex element excitations. Its full 2-D array factor is
  evaluated from a zero-padded FFT.
* :class:`UniformArrayAntenna` -- a steerable ULA/URA layer applied on top of
  any element or subarray pattern, with coherent peak gain left to processing.
* :class:`MultiBeamUniformArrayAntenna` -- the best-beam envelope of several
  simultaneously formed beams from the same ULA/URA.
* :class:`AntennaPair` -- a transmit/receive antenna pair, as a real module
  ships (or as two designs combined during a study).  This is what the engine
  takes as its ``antenna``.

:func:`load_pattern_cut_csv` builds a single :class:`PatternCutAntenna` from a CSV
table of gain-vs-angle cuts, and :func:`load_antenna_pair_csv` builds a TX/RX
:class:`AntennaPair` from a table with separate transmit/receive columns; the
:func:`sencity_this_ii` and :func:`sencity_farad_iv` presets use the latter to
load the digitised Huber+Suhner SENCITY datasheet patterns shipped under
``radarperf/data/``.

The simple and tabulated models normally report one channel's element/subarray
gain, with coherent array gain handled in processing. ``RectangularArrayAntenna``
can instead report a complete aperture pattern; use the matching full-aperture
processing bookkeeping described by ``StandardProcessing``.
"""

from __future__ import annotations

import csv
import importlib.resources
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import IO, Optional, Sequence, cast

import numpy as np
import numpy.typing as npt
from scipy.interpolate import RegularGridInterpolator
from scipy.ndimage import map_coordinates

from .protocols import Antenna
from .units import SPEED_OF_LIGHT, FloatOrArray, linear_to_db

# Planes recognised in CSV pattern tables, mapped to azimuth/elevation.
_AZ_PLANES = {"azimuth", "az", "h", "horizontal"}
_EL_PLANES = {"elevation", "el", "v", "vertical"}


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


class UniformRectangularApertureAntenna:
    """Uniformly illuminated continuous rectangular aperture.

    Parameters
    ----------
    horizontal_extent_m, vertical_extent_m:
        Physical aperture extents corresponding to direction cosines ``u``
        (positive left) and ``v`` (positive up).
    center_frequency_hz:
        Frequency at which the pattern and directivity are evaluated.
    aperture_efficiency:
        Fraction of the ideal uniformly illuminated aperture directivity. The
        boresight gain is ``efficiency * 4*pi*area/wavelength**2``.

    The normalized power pattern is separable:
    ``sinc(extent_u*u/wavelength)**2 * sinc(extent_v*v/wavelength)**2``, where
    NumPy's normalized sinc convention is used. This is an ideal aperture
    model; it does not include element patterns, coupling, edge effects or
    scan-dependent embedded-element behavior.
    """

    def __init__(
        self,
        horizontal_extent_m: float,
        vertical_extent_m: float,
        *,
        center_frequency_hz: float,
        aperture_efficiency: float = 1.0,
    ) -> None:
        if not np.isfinite(horizontal_extent_m) or horizontal_extent_m <= 0.0:
            raise ValueError("horizontal_extent_m must be finite and positive")
        if not np.isfinite(vertical_extent_m) or vertical_extent_m <= 0.0:
            raise ValueError("vertical_extent_m must be finite and positive")
        if not np.isfinite(center_frequency_hz) or center_frequency_hz <= 0.0:
            raise ValueError("center_frequency_hz must be finite and positive")
        if (
            not np.isfinite(aperture_efficiency)
            or aperture_efficiency <= 0.0
            or aperture_efficiency > 1.0
        ):
            raise ValueError("aperture_efficiency must be within (0, 1]")

        self.horizontal_extent_m = float(horizontal_extent_m)
        self.vertical_extent_m = float(vertical_extent_m)
        self.center_frequency_hz = float(center_frequency_hz)
        self.aperture_efficiency = float(aperture_efficiency)
        self._wavelength_m = SPEED_OF_LIGHT / self.center_frequency_hz

        directivity = (
            self.aperture_efficiency
            * 4.0
            * np.pi
            * self.horizontal_extent_m
            * self.vertical_extent_m
            / self._wavelength_m**2
        )
        self.boresight_gain_dbi = float(linear_to_db(directivity))
        angles = np.linspace(-90.0, 90.0, 7201)
        zeros = np.zeros_like(angles)
        self.beamwidth_az_deg = _estimate_beamwidth(
            angles, np.asarray(self.gain_dbi(angles, zeros), dtype=float)
        )
        self.beamwidth_el_deg = _estimate_beamwidth(
            angles, np.asarray(self.gain_dbi(zeros, angles), dtype=float)
        )

    def gain_dbi_uv(self, u: FloatOrArray, v: FloatOrArray) -> FloatOrArray:
        """Gain [dBi] at broadcastable direction cosines ``u`` and ``v``."""
        u_array, v_array = np.broadcast_arrays(
            np.asarray(u, dtype=float), np.asarray(v, dtype=float)
        )
        horizontal_voltage = np.sinc(
            self.horizontal_extent_m * u_array / self._wavelength_m
        )
        vertical_voltage = np.sinc(
            self.vertical_extent_m * v_array / self._wavelength_m
        )
        relative_power = (horizontal_voltage * vertical_voltage) ** 2
        gain = self.boresight_gain_dbi + linear_to_db(
            np.maximum(relative_power, 1.0e-30)
        )
        return float(gain) if gain.ndim == 0 else cast(FloatOrArray, gain)

    def gain_dbi(
        self, azimuth_deg: FloatOrArray, elevation_deg: FloatOrArray
    ) -> FloatOrArray:
        azimuth = np.radians(np.asarray(azimuth_deg, dtype=float))
        elevation = np.radians(np.asarray(elevation_deg, dtype=float))
        u = np.sin(azimuth) * np.cos(elevation)
        v = np.sin(elevation)
        return self.gain_dbi_uv(cast(FloatOrArray, u), cast(FloatOrArray, v))


@dataclass(frozen=True)
class PatternCutAntenna:
    """Separable antenna built from azimuth and elevation pattern cuts.

    Parameters
    ----------
    boresight_gain_dbi:
        On-axis gain [dBi].
    az_angles_deg, az_relative_db:
        Azimuth cut: angles and *relative* gain (dB relative to boresight,
        usually <= 0) at those angles.  Linearly interpolated; clamped to the
        endpoints outside range.
    el_angles_deg, el_relative_db:
        Elevation cut, same convention.

    The total gain is ``boresight + rel_az(az) + rel_el(el)`` -- a separability
    assumption that is good near boresight and a reasonable engineering
    approximation elsewhere.  Build from tabulated *relative* cuts with
    :meth:`from_cuts`, from *absolute* gain cuts with :meth:`from_absolute_cuts`,
    or from a CSV pattern table with :func:`load_pattern_cut_csv`.
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

    @classmethod
    def from_absolute_cuts(
        cls,
        az_cut: Sequence[tuple[float, float]],
        el_cut: Sequence[tuple[float, float]],
    ) -> "PatternCutAntenna":
        """Build from ``[(angle_deg, absolute_gain_dbi), ...]`` cuts.

        Each cut is referenced to its own on-axis (0 deg) gain to form the
        relative pattern, and the reported ``boresight_gain_dbi`` is the mean of
        the two on-axis gains -- they nominally agree, but independently
        digitised cuts differ by a few tenths of a dB, and averaging avoids
        favouring one plane.  (A consequence of separability: where a cut ripples
        slightly above its on-axis value the relative gain is slightly positive.)
        """
        az = np.array(sorted(az_cut), dtype=float)
        el = np.array(sorted(el_cut), dtype=float)
        az_boresight = float(np.interp(0.0, az[:, 0], az[:, 1]))
        el_boresight = float(np.interp(0.0, el[:, 0], el[:, 1]))
        return cls(
            boresight_gain_dbi=0.5 * (az_boresight + el_boresight),
            az_angles_deg=az[:, 0],
            az_relative_db=az[:, 1] - az_boresight,
            el_angles_deg=el[:, 0],
            el_relative_db=el[:, 1] - el_boresight,
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


class RectangularArrayAntenna:
    """Uniform rectangular array with arbitrary complex element excitations.

    Parameters
    ----------
    horizontal_positions_m, vertical_positions_m:
        Strictly increasing, uniformly spaced radiator coordinates. Horizontal
        positions correspond to direction cosine ``u`` (positive left), and
        vertical positions to ``v`` (positive up).
    excitations:
        Complex aperture weights with shape ``(n_horizontal, n_vertical)``.
        Their absolute scale is immaterial: the array factor is normalized by
        total excitation power, so changing the taper redistributes a fixed
        total input power rather than introducing an insertion loss.
    center_frequency_hz:
        Frequency at which the spatial pattern is evaluated.
    element_gain_dbi:
        Boresight gain of one radiator. The resulting array gain is this value
        plus ``10 log10(|AF|^2 / sum(|w|^2))``.
    fft_size:
        Zero-padded FFT size along both aperture axes. Larger values improve
        interpolation around narrow lobes and nulls.

    The FFT is periodic in spatial frequency. This implementation wraps that
    periodic result when evaluating visible direction cosines outside the
    principal FFT interval, which is needed when element spacing exceeds half
    a wavelength.

    Beamwidths describe the contiguous 3 dB lobe around the strongest sampled
    peak in each principal cut, not the span across separate grating lobes.
    Equal-height peaks are resolved by choosing the one closest to boresight.
    """

    def __init__(
        self,
        horizontal_positions_m: npt.ArrayLike,
        vertical_positions_m: npt.ArrayLike,
        excitations: npt.ArrayLike,
        *,
        center_frequency_hz: float,
        element_gain_dbi: float = 0.0,
        fft_size: int = 1024,
    ) -> None:
        horizontal = np.asarray(horizontal_positions_m, dtype=float)
        vertical = np.asarray(vertical_positions_m, dtype=float)
        weights = np.asarray(excitations, dtype=complex)

        _validate_uniform_axis(horizontal, "horizontal_positions_m")
        _validate_uniform_axis(vertical, "vertical_positions_m")
        if weights.shape != (horizontal.size, vertical.size):
            raise ValueError("excitations shape must be (n_horizontal, n_vertical)")
        if not np.all(np.isfinite(weights.real)) or not np.all(
            np.isfinite(weights.imag)
        ):
            raise ValueError("excitations must be finite")
        excitation_power = float(np.sum(np.abs(weights) ** 2))
        if excitation_power <= 0.0:
            raise ValueError("at least one excitation must be nonzero")
        if not np.isfinite(center_frequency_hz) or center_frequency_hz <= 0.0:
            raise ValueError("center_frequency_hz must be finite and positive")
        if not np.isfinite(element_gain_dbi):
            raise ValueError("element_gain_dbi must be finite")
        if fft_size < max(weights.shape):
            raise ValueError("fft_size must be at least as large as the array")

        self.horizontal_positions_m = horizontal.copy()
        self.vertical_positions_m = vertical.copy()
        self.excitations = weights.copy()
        self.horizontal_positions_m.flags.writeable = False
        self.vertical_positions_m.flags.writeable = False
        self.excitations.flags.writeable = False
        self.center_frequency_hz = float(center_frequency_hz)
        self.element_gain_dbi = float(element_gain_dbi)
        self.fft_size = int(fft_size)
        self._excitation_power = excitation_power
        self._horizontal_spacing_m = float(np.diff(horizontal)[0])
        self._vertical_spacing_m = float(np.diff(vertical)[0])
        self._wavelength_m = SPEED_OF_LIGHT / self.center_frequency_hz
        self._fft_power = self._make_fft_power()

        boresight_array_gain = abs(np.sum(weights)) ** 2 / excitation_power
        self.boresight_gain_dbi = self.element_gain_dbi + float(
            linear_to_db(boresight_array_gain)
        )
        angles = np.linspace(-90.0, 90.0, 7201)
        zeros = np.zeros_like(angles)
        self.beamwidth_az_deg = _estimate_main_lobe_beamwidth(
            angles, np.asarray(self.gain_dbi(angles, zeros), dtype=float)
        )
        self.beamwidth_el_deg = _estimate_main_lobe_beamwidth(
            angles, np.asarray(self.gain_dbi(zeros, angles), dtype=float)
        )

    @classmethod
    def from_element_list(
        cls,
        horizontal_positions_m: npt.ArrayLike,
        vertical_positions_m: npt.ArrayLike,
        excitations: npt.ArrayLike,
        *,
        center_frequency_hz: float,
        element_gain_dbi: float = 0.0,
        fft_size: int = 1024,
    ) -> "RectangularArrayAntenna":
        """Build a rectangular grid from one coordinate pair per excitation.

        The input order is arbitrary. Every combination of unique horizontal
        and vertical coordinates must occur exactly once.
        """
        horizontal = np.asarray(horizontal_positions_m, dtype=float)
        vertical = np.asarray(vertical_positions_m, dtype=float)
        weights = np.asarray(excitations, dtype=complex)
        if horizontal.ndim != 1 or vertical.ndim != 1 or weights.ndim != 1:
            raise ValueError("element-list coordinates and excitations must be 1-D")
        if not (horizontal.size == vertical.size == weights.size):
            raise ValueError(
                "element-list coordinates and excitations must have equal lengths"
            )

        horizontal_axis = np.unique(horizontal)
        vertical_axis = np.unique(vertical)
        if horizontal.size != horizontal_axis.size * vertical_axis.size:
            raise ValueError(
                "element list does not describe a complete rectangular grid"
            )

        grid = np.empty((horizontal_axis.size, vertical_axis.size), dtype=complex)
        occupied = np.zeros(grid.shape, dtype=bool)
        horizontal_indices = np.searchsorted(horizontal_axis, horizontal)
        vertical_indices = np.searchsorted(vertical_axis, vertical)
        for h_index, v_index, weight in zip(
            horizontal_indices, vertical_indices, weights, strict=True
        ):
            if occupied[h_index, v_index]:
                raise ValueError("element list contains a duplicate coordinate")
            grid[h_index, v_index] = weight
            occupied[h_index, v_index] = True
        if not bool(np.all(occupied)):
            raise ValueError(
                "element list does not describe a complete rectangular grid"
            )

        return cls(
            horizontal_axis,
            vertical_axis,
            grid,
            center_frequency_hz=center_frequency_hz,
            element_gain_dbi=element_gain_dbi,
            fft_size=fft_size,
        )

    @property
    def array_factor_boresight_gain_db(self) -> float:
        """Boresight gain from coherent array combination alone [dB]."""
        return self.boresight_gain_dbi - self.element_gain_dbi

    def _make_fft_power(self) -> npt.NDArray[np.float64]:
        spectrum = np.fft.fftshift(
            np.fft.fft2(self.excitations, s=(self.fft_size, self.fft_size))
        )
        return np.asarray(np.abs(spectrum) ** 2 / self._excitation_power, dtype=float)

    def gain_dbi_uv(self, u: FloatOrArray, v: FloatOrArray) -> FloatOrArray:
        """Gain [dBi] at broadcastable direction cosines ``u`` and ``v``."""
        u_array, v_array = np.broadcast_arrays(
            np.asarray(u, dtype=float), np.asarray(v, dtype=float)
        )
        horizontal_frequency = self._wrap_spatial_frequency(
            u_array * self._horizontal_spacing_m / self._wavelength_m
        )
        vertical_frequency = self._wrap_spatial_frequency(
            v_array * self._vertical_spacing_m / self._wavelength_m
        )
        horizontal_index = horizontal_frequency * self.fft_size + self.fft_size // 2
        vertical_index = vertical_frequency * self.fft_size + self.fft_size // 2
        coordinates = np.vstack((horizontal_index.ravel(), vertical_index.ravel()))
        power_gain = map_coordinates(
            self._fft_power,
            coordinates,
            order=1,
            mode="grid-wrap",
        ).reshape(u_array.shape)
        gain = self.element_gain_dbi + linear_to_db(np.maximum(power_gain, 1.0e-30))
        return float(gain) if gain.ndim == 0 else cast(FloatOrArray, gain)

    def gain_dbi(
        self, azimuth_deg: FloatOrArray, elevation_deg: FloatOrArray
    ) -> FloatOrArray:
        azimuth = np.radians(np.asarray(azimuth_deg, dtype=float))
        elevation = np.radians(np.asarray(elevation_deg, dtype=float))
        u = np.sin(azimuth) * np.cos(elevation)
        v = np.sin(elevation)
        return self.gain_dbi_uv(cast(FloatOrArray, u), cast(FloatOrArray, v))

    @staticmethod
    def _wrap_spatial_frequency(
        frequency: npt.NDArray[np.float64],
    ) -> npt.NDArray[np.float64]:
        return np.asarray((frequency + 0.5) % 1.0 - 0.5, dtype=float)


class UniformArrayAntenna:
    """Steered uniform-array factor layered over an element/subarray pattern.

    This represents a ULA (one count is 1) or URA whose channels all have the
    same ``element`` pattern and are combined coherently toward one steering
    direction. Its gain is the element gain plus an array factor normalized to
    0 dB in the steering direction. The ideal coherent peak gain -- ``n`` for
    RX combining, or the directivity part of coherent TX -- remains in the
    processing model. This separation preserves the existing link-budget
    bookkeeping while adding the off-beam loss that an ideal constant gain
    previously omitted.

    Horizontal spacing corresponds to direction cosine ``u`` (positive left),
    and vertical spacing to ``v`` (positive up).
    """

    def __init__(
        self,
        element: Antenna,
        *,
        horizontal_count: int,
        vertical_count: int,
        horizontal_spacing_m: float = 0.0,
        vertical_spacing_m: float = 0.0,
        center_frequency_hz: float,
        steering_azimuth_deg: float = 0.0,
        steering_elevation_deg: float = 0.0,
    ) -> None:
        _validate_uniform_array_axis(
            horizontal_count, horizontal_spacing_m, "horizontal"
        )
        _validate_uniform_array_axis(vertical_count, vertical_spacing_m, "vertical")
        if not np.isfinite(center_frequency_hz) or center_frequency_hz <= 0.0:
            raise ValueError("center_frequency_hz must be finite and positive")
        if not -90.0 <= steering_azimuth_deg <= 90.0:
            raise ValueError("steering_azimuth_deg must be within [-90, 90]")
        if not -90.0 <= steering_elevation_deg <= 90.0:
            raise ValueError("steering_elevation_deg must be within [-90, 90]")

        self.element = element
        self.horizontal_count = horizontal_count
        self.vertical_count = vertical_count
        self.horizontal_spacing_m = float(horizontal_spacing_m)
        self.vertical_spacing_m = float(vertical_spacing_m)
        self.center_frequency_hz = float(center_frequency_hz)
        self.steering_azimuth_deg = float(steering_azimuth_deg)
        self.steering_elevation_deg = float(steering_elevation_deg)
        self._wavelength_m = SPEED_OF_LIGHT / self.center_frequency_hz

        steering_azimuth = np.radians(self.steering_azimuth_deg)
        steering_elevation = np.radians(self.steering_elevation_deg)
        self.steering_u = float(np.sin(steering_azimuth) * np.cos(steering_elevation))
        self.steering_v = float(np.sin(steering_elevation))
        self.boresight_gain_dbi = float(self.gain_dbi(0.0, 0.0))

        angles = np.linspace(-90.0, 90.0, 7201)
        az_gain = np.asarray(
            self.gain_dbi(angles, self.steering_elevation_deg), dtype=float
        )
        el_gain = np.asarray(
            self.gain_dbi(self.steering_azimuth_deg, angles), dtype=float
        )
        self.beamwidth_az_deg = _estimate_main_lobe_beamwidth(
            angles, az_gain, self.steering_azimuth_deg
        )
        self.beamwidth_el_deg = _estimate_main_lobe_beamwidth(
            angles, el_gain, self.steering_elevation_deg
        )

    @classmethod
    def from_steering_uv(
        cls,
        element: Antenna,
        *,
        horizontal_count: int,
        vertical_count: int,
        horizontal_spacing_m: float = 0.0,
        vertical_spacing_m: float = 0.0,
        center_frequency_hz: float,
        steering_u: float,
        steering_v: float,
    ) -> "UniformArrayAntenna":
        """Build a beam whose steering direction is given directly in u/v."""
        steering_azimuth_deg, steering_elevation_deg = _angles_from_uv(
            steering_u, steering_v
        )
        return cls(
            element,
            horizontal_count=horizontal_count,
            vertical_count=vertical_count,
            horizontal_spacing_m=horizontal_spacing_m,
            vertical_spacing_m=vertical_spacing_m,
            center_frequency_hz=center_frequency_hz,
            steering_azimuth_deg=steering_azimuth_deg,
            steering_elevation_deg=steering_elevation_deg,
        )

    @property
    def element_count(self) -> int:
        """Number of coherently combined elements/subarrays."""
        return self.horizontal_count * self.vertical_count

    def array_factor_relative_db_uv(
        self, u: FloatOrArray, v: FloatOrArray
    ) -> FloatOrArray:
        """Normalized array factor [dB] at direction cosines ``u`` and ``v``."""
        u_array, v_array = np.broadcast_arrays(
            np.asarray(u, dtype=float), np.asarray(v, dtype=float)
        )
        horizontal_power = _uniform_axis_factor_power(
            self.horizontal_count,
            self.horizontal_spacing_m / self._wavelength_m,
            u_array - self.steering_u,
        )
        vertical_power = _uniform_axis_factor_power(
            self.vertical_count,
            self.vertical_spacing_m / self._wavelength_m,
            v_array - self.steering_v,
        )
        relative_db = linear_to_db(
            np.maximum(horizontal_power * vertical_power, 1.0e-30)
        )
        return (
            float(relative_db)
            if relative_db.ndim == 0
            else cast(FloatOrArray, relative_db)
        )

    def gain_dbi(
        self, azimuth_deg: FloatOrArray, elevation_deg: FloatOrArray
    ) -> FloatOrArray:
        azimuth = np.radians(np.asarray(azimuth_deg, dtype=float))
        elevation = np.radians(np.asarray(elevation_deg, dtype=float))
        u = np.sin(azimuth) * np.cos(elevation)
        v = np.sin(elevation)
        element_gain = np.asarray(
            self.element.gain_dbi(azimuth_deg, elevation_deg), dtype=float
        )
        gain = element_gain + np.asarray(
            self.array_factor_relative_db_uv(
                cast(FloatOrArray, u), cast(FloatOrArray, v)
            ),
            dtype=float,
        )
        return float(gain) if gain.ndim == 0 else cast(FloatOrArray, gain)


class MultiBeamUniformArrayAntenna:
    """Best-beam envelope for several beams formed by one uniform array.

    Each beam uses the same element/subarray pattern, array geometry and ideal
    coherent peak gain, but has its own steering point in u/v. ``gain_dbi``
    returns the maximum gain across beams and ``gain_dbi_per_beam`` exposes the
    individual patterns with the beam index on axis 0.

    This is an optimistic antenna-layer model of "detection in any beam": it
    selects the strongest beam without applying a multiple-testing Pfa penalty
    or modelling correlated receiver noise between beams. Those effects belong
    in a future multi-beam detector model.
    """

    def __init__(
        self,
        element: Antenna,
        *,
        horizontal_count: int,
        vertical_count: int,
        horizontal_spacing_m: float = 0.0,
        vertical_spacing_m: float = 0.0,
        center_frequency_hz: float,
        steering_u: npt.ArrayLike,
        steering_v: npt.ArrayLike,
    ) -> None:
        _validate_uniform_array_axis(
            horizontal_count, horizontal_spacing_m, "horizontal"
        )
        _validate_uniform_array_axis(vertical_count, vertical_spacing_m, "vertical")
        if not np.isfinite(center_frequency_hz) or center_frequency_hz <= 0.0:
            raise ValueError("center_frequency_hz must be finite and positive")
        steering_u_array = np.asarray(steering_u, dtype=float)
        steering_v_array = np.asarray(steering_v, dtype=float)
        if steering_u_array.ndim != 1 or steering_v_array.ndim != 1:
            raise ValueError("steering_u and steering_v must be 1-D")
        if (
            steering_u_array.size == 0
            or steering_u_array.shape != steering_v_array.shape
        ):
            raise ValueError(
                "steering_u and steering_v must have equal nonzero lengths"
            )
        if not np.all(np.isfinite(steering_u_array)) or not np.all(
            np.isfinite(steering_v_array)
        ):
            raise ValueError("steering_u and steering_v must be finite")
        if np.any(steering_u_array**2 + steering_v_array**2 > 1.0):
            raise ValueError("all steering points must lie within the visible u/v disk")

        self.element = element
        self.horizontal_count = horizontal_count
        self.vertical_count = vertical_count
        self.horizontal_spacing_m = float(horizontal_spacing_m)
        self.vertical_spacing_m = float(vertical_spacing_m)
        self.center_frequency_hz = float(center_frequency_hz)
        self.steering_u = steering_u_array.copy()
        self.steering_v = steering_v_array.copy()
        self.steering_u.flags.writeable = False
        self.steering_v.flags.writeable = False
        self._wavelength_m = SPEED_OF_LIGHT / self.center_frequency_hz

        reference_index = int(np.argmin(self.steering_u**2 + self.steering_v**2))
        reference_beam = self.beam(reference_index)
        self.beamwidth_az_deg = reference_beam.beamwidth_az_deg
        self.beamwidth_el_deg = reference_beam.beamwidth_el_deg
        self.boresight_gain_dbi = float(self.gain_dbi(0.0, 0.0))

    @property
    def element_count(self) -> int:
        """Number of coherently combined elements/subarrays per beam."""
        return self.horizontal_count * self.vertical_count

    @property
    def beam_count(self) -> int:
        """Number of simultaneously formed beams."""
        return int(self.steering_u.size)

    def beam(self, index: int) -> UniformArrayAntenna:
        """Construct one individually steered beam by index."""
        if not 0 <= index < self.beam_count:
            raise IndexError("beam index out of range")
        return UniformArrayAntenna.from_steering_uv(
            self.element,
            horizontal_count=self.horizontal_count,
            vertical_count=self.vertical_count,
            horizontal_spacing_m=self.horizontal_spacing_m,
            vertical_spacing_m=self.vertical_spacing_m,
            center_frequency_hz=self.center_frequency_hz,
            steering_u=float(self.steering_u[index]),
            steering_v=float(self.steering_v[index]),
        )

    def gain_dbi_per_beam(
        self, azimuth_deg: FloatOrArray, elevation_deg: FloatOrArray
    ) -> npt.NDArray[np.float64]:
        """Individual gains [dBi], shaped ``(n_beams, *direction_shape)``."""
        azimuth = np.radians(np.asarray(azimuth_deg, dtype=float))
        elevation = np.radians(np.asarray(elevation_deg, dtype=float))
        u, v = np.broadcast_arrays(
            np.sin(azimuth) * np.cos(elevation), np.sin(elevation)
        )
        element_gain = np.broadcast_to(
            np.asarray(self.element.gain_dbi(azimuth_deg, elevation_deg), dtype=float),
            u.shape,
        )
        array_factor_db = self._array_factor_db_uv(u, v, 0, self.beam_count)
        return np.asarray(element_gain[None, ...] + array_factor_db, dtype=float)

    def gain_dbi(
        self, azimuth_deg: FloatOrArray, elevation_deg: FloatOrArray
    ) -> FloatOrArray:
        azimuth = np.radians(np.asarray(azimuth_deg, dtype=float))
        elevation = np.radians(np.asarray(elevation_deg, dtype=float))
        u, v = np.broadcast_arrays(
            np.sin(azimuth) * np.cos(elevation), np.sin(elevation)
        )
        element_gain = np.broadcast_to(
            np.asarray(self.element.gain_dbi(azimuth_deg, elevation_deg), dtype=float),
            u.shape,
        )
        best_factor_db = np.full(u.shape, -np.inf)
        chunk_size = 16
        for start in range(0, self.beam_count, chunk_size):
            stop = min(start + chunk_size, self.beam_count)
            factors = self._array_factor_db_uv(u, v, start, stop)
            best_factor_db = np.maximum(best_factor_db, np.max(factors, axis=0))
        gain = element_gain + best_factor_db
        return float(gain) if gain.ndim == 0 else cast(FloatOrArray, gain)

    def _array_factor_db_uv(
        self,
        u: npt.NDArray[np.float64],
        v: npt.NDArray[np.float64],
        start: int,
        stop: int,
    ) -> npt.NDArray[np.float64]:
        beam_shape = (stop - start,) + (1,) * u.ndim
        steering_u = self.steering_u[start:stop].reshape(beam_shape)
        steering_v = self.steering_v[start:stop].reshape(beam_shape)
        horizontal_power = _uniform_axis_factor_power(
            self.horizontal_count,
            self.horizontal_spacing_m / self._wavelength_m,
            u[None, ...] - steering_u,
        )
        vertical_power = _uniform_axis_factor_power(
            self.vertical_count,
            self.vertical_spacing_m / self._wavelength_m,
            v[None, ...] - steering_v,
        )
        return np.asarray(
            linear_to_db(np.maximum(horizontal_power * vertical_power, 1.0e-30)),
            dtype=float,
        )


def _uniform_axis_factor_power(
    count: int,
    spacing_wavelengths: float,
    direction_offset: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    if count == 1:
        return np.ones_like(direction_offset)
    spatial_frequency = spacing_wavelengths * direction_offset
    denominator = np.sinc(spatial_frequency)
    voltage = np.divide(
        np.sinc(count * spatial_frequency),
        denominator,
        out=np.ones_like(spatial_frequency),
        where=np.abs(denominator) > 1.0e-14,
    )
    return np.asarray(voltage**2, dtype=float)


def _angles_from_uv(u: float, v: float) -> tuple[float, float]:
    if not np.isfinite(u) or not np.isfinite(v) or u**2 + v**2 > 1.0:
        raise ValueError("steering point must lie within the visible u/v disk")
    elevation = np.arcsin(v)
    cos_elevation = np.cos(elevation)
    sin_azimuth = 0.0 if cos_elevation == 0.0 else u / cos_elevation
    azimuth = np.arcsin(np.clip(sin_azimuth, -1.0, 1.0))
    return float(np.degrees(azimuth)), float(np.degrees(elevation))


def _validate_uniform_array_axis(count: int, spacing_m: float, name: str) -> None:
    if count < 1:
        raise ValueError(f"{name}_count must be >= 1")
    if not np.isfinite(spacing_m) or spacing_m < 0.0:
        raise ValueError(f"{name}_spacing_m must be finite and non-negative")
    if count > 1 and spacing_m <= 0.0:
        raise ValueError(f"{name}_spacing_m must be positive when count > 1")


def _validate_uniform_axis(axis: npt.NDArray[np.float64], name: str) -> None:
    if axis.ndim != 1 or axis.size < 2:
        raise ValueError(f"{name} must be a 1-D array with at least two positions")
    if not np.all(np.isfinite(axis)):
        raise ValueError(f"{name} must be finite")
    spacing = np.diff(axis)
    if np.any(spacing <= 0.0):
        raise ValueError(f"{name} must be strictly increasing")
    if not np.allclose(spacing, spacing[0], rtol=1.0e-9, atol=1.0e-12):
        raise ValueError(f"{name} must be uniformly spaced")


def _estimate_main_lobe_beamwidth(
    angles_deg: npt.NDArray[np.float64],
    gain_db: npt.NDArray[np.float64],
    center_deg: float | None = None,
) -> float:
    """Contiguous, peak-relative 3 dB width at a chosen angle or the cut peak.

    Without ``center_deg``, choose the strongest peak; break numerical ties
    by proximity to boresight. With a center, return NaN if it is below the
    cut's peak-relative 3 dB threshold.
    """
    peak_gain_db = gain_db.max()
    above = gain_db >= peak_gain_db - 3.0
    if center_deg is None:
        peak_indices = np.flatnonzero(
            np.isclose(gain_db, peak_gain_db, rtol=0.0, atol=1.0e-12)
        )
        if peak_indices.size == 0:
            return float("nan")
        center_index = int(peak_indices[np.argmin(np.abs(angles_deg[peak_indices]))])
    else:
        center_index = int(np.argmin(np.abs(angles_deg - center_deg)))
    if not above[center_index]:
        return float("nan")
    left = center_index
    right = center_index
    while left > 0 and above[left - 1]:
        left -= 1
    while right + 1 < above.size and above[right + 1]:
        right += 1
    if left == right:
        return float("nan")
    return float(angles_deg[right] - angles_deg[left])


@dataclass(frozen=True)
class AntennaPair:
    """A transmit/receive antenna pair -- the engine's ``antenna``.

    A real module (e.g. a Huber+Suhner SENCITY) ships as one part carrying its
    own transmit and receive elements, so it is natural to keep them together.
    The two members are ordinary :class:`Antenna` objects -- two distinct designs
    combined during a paper study, or (via :meth:`from_element`) the same element
    used for both ports.  Pass the pair straight to the engine::

        radar = Radar(antenna=sencity_this_ii(), ...)
    """

    tx: Antenna
    rx: Antenna
    name: str = ""

    @classmethod
    def from_element(cls, element: Antenna, *, name: str = "") -> "AntennaPair":
        """Pair a single element used for both transmit and receive."""
        return cls(tx=element, rx=element, name=name)


def _estimate_beamwidth(
    angles_deg: npt.NDArray[np.float64], gain_db: npt.NDArray[np.float64]
) -> float:
    """Estimate the 3 dB beamwidth from a cut (peak-relative or absolute dB)."""
    rel = gain_db - gain_db.max()
    above = angles_deg[rel >= -3.0]
    if above.size < 2:
        return float("nan")
    return float(above.max() - above.min())


def _canonical_plane(name: str) -> str:
    """Map a CSV plane label to ``"azimuth"`` or ``"elevation"``."""
    key = name.strip().lower()
    if key in _AZ_PLANES:
        return "azimuth"
    if key in _EL_PLANES:
        return "elevation"
    raise ValueError(f"unrecognised plane {name!r}; expected azimuth or elevation")


def load_pattern_cut_csv(
    source: "str | os.PathLike[str] | IO[str]",
    *,
    gain_column: str = "gain_dbi",
    antenna_name: Optional[str] = None,
    frequency_ghz: Optional[float] = None,
    plane_column: str = "plane",
    angle_column: str = "angle_deg",
) -> PatternCutAntenna:
    """Build a single :class:`PatternCutAntenna` from a CSV table of gain cuts.

    The CSV needs a plane column (values ``azimuth``/``elevation``, or the short
    ``az``/``el``), an angle column [deg] and the named absolute-gain column
    [dBi].  ``antenna_name`` (matched against the ``antenna_name`` or
    ``part_number`` columns) and ``frequency_ghz`` filter files that hold more
    than one antenna or frequency; after filtering, exactly one azimuth and one
    elevation cut must remain.  ``source`` may be a path or an open text file.

    Use :func:`load_antenna_pair_csv` for tables with separate transmit and
    receive gain columns.
    """
    rows = _read_pattern_rows(source, antenna_name, frequency_ghz)
    return _build_pattern_cut(rows, gain_column, plane_column, angle_column)


def load_antenna_pair_csv(
    source: "str | os.PathLike[str] | IO[str]",
    *,
    tx_column: str = "avg_tx_gain_dbi",
    rx_column: str = "avg_rx_gain_dbi",
    name: Optional[str] = None,
    antenna_name: Optional[str] = None,
    frequency_ghz: Optional[float] = None,
    plane_column: str = "plane",
    angle_column: str = "angle_deg",
) -> AntennaPair:
    """Build an :class:`AntennaPair` from a CSV with TX and RX gain columns.

    Loads ``tx_column`` into the pair's transmit element and ``rx_column`` into
    its receive element, so one datasheet table becomes a ready-to-use TX/RX
    pair.  Filtering and the plane/angle columns behave as in
    :func:`load_pattern_cut_csv`.  ``name`` defaults to the file's
    ``antenna_name`` (or ``part_number``).
    """
    rows = _read_pattern_rows(source, antenna_name, frequency_ghz)
    tx = _build_pattern_cut(rows, tx_column, plane_column, angle_column)
    rx = _build_pattern_cut(rows, rx_column, plane_column, angle_column)
    if name is None:
        name = rows[0].get("antenna_name") or rows[0].get("part_number") or ""
    return AntennaPair(tx=tx, rx=rx, name=name)


def _read_pattern_rows(
    source: "str | os.PathLike[str] | IO[str]",
    antenna_name: Optional[str],
    frequency_ghz: Optional[float],
) -> list[dict[str, str]]:
    if isinstance(source, (str, os.PathLike)):
        with open(source, newline="") as handle:
            rows = list(csv.DictReader(handle))
    else:
        rows = list(csv.DictReader(source))
    rows = [r for r in rows if _row_matches(r, antenna_name, frequency_ghz)]
    if not rows:
        raise ValueError("no rows match the requested antenna/frequency")
    _require_unambiguous(rows)
    return rows


def _build_pattern_cut(
    rows: list[dict[str, str]],
    gain_column: str,
    plane_column: str,
    angle_column: str,
) -> PatternCutAntenna:
    missing = {plane_column, angle_column, gain_column} - set(rows[0])
    if missing:
        raise ValueError(f"CSV is missing column(s): {sorted(missing)}")
    by_plane: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for r in rows:
        plane = _canonical_plane(r[plane_column])
        by_plane[plane].append((float(r[angle_column]), float(r[gain_column])))
    if by_plane.keys() != {"azimuth", "elevation"}:
        raise ValueError(
            "CSV must contain exactly one azimuth and one elevation cut; got "
            f"{sorted(by_plane)}"
        )
    return PatternCutAntenna.from_absolute_cuts(
        by_plane["azimuth"], by_plane["elevation"]
    )


def _row_matches(
    row: dict[str, str], antenna_name: Optional[str], frequency_ghz: Optional[float]
) -> bool:
    if antenna_name is not None and antenna_name not in (
        row.get("antenna_name"),
        row.get("part_number"),
    ):
        return False
    if frequency_ghz is not None and row.get("frequency_ghz"):
        return float(row["frequency_ghz"]) == frequency_ghz
    return True


def _require_unambiguous(rows: list[dict[str, str]]) -> None:
    names = {
        name for r in rows if (name := r.get("antenna_name") or r.get("part_number"))
    }
    if len(names) > 1:
        raise ValueError(
            f"CSV holds several antennas {sorted(names)}; pass antenna_name="
        )
    freqs = {r["frequency_ghz"] for r in rows if r.get("frequency_ghz")}
    if len(freqs) > 1:
        raise ValueError(
            f"CSV holds several frequencies {sorted(freqs)}; pass frequency_ghz="
        )


# --- Datasheet presets (digitised pattern cuts; verify before use) -----------


def _load_packaged_pair(filename: str, name: str) -> AntennaPair:
    resource = importlib.resources.files("radarperf").joinpath("data", filename)
    with importlib.resources.as_file(resource) as path:
        return load_antenna_pair_csv(path, name=name)


def sencity_this_ii() -> AntennaPair:
    """Huber+Suhner SENCITY THIS-II radar antenna (art. 1377.99.0701).

    76-81 GHz, 4 TX / 4 RX, horizontal polarisation; MMIC interface for TI
    AWR2544 and similar.  Boresight directivity ~16 dBi.  A broad azimuth fan
    (~140 deg 10-dB beamwidth) paired with a narrow elevation beam (~16 deg
    10-dB beamwidth) and first sidelobes > 20 dB down.

    Returns an :class:`AntennaPair` whose ``tx``/``rx`` elements are the
    datasheet's per-channel ``Avg. TX``/``Avg. RX`` cuts (similar but not
    identical)::

        radar = Radar(antenna=sencity_this_ii(), ...)

    Digitised from the preliminary datasheet's 77 GHz performance charts (see
    ``radarperf/data/sencity_this_ii.csv``); valid for a PCB mount without
    radome.
    """
    return _load_packaged_pair("sencity_this_ii.csv", "SENCITY THIS-II")


def sencity_farad_iv() -> AntennaPair:
    """Huber+Suhner SENCITY FARAD-IV radar antenna (art. 1377.99.0744).

    76-81 GHz, 8 TX / 8 RX, vertical polarisation; MMIC interface for Infineon
    CTRX8191F and similar.  Boresight directivity ~15 dBi.  A medium azimuth beam
    (~94 deg 10-dB beamwidth) and a narrow elevation beam (~30 deg 10-dB
    beamwidth) with first sidelobes ~20 dB down.

    Returns an :class:`AntennaPair` whose ``tx``/``rx`` elements are the
    datasheet's per-channel ``Avg. TX``/``Avg. RX`` cuts (similar but not
    identical).

    Digitised from the preliminary datasheet's 77 GHz performance charts (see
    ``radarperf/data/sencity_farad_iv.csv``); valid for a PCB mount without
    radome.
    """
    return _load_packaged_pair("sencity_farad_iv.csv", "SENCITY FARAD-IV")
