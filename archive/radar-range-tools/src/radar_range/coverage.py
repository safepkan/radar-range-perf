"""Range sweeps and coverage-grid calculations."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from radar_range.detection import FluctuationModel, pd_from_snr
from radar_range.equation import RadarScenario, SnrResult, calculate_snr
from radar_range.types import ArrayLikeFloat, FloatArray, as_float_array


@dataclass(frozen=True)
class RangeSweepResult:
    """SNR/SINR/Pd result for a one-dimensional or gridded sweep."""

    snr: SnrResult
    pd: FloatArray
    pfa: float
    fluctuation_model: FluctuationModel
    used_sinr_for_pd: bool = True

    @property
    def range_m(self) -> FloatArray:
        """Range grid."""

        return self.snr.range_m

    @property
    def snr_db(self) -> FloatArray:
        """SNR in dB."""

        return self.snr.snr_db

    @property
    def sinr_db(self) -> FloatArray:
        """SINR in dB."""

        return self.snr.sinr_db


def range_sweep(
    scenario: RadarScenario,
    ranges_m: ArrayLikeFloat,
    azimuth_rad: ArrayLikeFloat = 0.0,
    elevation_rad: ArrayLikeFloat = 0.0,
    pfa: float = 1.0e-6,
    fluctuation_model: FluctuationModel = "nonfluctuating",
    use_sinr_for_pd: bool = True,
) -> RangeSweepResult:
    """Calculate SNR/SINR and Pd over a range vector or broadcastable arrays."""

    snr = calculate_snr(scenario, ranges_m, azimuth_rad, elevation_rad)
    statistic_snr = snr.sinr_linear if use_sinr_for_pd else snr.snr_linear
    pd = pd_from_snr(
        statistic_snr,
        pfa=pfa,
        fluctuation_model=fluctuation_model,
        noncoherent_looks=scenario.processing.detector_looks,
        signal_looks=scenario.processing.signal_looks,
    )
    return RangeSweepResult(
        snr=snr,
        pd=pd,
        pfa=pfa,
        fluctuation_model=fluctuation_model,
        used_sinr_for_pd=use_sinr_for_pd,
    )


def range_azimuth_grid(
    scenario: RadarScenario,
    ranges_m: ArrayLikeFloat,
    azimuths_rad: ArrayLikeFloat,
    elevation_rad: float = 0.0,
    pfa: float = 1.0e-6,
    fluctuation_model: FluctuationModel = "nonfluctuating",
    use_sinr_for_pd: bool = True,
) -> RangeSweepResult:
    """Calculate a range/azimuth coverage grid.

    The returned arrays have shape ``(len(ranges_m), len(azimuths_rad))``.
    """

    ranges = as_float_array(ranges_m)
    azimuths = as_float_array(azimuths_rad)
    range_grid, azimuth_grid = np.meshgrid(ranges, azimuths, indexing="ij")
    return range_sweep(
        scenario,
        range_grid,
        azimuth_grid,
        elevation_rad,
        pfa=pfa,
        fluctuation_model=fluctuation_model,
        use_sinr_for_pd=use_sinr_for_pd,
    )


def coverage_boundary_range(
    sweep: RangeSweepResult,
    pd_threshold: float,
    axis: int = 0,
) -> FloatArray:
    """Return the farthest range where Pd exceeds a threshold.

    For a range/angle grid with range on axis 0, the returned array has one
    value per angle. Grid columns with no detection above threshold are returned
    as NaN.
    """

    if pd_threshold < 0.0 or pd_threshold > 1.0:
        raise ValueError("pd_threshold must be in [0, 1]")
    if axis != 0:
        raise NotImplementedError("Only range on axis 0 is currently supported")
    pd = sweep.pd
    ranges = sweep.range_m
    if pd.ndim == 1:
        valid = pd >= pd_threshold
        if not np.any(valid):
            return np.asarray(np.nan, dtype=float)
        return np.asarray(np.max(ranges[valid]), dtype=float)

    boundary = np.full(pd.shape[1:], np.nan, dtype=float)
    for index in np.ndindex(pd.shape[1:]):
        column = pd[(slice(None),) + index]
        valid = column >= pd_threshold
        if np.any(valid):
            boundary[index] = float(np.max(ranges[(slice(None),) + index][valid]))
    return boundary
