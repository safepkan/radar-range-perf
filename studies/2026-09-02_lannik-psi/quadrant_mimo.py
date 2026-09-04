"""Ideal four-quadrant TX MIMO ambiguity experiment for Lannik Psi.

The complete prescribed TX aperture is split geometrically into four
equal-power quadrants. Each quadrant is treated as one perfectly known complex
TX channel, corresponding to coherently combining the two MMIC ports intended
to feed that quadrant. The four quadrant waveforms are assumed perfectly
orthogonal and their matched-filter outputs are retained for all eight RX
channels, giving 32 virtual measurements.

The script first tests whether the exact quadrant patterns distinguish
directions that are exact grating-lobe aliases for the physical RX channel
array. It then estimates ideal MIMO detection range and binary ambiguity-
resolution range for an illustrative interlaced schedule.

This deliberately excludes waveform orthogonality loss, calibration error,
phase noise, processing-capacity and multiple-target effects.

Run from the repository root with::

    venv/bin/python studies/2026-09-02_lannik-psi/quadrant_mimo.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from matplotlib.axes import Axes
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle
from scipy.special import betaincinv

from lannik_psi import (
    CENTER_FREQUENCY_HZ,
    COVERAGE_CUTS,
    DETECTION_LEVELS,
    PFA,
    RADIATOR_GAIN_DBI,
    RX_SQUARE_LAYOUT,
    RX_SOURCE_SUBARRAY_HEIGHT_M,
    RX_SOURCE_SUBARRAY_WIDTH_M,
    RX_SUPPLIED_LAYOUT,
    TARGET,
    CoverageCut,
    RxAntennaLayout,
    lannik_psi,
    load_tx_antenna,
    rx_principal_cut_angles_deg,
)
from radarperf import (
    Geometry,
    MultiBeamUniformArrayAntenna,
    RectangularArrayAntenna,
    required_snr_db,
)
from radarperf.plotting import is_non_interactive_backend
from radarperf.units import SPEED_OF_LIGHT

ComplexArray = npt.NDArray[np.complex128]
FloatArray = npt.NDArray[np.float64]

UV_LIMIT = 0.55
UV_SAMPLES = 441
CORRELATION_FLOOR_DB = -35.0
FIELD_CHUNK_SIZE = 4096
RANGE_REFERENCE_M = 100.0
RANGE_CUT_LIMIT_DEG = 30.0
RANGE_CUT_SAMPLES = 1201
AMBIGUITY_SUCCESS_PROBABILITY = 0.99
MIMO_UPDATE_COUNTS = (1, 2, 4)
MIMO_FRAME_INTERVAL = 4
FRAME_RATE_HZ = 20.0


@dataclass(frozen=True)
class TxQuadrant:
    """One independently coded TX quadrant with unit-power normalization."""

    name: str
    horizontal_m: FloatArray
    vertical_m: FloatArray
    excitations: ComplexArray

    @property
    def excitation_power(self) -> float:
        """Integrated relative excitation power in this quadrant."""
        return float(np.sum(np.abs(self.excitations) ** 2))


@dataclass(frozen=True)
class AliasCase:
    """One RX geometry used in the quadrant-MIMO ambiguity comparison."""

    name: str
    layout: RxAntennaLayout


@dataclass(frozen=True)
class AliasMap:
    """RX-folded alias correlation and supporting plotting grids."""

    u: FloatArray
    v: FloatArray
    correlation_db: FloatArray
    tx_relative_db: FloatArray
    period_u: float
    period_v: float


@dataclass(frozen=True)
class MimoRangeCut:
    """Detection and folded-alias resolution ranges in one angular cut."""

    definition: CoverageCut
    angle_deg: FloatArray
    coherent_detection_ranges_m: tuple[FloatArray, ...]
    mimo_detection_ranges_m: tuple[FloatArray, ...]
    ambiguity_ranges_m: tuple[FloatArray, ...]
    alias_correlation_db: FloatArray
    principal_edge_deg: float


@dataclass(frozen=True)
class RxHeightTrade:
    """Vertical-edge performance as RX subarray height is varied."""

    height_lambda: FloatArray
    principal_edge_deg: FloatArray
    alias_correlation_db: FloatArray
    coherent_pd50_range_m: FloatArray
    mimo_detection_ranges_m: tuple[FloatArray, ...]
    ambiguity_ranges_m: tuple[FloatArray, ...]


ALIAS_CASES = (
    AliasCase("Supplied-height RX subarrays", RX_SUPPLIED_LAYOUT),
    AliasCase("Square RX subarrays", RX_SQUARE_LAYOUT),
)


def split_tx_quadrants(tx_antenna: RectangularArrayAntenna) -> tuple[TxQuadrant, ...]:
    """Split the complete TX excitation grid at the horizontal/vertical axes."""
    horizontal, vertical = np.meshgrid(
        tx_antenna.horizontal_positions_m,
        tx_antenna.vertical_positions_m,
        indexing="ij",
    )
    definitions = (
        ("right/down", horizontal < 0.0, vertical < 0.0),
        ("right/up", horizontal < 0.0, vertical > 0.0),
        ("left/down", horizontal > 0.0, vertical < 0.0),
        ("left/up", horizontal > 0.0, vertical > 0.0),
    )
    quadrants: list[TxQuadrant] = []
    for name, horizontal_mask, vertical_mask in definitions:
        mask = horizontal_mask & vertical_mask
        quadrants.append(
            TxQuadrant(
                name,
                np.asarray(horizontal[mask], dtype=float),
                np.asarray(vertical[mask], dtype=float),
                np.asarray(tx_antenna.excitations[mask], dtype=np.complex128),
            )
        )
    return tuple(quadrants)


def quadrant_fields_uv(
    quadrants: tuple[TxQuadrant, ...],
    u: FloatArray,
    v: FloatArray,
) -> ComplexArray:
    """Evaluate unit-input-power complex fields for every TX quadrant."""
    u_array, v_array = np.broadcast_arrays(u, v)
    u_flat = np.asarray(u_array.ravel(), dtype=float)
    v_flat = np.asarray(v_array.ravel(), dtype=float)
    wavelength_m = SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ
    fields = np.empty((len(quadrants), u_flat.size), dtype=np.complex128)
    for quadrant_index, quadrant in enumerate(quadrants):
        normalization = np.sqrt(quadrant.excitation_power)
        for start in range(0, u_flat.size, FIELD_CHUNK_SIZE):
            stop = min(start + FIELD_CHUNK_SIZE, u_flat.size)
            phase = np.exp(
                -2.0j
                * np.pi
                / wavelength_m
                * (
                    quadrant.horizontal_m[:, None] * u_flat[None, start:stop]
                    + quadrant.vertical_m[:, None] * v_flat[None, start:stop]
                )
            )
            fields[quadrant_index, start:stop] = (
                np.sum(quadrant.excitations[:, None] * phase, axis=0) / normalization
            )
    return np.asarray(fields.reshape((len(quadrants),) + u_array.shape))


def normalized_correlation(first: ComplexArray, second: ComplexArray) -> FloatArray:
    """Squared normalized inner product along the TX-channel axis."""
    inner = np.sum(np.conj(first) * second, axis=0)
    first_power = np.sum(np.abs(first) ** 2, axis=0)
    second_power = np.sum(np.abs(second) ** 2, axis=0)
    denominator = first_power * second_power
    correlation = np.divide(
        np.abs(inner) ** 2,
        denominator,
        out=np.zeros_like(denominator, dtype=float),
        where=denominator > 0.0,
    )
    return np.asarray(np.clip(correlation, 0.0, 1.0), dtype=float)


def fold_to_principal_cell(coordinate: FloatArray, period: float) -> FloatArray:
    """Map one steering coordinate into its centered RX array-factor period."""
    return np.asarray((coordinate + 0.5 * period) % period - 0.5 * period)


def make_alias_map(
    tx_antenna: RectangularArrayAntenna,
    quadrants: tuple[TxQuadrant, ...],
    layout: RxAntennaLayout,
) -> AliasMap:
    """Correlate every direction with the alias folded into the RX cell.

    At these exact RX-period translations, all eight RX phase-center responses
    repeat. Their unit correlation is therefore omitted: the plotted
    four-quadrant TX correlation is also the complete 4-TX by 8-RX virtual-array
    correlation.
    """
    wavelength_m = SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ
    period_u = wavelength_m / layout.channel_horizontal_spacing_m
    period_v = wavelength_m / layout.channel_vertical_spacing_m
    axis = np.linspace(-UV_LIMIT, UV_LIMIT, UV_SAMPLES)
    u, v = np.meshgrid(axis, axis, indexing="ij")
    folded_u = fold_to_principal_cell(u, period_u)
    folded_v = fold_to_principal_cell(v, period_v)

    fields = quadrant_fields_uv(quadrants, u, v)
    folded_fields = quadrant_fields_uv(quadrants, folded_u, folded_v)
    correlation = normalized_correlation(fields, folded_fields)
    inside_principal = (np.abs(u) <= 0.5 * period_u) & (np.abs(v) <= 0.5 * period_v)
    correlation_db = 10.0 * np.log10(np.maximum(correlation, 1.0e-30))
    correlation_db = np.where(inside_principal, np.nan, correlation_db)

    tx_gain = np.asarray(tx_antenna.gain_dbi_uv(u, v), dtype=float)
    tx_relative_db = tx_gain - float(tx_antenna.gain_dbi_uv(0.0, 0.0))
    return AliasMap(
        u=np.asarray(u),
        v=np.asarray(v),
        correlation_db=np.asarray(correlation_db),
        tx_relative_db=np.asarray(tx_relative_db),
        period_u=period_u,
        period_v=period_v,
    )


def correlation_between(
    quadrants: tuple[TxQuadrant, ...],
    first_u: float,
    first_v: float,
    second_u: float,
    second_v: float,
) -> float:
    """Return normalized four-quadrant correlation for two scalar directions."""
    first = quadrant_fields_uv(quadrants, np.asarray(first_u), np.asarray(first_v))
    second = quadrant_fields_uv(quadrants, np.asarray(second_u), np.asarray(second_v))
    return float(normalized_correlation(first, second))


def correlation_db(correlation: float) -> float:
    """Format-safe correlation power in decibels."""
    return float(10.0 * np.log10(max(correlation, 1.0e-30)))


def cut_uv(cut: CoverageCut, angle_deg: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Return u/v coordinates for a signed angle in one study cut."""
    direction_cosine = np.sin(np.radians(angle_deg))
    zeros = np.zeros_like(direction_cosine)
    if cut.name == "horizontal":
        return np.asarray(direction_cosine), np.asarray(zeros)
    if cut.name == "vertical":
        return np.asarray(zeros), np.asarray(direction_cosine)
    diagonal = direction_cosine / np.sqrt(2.0)
    return np.asarray(diagonal), np.asarray(diagonal)


def angles_from_uv(u: FloatArray, v: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Convert visible direction cosines to study azimuth/elevation angles."""
    elevation_rad = np.arcsin(np.clip(v, -1.0, 1.0))
    cosine_elevation = np.cos(elevation_rad)
    azimuth_rad = np.arcsin(np.clip(u / cosine_elevation, -1.0, 1.0))
    return (
        np.asarray(np.degrees(azimuth_rad), dtype=float),
        np.asarray(np.degrees(elevation_rad), dtype=float),
    )


def mimo_tx_gain_dbi(
    quadrants: tuple[TxQuadrant, ...], u: FloatArray, v: FloatArray
) -> FloatArray:
    """Equivalent gain for equal-power orthogonal quadrant transmission.

    Each quadrant field is normalized to unit quadrant input power. Averaging
    their powers gives the effective gain referred to the unchanged total
    eight-port TX power. At boresight this is 6 dB below the coherent sum of
    four equal quadrants.
    """
    fields = quadrant_fields_uv(quadrants, u, v)
    array_gain = np.mean(np.abs(fields) ** 2, axis=0)
    return np.asarray(
        RADIATOR_GAIN_DBI + 10.0 * np.log10(np.maximum(array_gain, 1.0e-30)),
        dtype=float,
    )


def range_at_required_snr(
    snr_at_reference_db: FloatArray, required_db: float | FloatArray
) -> FloatArray:
    """Convert directional reference-range SNR into an R^-4 range boundary."""
    return np.asarray(
        RANGE_REFERENCE_M
        * 10.0 ** ((np.asarray(snr_at_reference_db) - required_db) / 40.0),
        dtype=float,
    )


def required_binary_alias_snr_db(
    correlation: FloatArray,
    *,
    error_probability: float,
    update_count: int,
) -> FloatArray:
    """Mean per-update SNR required for binary Swerling-1 disambiguation.

    The two hypotheses have normalized squared correlation ``correlation``.
    Each MIMO update has an independent Swerling-1 complex amplitude and
    independent complex Gaussian noise. Evidence is accumulated as projection
    energy, allowing an unrelated complex target amplitude in every update.

    For one update, the wrong-hypothesis probability is the negative-eigenvalue
    fraction of the two-subspace quadratic decision statistic. Summing
    ``update_count`` independent updates changes that fraction through a
    Beta(update_count, update_count) distribution, which can be inverted in
    closed form for the required mean SNR.
    """
    if not 0.0 < error_probability < 0.5:
        raise ValueError("error_probability must be between 0 and 0.5")
    if update_count < 1:
        raise ValueError("update_count must be positive")
    rho = np.clip(np.asarray(correlation, dtype=float), 0.0, 1.0)
    single_update_error = float(
        betaincinv(update_count, update_count, error_probability)
    )
    decision_ratio = 1.0 - 2.0 * single_update_error
    coefficient_a = (1.0 - decision_ratio**2) * (1.0 - rho)
    coefficient_b = 4.0 * decision_ratio**2
    with np.errstate(divide="ignore", invalid="ignore"):
        required_linear = (
            coefficient_b
            + np.sqrt(coefficient_b**2 + 4.0 * coefficient_a * coefficient_b)
        ) / (2.0 * coefficient_a)
        required_db = 10.0 * np.log10(required_linear)
    return np.asarray(required_db, dtype=float)


def compute_mimo_range_cut(
    cut: CoverageCut,
    tx_antenna: RectangularArrayAntenna,
    quadrants: tuple[TxQuadrant, ...],
    rx_antenna: MultiBeamUniformArrayAntenna,
    coherent_boresight_snr_db: float,
    detection_snr_db: tuple[float, ...],
) -> MimoRangeCut:
    """Compute coherent/MIMO detection and binary resolution range in one cut."""
    angle_deg = np.linspace(
        -RANGE_CUT_LIMIT_DEG, RANGE_CUT_LIMIT_DEG, RANGE_CUT_SAMPLES
    )
    u, v = cut_uv(cut, angle_deg)
    azimuth_deg, elevation_deg = angles_from_uv(u, v)
    coherent_tx_gain_db = np.asarray(tx_antenna.gain_dbi_uv(u, v), dtype=float)
    mimo_tx_gain_db = mimo_tx_gain_dbi(quadrants, u, v)
    rx_gain_db = np.asarray(
        rx_antenna.gain_dbi(azimuth_deg, elevation_deg), dtype=float
    )
    coherent_boresight_tx_gain_db = float(tx_antenna.gain_dbi_uv(0.0, 0.0))
    boresight_rx_gain_db = float(rx_antenna.gain_dbi(0.0, 0.0))
    rx_relative_db = rx_gain_db - boresight_rx_gain_db
    coherent_snr_db = (
        coherent_boresight_snr_db
        + coherent_tx_gain_db
        - coherent_boresight_tx_gain_db
        + rx_relative_db
    )
    mimo_snr_db = (
        coherent_boresight_snr_db
        + mimo_tx_gain_db
        - coherent_boresight_tx_gain_db
        + rx_relative_db
    )

    coherent_ranges = tuple(
        range_at_required_snr(coherent_snr_db, required_db)
        for required_db in detection_snr_db
    )
    mimo_ranges = tuple(
        range_at_required_snr(mimo_snr_db, required_db)
        for required_db in detection_snr_db
    )

    wavelength_m = SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ
    period_u = wavelength_m / rx_antenna.horizontal_spacing_m
    period_v = wavelength_m / rx_antenna.vertical_spacing_m
    folded_u = fold_to_principal_cell(u, period_u)
    folded_v = fold_to_principal_cell(v, period_v)
    fields = quadrant_fields_uv(quadrants, u, v)
    folded_fields = quadrant_fields_uv(quadrants, folded_u, folded_v)
    correlation = normalized_correlation(fields, folded_fields)
    inside_principal = (np.abs(u) <= 0.5 * period_u) & (np.abs(v) <= 0.5 * period_v)
    alias_correlation_db = 10.0 * np.log10(np.maximum(correlation, 1.0e-30))
    alias_correlation_db = np.where(inside_principal, np.nan, alias_correlation_db)
    ambiguity_ranges: list[FloatArray] = []
    for update_count in MIMO_UPDATE_COUNTS:
        required_resolution_db = required_binary_alias_snr_db(
            correlation,
            error_probability=1.0 - AMBIGUITY_SUCCESS_PROBABILITY,
            update_count=update_count,
        )
        resolution_range = range_at_required_snr(mimo_snr_db, required_resolution_db)
        ambiguity_ranges.append(
            np.asarray(np.where(inside_principal, np.nan, resolution_range))
        )

    principal_az_deg, principal_el_deg = rx_principal_cut_angles_deg(rx_antenna)
    if cut.name == "horizontal":
        principal_edge_deg = principal_az_deg
    elif cut.name == "vertical":
        principal_edge_deg = principal_el_deg
    else:
        principal_edge_deg = float(
            np.degrees(np.arcsin(np.sqrt(2.0) * min(0.5 * period_u, 0.5 * period_v)))
        )
    return MimoRangeCut(
        definition=cut,
        angle_deg=np.asarray(angle_deg),
        coherent_detection_ranges_m=coherent_ranges,
        mimo_detection_ranges_m=mimo_ranges,
        ambiguity_ranges_m=tuple(ambiguity_ranges),
        alias_correlation_db=np.asarray(alias_correlation_db),
        principal_edge_deg=principal_edge_deg,
    )


def compute_rx_height_trade(
    tx_antenna: RectangularArrayAntenna,
    quadrants: tuple[TxQuadrant, ...],
    square_boresight_snr_db: float,
    detection_snr_db: tuple[float, ...],
) -> RxHeightTrade:
    """Sweep dense RX subarray height and evaluate its vertical cell edge."""
    wavelength_m = SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ
    square_height_lambda = RX_SOURCE_SUBARRAY_WIDTH_M / wavelength_m
    source_height_lambda = RX_SOURCE_SUBARRAY_HEIGHT_M / wavelength_m
    height_lambda = np.linspace(square_height_lambda, source_height_lambda, 81)
    edge_v = 0.5 / height_lambda
    principal_edge_deg = np.degrees(np.arcsin(edge_v))

    zeros = np.zeros_like(edge_v)
    coherent_tx_gain_db = np.asarray(tx_antenna.gain_dbi_uv(zeros, edge_v), dtype=float)
    mimo_tx_gain_db = mimo_tx_gain_dbi(quadrants, zeros, edge_v)
    coherent_boresight_tx_gain_db = float(tx_antenna.gain_dbi_uv(0.0, 0.0))
    rx_boresight_delta_db = 10.0 * np.log10(height_lambda / square_height_lambda)
    # At a densely packed subarray's principal edge, h*v/lambda = 0.5.
    # The best periodic channel-array beam has unity array factor there.
    rx_edge_relative_db = 20.0 * np.log10(np.abs(np.sinc(height_lambda * edge_v)))
    coherent_snr_db = (
        square_boresight_snr_db
        + rx_boresight_delta_db
        + coherent_tx_gain_db
        - coherent_boresight_tx_gain_db
        + rx_edge_relative_db
    )
    mimo_snr_db = (
        square_boresight_snr_db
        + rx_boresight_delta_db
        + mimo_tx_gain_db
        - coherent_boresight_tx_gain_db
        + rx_edge_relative_db
    )
    coherent_pd50_range_m = range_at_required_snr(coherent_snr_db, detection_snr_db[0])
    mimo_detection_ranges_m = tuple(
        range_at_required_snr(mimo_snr_db, required_db)
        for required_db in detection_snr_db
    )

    positive_edge_fields = quadrant_fields_uv(quadrants, zeros, edge_v)
    negative_edge_fields = quadrant_fields_uv(quadrants, zeros, -edge_v)
    correlation = normalized_correlation(positive_edge_fields, negative_edge_fields)
    alias_correlation_db = 10.0 * np.log10(np.maximum(correlation, 1.0e-30))
    ambiguity_ranges_m = tuple(
        range_at_required_snr(
            mimo_snr_db,
            required_binary_alias_snr_db(
                correlation,
                error_probability=1.0 - AMBIGUITY_SUCCESS_PROBABILITY,
                update_count=update_count,
            ),
        )
        for update_count in MIMO_UPDATE_COUNTS
    )
    return RxHeightTrade(
        height_lambda=np.asarray(height_lambda),
        principal_edge_deg=np.asarray(principal_edge_deg),
        alias_correlation_db=np.asarray(alias_correlation_db),
        coherent_pd50_range_m=coherent_pd50_range_m,
        mimo_detection_ranges_m=mimo_detection_ranges_m,
        ambiguity_ranges_m=ambiguity_ranges_m,
    )


def print_diagnostics(
    quadrants: tuple[TxQuadrant, ...], cases: tuple[AliasCase, ...]
) -> None:
    """Print quadrant equality and representative exact-alias correlations."""
    total_power = sum(quadrant.excitation_power for quadrant in quadrants)
    print("Four-quadrant TX aperture")
    for quadrant in quadrants:
        boresight = quadrant_fields_uv((quadrant,), np.asarray(0.0), np.asarray(0.0))[0]
        print(
            f"  {quadrant.name:10s}: {quadrant.horizontal_m.size:2d} radiators, "
            f"{100.0 * quadrant.excitation_power / total_power:5.2f}% power, "
            f"boresight phase {np.degrees(np.angle(boresight)):6.2f} deg"
        )

    wavelength_m = SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ
    print("\nFour-quadrant MIMO correlation between representative RX aliases")
    print("  (0 dB is unresolved; more negative is better)")
    for case in cases:
        period_u = wavelength_m / case.layout.channel_horizontal_spacing_m
        period_v = wavelength_m / case.layout.channel_vertical_spacing_m
        pairs = (
            (
                "opposite u edges",
                (-0.5 * period_u, 0.0),
                (0.5 * period_u, 0.0),
            ),
            (
                "opposite v edges",
                (0.0, -0.5 * period_v),
                (0.0, 0.5 * period_v),
            ),
            (
                "opposite corners",
                (-0.5 * period_u, -0.5 * period_v),
                (0.5 * period_u, 0.5 * period_v),
            ),
            ("boresight/u replica", (0.0, 0.0), (period_u, 0.0)),
            ("boresight/v replica", (0.0, 0.0), (0.0, period_v)),
        )
        print(f"\n  {case.name}")
        print(
            f"    RX periods: {period_u:.4f} u x {period_v:.4f} v; "
            f"principal half-widths {0.5 * period_u:.4f} x "
            f"{0.5 * period_v:.4f}"
        )
        for label, first, second in pairs:
            value = correlation_between(quadrants, *first, *second)
            print(f"    {label:23s}: {correlation_db(value):7.2f} dB")


def plot_alias_map_axis(
    ax: Axes,
    alias_map: AliasMap,
    case: AliasCase,
    color_norm: Normalize,
) -> None:
    """Draw one RX geometry's four-quadrant MIMO alias-correlation map."""
    axis = alias_map.u[:, 0]
    ax.pcolormesh(
        axis,
        axis,
        alias_map.correlation_db.T,
        shading="auto",
        cmap="magma",
        norm=color_norm,
    )
    contours = ax.contour(
        axis,
        axis,
        alias_map.tx_relative_db.T,
        levels=(-20.0, -10.0, -3.0),
        colors="white",
        linewidths=(0.7, 0.9, 1.2),
    )
    ax.clabel(contours, fmt=lambda level: f"TX {level:.0f} dB", fontsize=7)
    half_u = 0.5 * alias_map.period_u
    half_v = 0.5 * alias_map.period_v
    ax.add_patch(
        Rectangle(
            (-half_u, -half_v),
            2.0 * half_u,
            2.0 * half_v,
            facecolor="none",
            edgecolor="C3",
            linestyle="--",
            linewidth=1.2,
            label="RX principal-region edges",
            zorder=4,
        )
    )
    wavelength_m = SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ
    width_lambda = case.layout.subarray_width_m / wavelength_m
    height_lambda = case.layout.subarray_height_m / wavelength_m
    ax.set_title(
        f"{case.name}\n"
        f"{width_lambda:.2f}λ × {height_lambda:.2f}λ subarrays; "
        f"{case.layout.horizontal_count} × {case.layout.vertical_count} channels"
    )
    ax.set_xlabel("u [-]")
    ax.set_ylabel("v [-]")
    ax.set_aspect("equal")
    ax.set_facecolor("0.82")
    ax.grid(True, alpha=0.15)
    ax.legend(loc="lower left", fontsize=8)


def plot_alias_maps(
    tx_antenna: RectangularArrayAntenna,
    quadrants: tuple[TxQuadrant, ...],
    cases: tuple[AliasCase, ...],
    path: Path,
) -> None:
    """Save four-quadrant MIMO alias discrimination for both RX variants."""
    maps = tuple(make_alias_map(tx_antenna, quadrants, case.layout) for case in cases)
    color_norm = Normalize(vmin=CORRELATION_FLOOR_DB, vmax=0.0)
    fig, axes = plt.subplots(1, len(cases), figsize=(12.5, 6.0))
    axes_array = np.atleast_1d(axes)
    for ax, alias_map, case in zip(axes_array, maps, cases, strict=True):
        plot_alias_map_axis(ax, alias_map, case, color_norm)

    scalar_mappable = plt.cm.ScalarMappable(norm=color_norm, cmap="magma")
    colorbar_ax = fig.add_axes((0.31, 0.105, 0.38, 0.035))
    fig.colorbar(
        scalar_mappable,
        cax=colorbar_ax,
        orientation="horizontal",
        label="squared correlation with RX-folded angular alias [dB]",
    )
    fig.suptitle(
        "Ideal four-quadrant MIMO discrimination of RX grating aliases\n"
        "0 dB means indistinguishable up to unknown target amplitude",
        fontsize=13,
    )
    fig.text(
        0.5,
        0.025,
        "Exact prescribed complex TX quadrant patterns; 4 orthogonal TX × 8 RX; "
        "white contours show coherent TX sum gain | blank rectangle is the RX "
        "principal region | coherent-TX correlation would remain 0 dB",
        ha="center",
        fontsize=8,
        color="0.3",
    )
    fig.subplots_adjust(left=0.07, right=0.98, bottom=0.22, top=0.82, wspace=0.22)
    fig.savefig(path, dpi=150)
    print(f"\n  saved {path}")


def mark_principal_interval(ax: Axes, half_angle_deg: float) -> None:
    """Shade the unambiguous RX interval and mark its two edges."""
    ax.axvspan(
        -half_angle_deg,
        half_angle_deg,
        color="0.92",
        zorder=-5,
        label="RX principal region",
    )
    ax.axvline(-half_angle_deg, color="C3", linestyle="--", linewidth=1.0)
    ax.axvline(half_angle_deg, color="C3", linestyle="--", linewidth=1.0)


def plot_mimo_detection_range_cuts(cuts: tuple[MimoRangeCut, ...], path: Path) -> None:
    """Compare coherent-TX and ideal four-quadrant MIMO detection ranges."""
    fig, axes = plt.subplots(1, len(cuts), figsize=(12.5, 4.8), sharey=True)
    axes_array = np.atleast_1d(axes)
    line_styles = ("-", "--")
    for ax, cut in zip(axes_array, cuts, strict=True):
        mark_principal_interval(ax, cut.principal_edge_deg)
        for level, line_style, coherent_range, mimo_range in zip(
            DETECTION_LEVELS,
            line_styles,
            cut.coherent_detection_ranges_m,
            cut.mimo_detection_ranges_m,
            strict=True,
        ):
            ax.plot(
                cut.angle_deg,
                coherent_range,
                color="C0",
                linestyle=line_style,
                label=f"coherent TX, Pd={level:.0%}",
            )
            ax.plot(
                cut.angle_deg,
                mimo_range,
                color="C1",
                linestyle=line_style,
                label=f"4-quadrant MIMO, Pd={level:.0%}",
            )
        ax.set_title(cut.definition.title)
        ax.set_xlabel("signed off-boresight angle [deg]")
        ax.set_xlim(-RANGE_CUT_LIMIT_DEG, RANGE_CUT_LIMIT_DEG)
        ax.set_ylim(0.0, 1200.0)
        ax.grid(True, alpha=0.25)
    axes_array[0].set_ylabel("single-CPI detection range [m]")
    handles, labels = axes_array[0].get_legend_handles_labels()
    figure_legend = fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=3,
        fontsize=8,
        bbox_to_anchor=(0.5, 0.075),
    )
    figure_legend.get_frame().set_alpha(0.9)
    fig.suptitle(
        "Lannik Psi coherent-TX and ideal four-quadrant MIMO detection range\n"
        "Supplied-height rectangular RX baseline"
    )
    fig.text(
        0.5,
        0.018,
        "1 m² Swerling-1 target | Pfa=1e-6 | same full-length CPI and total "
        "eight-port TX power | ideal coherent RX/TX-channel processing | "
        "no MIMO implementation loss",
        ha="center",
        fontsize=8,
        color="0.3",
    )
    fig.tight_layout(rect=(0.0, 0.15, 1.0, 0.94))
    fig.savefig(path, dpi=150)
    print(f"  saved {path}")


def plot_mimo_resolution_range_cuts(cuts: tuple[MimoRangeCut, ...], path: Path) -> None:
    """Show binary folded-alias resolution range after repeated MIMO updates."""
    fig, axes = plt.subplots(
        2,
        len(cuts),
        figsize=(12.5, 7.2),
        sharex="col",
        sharey="row",
        height_ratios=(2.0, 1.0),
    )
    update_colors = ("C3", "C4", "C2")
    update_period_s = MIMO_FRAME_INTERVAL / FRAME_RATE_HZ
    for column, cut in enumerate(cuts):
        range_ax = axes[0, column]
        correlation_ax = axes[1, column]
        mark_principal_interval(range_ax, cut.principal_edge_deg)
        mark_principal_interval(correlation_ax, cut.principal_edge_deg)
        range_ax.plot(
            cut.angle_deg,
            cut.mimo_detection_ranges_m[0],
            color="0.35",
            linestyle=":",
            label="MIMO Pd=50%",
        )
        range_ax.plot(
            cut.angle_deg,
            cut.mimo_detection_ranges_m[1],
            color="0.15",
            linestyle="--",
            label="MIMO Pd=90%",
        )
        for update_count, color, resolution_range in zip(
            MIMO_UPDATE_COUNTS,
            update_colors,
            cut.ambiguity_ranges_m,
            strict=True,
        ):
            range_ax.plot(
                cut.angle_deg,
                resolution_range,
                color=color,
                label=(
                    f"{AMBIGUITY_SUCCESS_PROBABILITY:.0%} resolution, "
                    f"{update_count} update"
                    f"{'s' if update_count != 1 else ''} "
                    f"(≤{update_count * update_period_s:.1f} s)"
                ),
            )
        range_ax.set_title(cut.definition.title)
        range_ax.set_ylim(0.0, 1000.0)
        range_ax.grid(True, alpha=0.25)
        correlation_ax.plot(
            cut.angle_deg,
            cut.alias_correlation_db,
            color="C5",
        )
        correlation_ax.axhline(-3.0, color="0.5", linestyle=":", linewidth=0.8)
        correlation_ax.set_ylim(CORRELATION_FLOOR_DB, 0.5)
        correlation_ax.set_xlim(-RANGE_CUT_LIMIT_DEG, RANGE_CUT_LIMIT_DEG)
        correlation_ax.set_xlabel("signed off-boresight angle [deg]")
        correlation_ax.grid(True, alpha=0.25)
    axes[0, 0].set_ylabel("range [m]")
    axes[1, 0].set_ylabel("squared correlation with\nfolded RX alias [dB]")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure_legend = fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=3,
        fontsize=8,
        bbox_to_anchor=(0.5, 0.065),
    )
    figure_legend.get_frame().set_alpha(0.9)
    fig.suptitle(
        "Ideal four-quadrant MIMO detection and binary ambiguity-resolution range\n"
        "Supplied-height rectangular RX baseline"
    )
    fig.text(
        0.5,
        0.014,
        "MIMO every fourth 20 Hz frame (5 Hz) | 1 m² Swerling-1 target; "
        "independent fluctuation and noise per MIMO update | resolution is "
        "true direction vs its folded principal-cell alias | perfect pattern "
        "knowledge/calibration",
        ha="center",
        fontsize=8,
        color="0.3",
    )
    fig.tight_layout(rect=(0.0, 0.145, 1.0, 0.95))
    fig.savefig(path, dpi=150)
    print(f"  saved {path}")


def plot_rx_height_trade(trade: RxHeightTrade, path: Path) -> None:
    """Show the vertical ambiguity trade from square to supplied RX height."""
    fig, (range_ax, correlation_ax) = plt.subplots(
        2,
        1,
        figsize=(8.5, 7.0),
        sharex=True,
        height_ratios=(2.0, 1.0),
    )
    range_ax.plot(
        trade.height_lambda,
        trade.coherent_pd50_range_m,
        color="C0",
        label="coherent TX, Pd=50%",
    )
    range_ax.plot(
        trade.height_lambda,
        trade.mimo_detection_ranges_m[0],
        color="0.35",
        linestyle=":",
        label="MIMO Pd=50%",
    )
    range_ax.plot(
        trade.height_lambda,
        trade.mimo_detection_ranges_m[1],
        color="0.15",
        linestyle="--",
        label="MIMO Pd=90%",
    )
    update_colors = ("C3", "C4", "C2")
    for update_count, color, resolution_range in zip(
        MIMO_UPDATE_COUNTS,
        update_colors,
        trade.ambiguity_ranges_m,
        strict=True,
    ):
        range_ax.plot(
            trade.height_lambda,
            resolution_range,
            color=color,
            label=(
                f"{AMBIGUITY_SUCCESS_PROBABILITY:.0%} resolution, "
                f"{update_count} update{'s' if update_count != 1 else ''}"
            ),
        )
    square_height_lambda = float(trade.height_lambda[0])
    source_height_lambda = float(trade.height_lambda[-1])
    for ax in (range_ax, correlation_ax):
        ax.axvline(
            square_height_lambda,
            color="C3",
            linestyle="--",
            linewidth=1.0,
        )
        ax.axvline(
            source_height_lambda,
            color="C3",
            linestyle="--",
            linewidth=1.0,
        )
        ax.grid(True, alpha=0.25)
    range_ax.text(
        square_height_lambda + 0.03,
        25.0,
        "current square",
        rotation=90,
        va="bottom",
        color="C3",
        fontsize=8,
    )
    range_ax.text(
        source_height_lambda - 0.03,
        25.0,
        "supplied height",
        rotation=90,
        va="bottom",
        ha="right",
        color="C3",
        fontsize=8,
    )
    range_ax.set_ylabel("vertical-edge range [m]")
    range_ax.set_ylim(0.0, 950.0)
    range_ax.legend(ncol=2, fontsize=8, loc="upper left")
    correlation_ax.plot(
        trade.height_lambda,
        trade.alias_correlation_db,
        color="C5",
    )
    correlation_ax.set_xlabel("RX subarray height [wavelengths]")
    correlation_ax.set_ylabel("opposite-edge squared\ncorrelation [dB]")
    correlation_ax.set_ylim(CORRELATION_FLOOR_DB, 0.5)
    edge_ax = correlation_ax.twinx()
    edge_ax.plot(
        trade.height_lambda,
        trade.principal_edge_deg,
        color="C6",
        linestyle=":",
    )
    edge_ax.set_ylabel("vertical principal-region edge [deg]", color="C6")
    edge_ax.tick_params(axis="y", colors="C6")
    fig.suptitle(
        "RX subarray-height trade at the vertical principal-region edge\n"
        "2.42λ width, dense 4 × 2 layout"
    )
    fig.text(
        0.5,
        0.014,
        "Same ideal four-quadrant MIMO and 5 Hz interlace assumptions | "
        "99% binary decision between opposite vertical cell edges | "
        "1 m² Swerling-1 target",
        ha="center",
        fontsize=8,
        color="0.3",
    )
    fig.tight_layout(rect=(0.0, 0.055, 1.0, 0.94))
    fig.savefig(path, dpi=150)
    print(f"  saved {path}")


def print_range_diagnostics(
    tx_antenna: RectangularArrayAntenna,
    quadrants: tuple[TxQuadrant, ...],
    cuts: tuple[MimoRangeCut, ...],
    height_trade: RxHeightTrade,
) -> None:
    """Print boresight sensitivity and representative resolution ranges."""
    coherent_gain_db = float(tx_antenna.gain_dbi_uv(0.0, 0.0))
    mimo_gain_db = float(mimo_tx_gain_dbi(quadrants, np.asarray(0.0), np.asarray(0.0)))
    print("\nInterlaced four-quadrant MIMO range model (supplied-height RX)")
    print(
        f"  boresight MIMO sensitivity : {mimo_gain_db - coherent_gain_db:6.2f} "
        "dB vs coherent TX"
    )
    boresight_index = int(np.argmin(np.abs(cuts[0].angle_deg)))
    for level, coherent_range, mimo_range in zip(
        DETECTION_LEVELS,
        cuts[0].coherent_detection_ranges_m,
        cuts[0].mimo_detection_ranges_m,
        strict=True,
    ):
        coherent_value = coherent_range[boresight_index]
        mimo_value = mimo_range[boresight_index]
        print(
            f"  Pd={level:.0%} boresight range    : {coherent_value:6.0f} m "
            f"coherent / {mimo_value:6.0f} m MIMO"
        )
    for cut in cuts[:2]:
        outside = np.flatnonzero(cut.angle_deg > cut.principal_edge_deg)
        edge_index = int(outside[0])
        ranges_text = ", ".join(
            f"{count} update{'s' if count != 1 else ''}: {ranges[edge_index]:.0f} m"
            for count, ranges in zip(
                MIMO_UPDATE_COUNTS, cut.ambiguity_ranges_m, strict=True
            )
        )
        print(
            f"  {cut.definition.name:10s} +edge, "
            f"{AMBIGUITY_SUCCESS_PROBABILITY:.0%} binary resolution: "
            f"{ranges_text}"
        )
    square_index = 0
    square_ranges_text = ", ".join(
        f"{count} update{'s' if count != 1 else ''}: " f"{ranges[square_index]:.0f} m"
        for count, ranges in zip(
            MIMO_UPDATE_COUNTS, height_trade.ambiguity_ranges_m, strict=True
        )
    )
    print(
        f"  square comparison vertical edge "
        f"({height_trade.principal_edge_deg[square_index]:.1f} deg, "
        f"{height_trade.alias_correlation_db[square_index]:.1f} dB): "
        f"{square_ranges_text}"
    )


def main() -> None:
    """Run the idealized four-quadrant MIMO ambiguity experiment."""
    product = lannik_psi()
    tx_antenna = load_tx_antenna()
    quadrants = split_tx_quadrants(tx_antenna)
    print_diagnostics(quadrants, ALIAS_CASES)
    rx_antenna = product.radar.antenna.rx
    if not isinstance(rx_antenna, MultiBeamUniformArrayAntenna):
        raise TypeError("Lannik Psi RX must be a MultiBeamUniformArrayAntenna")
    coherent_boresight_snr_db = product.radar.link_budget(
        TARGET, Geometry(range_m=RANGE_REFERENCE_M)
    ).snr_db
    processing_budget = product.radar.processing.budget(
        product.waveform,
        product.radar.frontend.n_tx,
        product.radar.frontend.n_rx,
    )
    detection_snr_db = tuple(
        required_snr_db(
            level,
            PFA,
            swerling=TARGET.swerling,
            n_pulses=processing_budget.n_noncoherent,
        )
        for level in DETECTION_LEVELS
    )
    range_cuts = tuple(
        compute_mimo_range_cut(
            cut,
            tx_antenna,
            quadrants,
            rx_antenna,
            coherent_boresight_snr_db,
            detection_snr_db,
        )
        for cut in COVERAGE_CUTS
    )
    square_product = lannik_psi(RX_SQUARE_LAYOUT)
    square_boresight_snr_db = square_product.radar.link_budget(
        TARGET, Geometry(range_m=RANGE_REFERENCE_M)
    ).snr_db
    height_trade = compute_rx_height_trade(
        tx_antenna,
        quadrants,
        square_boresight_snr_db,
        detection_snr_db,
    )
    print_range_diagnostics(tx_antenna, quadrants, range_cuts, height_trade)
    generated_dir = Path(__file__).parent / "generated" / "mimo"
    generated_dir.mkdir(parents=True, exist_ok=True)
    plot_alias_maps(
        tx_antenna,
        quadrants,
        ALIAS_CASES,
        generated_dir / "quadrant_mimo_alias_correlation.png",
    )
    plot_mimo_detection_range_cuts(
        range_cuts,
        generated_dir / "mimo_detection_range_cuts.png",
    )
    plot_mimo_resolution_range_cuts(
        range_cuts,
        generated_dir / "mimo_ambiguity_resolution_range_cuts.png",
    )
    plot_rx_height_trade(
        height_trade,
        generated_dir / "mimo_rx_height_trade.png",
    )
    if not is_non_interactive_backend():
        plt.show()


if __name__ == "__main__":
    main()
