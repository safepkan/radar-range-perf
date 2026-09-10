"""Stagger amount, TX-taper dependence and multi-frame resolution for Lannik Psi.

Extends the 2026-09-09 on-demand resolution experiment for the 2026-09-10
rectangular-prototype decision. Three questions are addressed:

1. Where does the ideal four-quadrant MIMO alias discrimination come from? The
   TX quadrant phase centers share the RX subarray lattice (both are eight
   radiator pitches), so it cannot be geometric. The supplied excitation phase
   and amplitude are removed in turn, the realized defocus is scaled, and a
   systematic top/bottom quadrant phase error is applied.
2. How much coherent-mode vertical-alias information does a stagger of a given
   size provide, and which competing lobes remain? The alternating column
   offset is swept from zero to half a subarray height and competitors are
   enumerated with their required RCS.
3. For URA, height/8 and height/4 stagger: how many ordinary coherent frames
   and how much on-demand MIMO illumination resolve the tested events?

The idealizations of ``rx_resolution_experiment.py`` apply: fixed 1 m² target
known to exist in a gate, unknown complex amplitude per update, independent
noise between frames, nominal processing dictionary, and no motion,
fluctuation, waveform loss or latency model. The height/4 layout is a study
construct for comparison; the 2026-09-08 sketch used one pitch. See RX_LAYOUT.md.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from matplotlib.patches import Rectangle
from scipy.ndimage import maximum_filter

from lannik_psi import (
    CENTER_FREQUENCY_HZ,
    RADIATOR_GAIN_DBI,
    RX_EXPERIMENTAL_STAGGERED_LAYOUT,
    RX_SOURCE_SUBARRAY_HEIGHT_M,
    RX_SOURCE_SUBARRAY_WIDTH_M,
    RX_SUPPLIED_LAYOUT,
    RxAntennaLayout,
    load_tx_antenna,
)
from quadrant_mimo import (
    ComplexArray,
    FloatArray,
    TxQuadrant,
    mimo_tx_gain_dbi,
    normalized_correlation,
    quadrant_fields_uv,
    split_tx_quadrants,
)
from radarperf import RectangularArrayAntenna
from radarperf.units import SPEED_OF_LIGHT
from rx_layout_experiment import channel_steering_vectors
from rx_resolution_experiment import (
    CASES,
    COHERENT_SNR_DB,
    SEED,
    HypothesisBank,
    build_bank,
    choose_cells,
    complex_noise,
    error_upper_bound,
    normalize_columns,
    subarray_relative_gain_db,
)

WAVELENGTH_M = SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ
PERIOD_U = WAVELENGTH_M / RX_SOURCE_SUBARRAY_WIDTH_M
PERIOD_V = WAVELENGTH_M / RX_SOURCE_SUBARRAY_HEIGHT_M
VERTICAL_EDGE = (0.0, 0.5 * PERIOD_V)
VERTICAL_ALIAS = (0.0, -0.5 * PERIOD_V)
HORIZONTAL_EDGE = (0.5 * PERIOD_U, 0.0)
HORIZONTAL_ALIAS = (-0.5 * PERIOD_U, 0.0)
STAGGER_FRACTIONS = (0.0, 0.125, 0.25, 0.375, 0.5)
DEFOCUS_SCALES = (0.0, 0.6, 0.8, 1.0, 1.2, 1.4)
QUADRANT_PHASE_ERRORS_DEG = (0.0, 10.0, 20.0, 30.0, 45.0)
COHERENT_UPDATE_COUNTS = (1, 2, 4)
# (name, independent per-channel/quadrant phase RMS, systematic phase on the
# alternate RX column group). +15° is the unfavourable sign for the H/4 layout.
RX_ERROR_SCENARIOS = (
    ("nominal", 0.0, 0.0),
    ("10° random", 10.0, 0.0),
    ("+15° column group", 0.0, 15.0),
)
ALTERNATE_COLUMN_MASK = (np.arange(8) // 2) % 2 == 1
BANK_U_SEED_FRACTION = 0.5
ENERGIES = np.array([0.0, 0.125, 0.25, 0.375, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0])
COMPETITOR_RCS_CEILING_DBSM = 12.0
COMPETITOR_RHO_FLOOR = 0.09
COMPETITOR_GRID_SAMPLES = 801
COMPETITOR_TRUE_DIRECTIONS = (
    ("vertical edge", 0.0, 0.5 * PERIOD_V),
    ("half edge", 0.0, 0.06),
    ("beam corner", -0.08, -0.08),
    ("horizontal edge", 0.5 * PERIOD_U, 0.0),
)
RADIATOR_PITCH_M = RX_SOURCE_SUBARRAY_HEIGHT_M / 8.0
IN_BEAM_LIMIT = 0.16
IN_BEAM_SAMPLES = 33
IN_BEAM_GRID_SAMPLES = 401
IN_BEAM_RCS_CEILING_DBSM = 10.0
TX_HALF_POWER_V = float(np.sin(np.radians(6.25)))


@dataclass(frozen=True)
class LayoutOption:
    """One rectangular RX phase-center layout compared in the experiment."""

    name: str
    layout: RxAntennaLayout


def staggered_layout(
    fraction: float, *, subarray_height_m: float = RX_SOURCE_SUBARRAY_HEIGHT_M
) -> RxAntennaLayout:
    """Alternate column offsets differing by ``fraction`` of the subarray height."""
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("stagger fraction must lie in [0, 1]")
    if fraction == 0.0 and subarray_height_m == RX_SOURCE_SUBARRAY_HEIGHT_M:
        return RX_SUPPLIED_LAYOUT
    offset = 0.5 * fraction * subarray_height_m
    return RxAntennaLayout(
        subarray_width_m=RX_SOURCE_SUBARRAY_WIDTH_M,
        subarray_height_m=subarray_height_m,
        horizontal_count=4,
        vertical_count=2,
        vertical_offsets_by_horizontal_m=(offset, -offset, offset, -offset),
    )


LAYOUT_OPTIONS = (
    LayoutOption("URA", RX_SUPPLIED_LAYOUT),
    LayoutOption("stagger H/8", RX_EXPERIMENTAL_STAGGERED_LAYOUT),
    LayoutOption("stagger H/4", staggered_layout(0.25)),
)


# --- TX taper decomposition ---------------------------------------------------


def antenna_from_excitations(
    tx: RectangularArrayAntenna, excitations: ComplexArray
) -> RectangularArrayAntenna:
    """Rebuild the TX antenna on its own grid with replaced excitations."""
    horizontal, vertical = np.meshgrid(
        tx.horizontal_positions_m, tx.vertical_positions_m, indexing="ij"
    )
    if excitations.shape != horizontal.shape:
        raise ValueError("excitations must match the TX grid shape")
    return RectangularArrayAntenna.from_element_list(
        np.asarray(horizontal.ravel(), dtype=float),
        np.asarray(vertical.ravel(), dtype=float),
        np.asarray(excitations.ravel(), dtype=np.complex128),
        center_frequency_hz=CENTER_FREQUENCY_HZ,
        element_gain_dbi=RADIATOR_GAIN_DBI,
        fft_size=tx.fft_size,
    )


def unwrapped_excitation_phase(excitations: ComplexArray) -> FloatArray:
    """Continuous supplied phase in radians, referenced to the aperture centre.

    ``np.angle`` wraps the smooth quadratic defocus at ±180°; scaling wrapped
    values creates discontinuities instead of a weaker or stronger defocus
    (review finding, 2026-09-10). Adjacent radiators differ by well under
    180°, so sequential unwrapping along both axes recovers the surface.
    """
    phase = np.unwrap(np.unwrap(np.angle(excitations), axis=0), axis=1)
    rows, columns = phase.shape
    centre = phase[rows // 2 - 1 : rows // 2 + 1, columns // 2 - 1 : columns // 2 + 1]
    return np.asarray(phase - np.mean(centre), dtype=float)


def scaled_defocus_antenna(
    tx: RectangularArrayAntenna, scale: float
) -> RectangularArrayAntenna:
    """Keep the supplied amplitude taper and scale the unwrapped supplied phase."""
    excitations = np.asarray(tx.excitations, dtype=np.complex128)
    return antenna_from_excitations(
        tx,
        np.abs(excitations)
        * np.exp(1j * scale * unwrapped_excitation_phase(excitations)),
    )


def uniform_quadrants(quadrants: tuple[TxQuadrant, ...]) -> tuple[TxQuadrant, ...]:
    """Same quadrant geometry with untapered, cophasal excitation."""
    return tuple(
        TxQuadrant(
            quadrant.name,
            quadrant.horizontal_m,
            quadrant.vertical_m,
            np.ones_like(quadrant.excitations),
        )
        for quadrant in quadrants
    )


def phase_offset_quadrants(
    quadrants: tuple[TxQuadrant, ...], upper_offset_deg: float
) -> tuple[TxQuadrant, ...]:
    """Apply one systematic phase offset to both upper quadrants."""
    return tuple(
        TxQuadrant(
            quadrant.name,
            quadrant.horizontal_m,
            quadrant.vertical_m,
            quadrant.excitations
            * np.exp(
                1j
                * np.radians(upper_offset_deg if quadrant.name.endswith("/up") else 0)
            ),
        )
        for quadrant in quadrants
    )


def quadrant_signature(
    quadrants: tuple[TxQuadrant, ...], direction: tuple[float, float]
) -> ComplexArray:
    return np.asarray(
        quadrant_fields_uv(
            quadrants, np.asarray(direction[0]), np.asarray(direction[1])
        ),
        dtype=np.complex128,
    )


def pair_correlation_db(
    quadrants: tuple[TxQuadrant, ...],
    first: tuple[float, float],
    second: tuple[float, float],
) -> float:
    """Squared normalized TX-quadrant signature correlation in decibels."""
    correlation = normalized_correlation(
        quadrant_signature(quadrants, first), quadrant_signature(quadrants, second)
    )
    return float(10.0 * np.log10(max(float(correlation), 1e-30)))


def mismatch_margin_db(
    true_quadrants: tuple[TxQuadrant, ...],
    nominal_quadrants: tuple[TxQuadrant, ...],
    true_direction: tuple[float, float],
    alias_direction: tuple[float, float],
) -> float:
    """dB by which the nominal true signature beats the nominal alias signature.

    The received signal uses the perturbed quadrants; both hypotheses use the
    nominal dictionary. Zero means the two hypotheses fit equally well.
    """
    received = quadrant_signature(true_quadrants, true_direction)
    fit_true = float(
        normalized_correlation(
            received, quadrant_signature(nominal_quadrants, true_direction)
        )
    )
    fit_alias = float(
        normalized_correlation(
            received, quadrant_signature(nominal_quadrants, alias_direction)
        )
    )
    return float(10.0 * np.log10(max(fit_true, 1e-30) / max(fit_alias, 1e-30)))


def principal_beamwidth_deg(antenna: RectangularArrayAntenna) -> float:
    """Horizontal 3 dB beamwidth from a fine principal-plane cut."""
    angles = np.linspace(-20.0, 20.0, 4001)
    u = np.sin(np.radians(angles))
    gain = np.asarray(antenna.gain_dbi_uv(u, np.zeros_like(u)), dtype=float)
    boresight = float(antenna.gain_dbi_uv(0.0, 0.0))
    inside = angles[gain >= boresight - 3.0]
    return float(inside.max() - inside.min())


def quadrant_squint_deg(
    quadrants: tuple[TxQuadrant, ...],
) -> list[tuple[str, float, float]]:
    """Peak direction of each quadrant's own pattern along the u and v axes."""
    axis = np.linspace(-0.4, 0.4, 1601)
    zeros = np.zeros_like(axis)
    result: list[tuple[str, float, float]] = []
    for quadrant in quadrants:
        along_u = np.abs(quadrant_fields_uv((quadrant,), axis, zeros)[0])
        along_v = np.abs(quadrant_fields_uv((quadrant,), zeros, axis)[0])
        result.append(
            (
                quadrant.name,
                float(np.degrees(np.arcsin(axis[int(np.argmax(along_u))]))),
                float(np.degrees(np.arcsin(axis[int(np.argmax(along_v))]))),
            )
        )
    return result


def print_tx_taper_diagnostics(tx: RectangularArrayAntenna) -> None:
    """Show that the MIMO discrimination follows from the supplied defocus."""
    nominal = split_tx_quadrants(tx)
    focused = split_tx_quadrants(scaled_defocus_antenna(tx, 0.0))
    print("TX quadrant signature correlation, exact alias pairs")
    print(
        "  variant           vertical edges  horizontal edges  boresight/vert. replica"
    )
    for name, quadrants in (
        ("nominal (defocused)", nominal),
        ("amplitude taper only", focused),
        ("uniform quadrants", uniform_quadrants(nominal)),
    ):
        print(
            f"  {name:20s} {pair_correlation_db(quadrants, VERTICAL_EDGE, VERTICAL_ALIAS):8.2f} dB"
            f" {pair_correlation_db(quadrants, HORIZONTAL_EDGE, HORIZONTAL_ALIAS):10.2f} dB"
            f" {pair_correlation_db(quadrants, (0.0, 0.0), (0.0, PERIOD_V)):12.2f} dB"
        )
    print(
        f"  nominal TX: {float(tx.gain_dbi_uv(0.0, 0.0)):.2f} dBi, "
        f"{principal_beamwidth_deg(tx):.2f} deg 3 dB beamwidth; amplitude taper only: "
        f"{float(scaled_defocus_antenna(tx, 0.0).gain_dbi_uv(0.0, 0.0)):.2f} dBi, "
        f"{principal_beamwidth_deg(scaled_defocus_antenna(tx, 0.0)):.2f} deg"
    )
    print("  quadrant pattern peaks (nominal):")
    for name, u_deg, v_deg in quadrant_squint_deg(nominal):
        print(f"    {name:10s} u {u_deg:+5.1f} deg, v {v_deg:+5.1f} deg")
    print("Realized defocus scale (true = nominal phase x scale, nominal dictionary)")
    print("  scale  vert-edge rho   vert margin   horiz margin   coherent beamwidth")
    for scale in DEFOCUS_SCALES:
        antenna = scaled_defocus_antenna(tx, scale)
        quadrants = split_tx_quadrants(antenna)
        print(
            f"  {scale:4.1f} {pair_correlation_db(quadrants, VERTICAL_EDGE, VERTICAL_ALIAS):10.2f} dB"
            f" {mismatch_margin_db(quadrants, nominal, VERTICAL_EDGE, VERTICAL_ALIAS):10.1f} dB"
            f" {mismatch_margin_db(quadrants, nominal, HORIZONTAL_EDGE, HORIZONTAL_ALIAS):11.1f} dB"
            f" {principal_beamwidth_deg(antenna):12.2f} deg"
        )
    print("Uncalibrated systematic upper/lower quadrant phase error, vertical edge")
    for error_deg in QUADRANT_PHASE_ERRORS_DEG:
        perturbed = phase_offset_quadrants(nominal, error_deg)
        print(
            f"  {error_deg:4.0f} deg: margin "
            f"{mismatch_margin_db(perturbed, nominal, VERTICAL_EDGE, VERTICAL_ALIAS):5.1f} dB"
        )


# --- Stagger amount and competitors --------------------------------------------


def rx_pair_correlation(
    layout: RxAntennaLayout,
    first: tuple[float, float],
    second: tuple[float, float],
) -> float:
    """Squared normalized RX channel steering-vector correlation."""
    a1 = channel_steering_vectors(layout, first[0], first[1])
    a2 = channel_steering_vectors(layout, second[0], second[1])
    return float(np.abs(np.vdot(a1, a2)) ** 2 / (a1.size * a2.size))


def stagger_variant_row(name: str, layout: RxAntennaLayout) -> dict[str, object]:
    """Vertical-alias information and cost of one alternating-column variant."""
    period_v = WAVELENGTH_M / layout.subarray_height_m
    vertical = rx_pair_correlation(
        layout, (0.0, 0.5 * period_v), (0.0, -0.5 * period_v)
    )
    horizontal = rx_pair_correlation(layout, HORIZONTAL_EDGE, HORIZONTAL_ALIAS)
    return dict(
        name=name,
        subarray_height_mm=1e3 * layout.subarray_height_m,
        vertical_edge_deg=float(np.degrees(np.arcsin(0.5 * period_v))),
        one_minus_rho=1.0 - vertical,
        horizontal_rho=horizontal,
        subarray_gain_change_db=float(
            10 * np.log10(layout.subarray_height_m / RX_SOURCE_SUBARRAY_HEIGHT_M)
        ),
        aperture_height_mm=1e3 * layout.overall_height_m,
    )


def stagger_variant_rows() -> list[dict[str, object]]:
    """Offset sweep at the supplied height plus equal-total-height variants."""
    rows = [
        stagger_variant_row(f"8 rows, s = {fraction:g} H", staggered_layout(fraction))
        for fraction in STAGGER_FRACTIONS
    ]
    # Keep the 37.6 mm total height: 7-row subarrays with a two-pitch stagger
    # exactly fill the original 16-row grid, or shrink 8 rows continuously.
    rows.append(
        stagger_variant_row(
            "7 rows, s = 2 pitches",
            staggered_layout(2.0 / 7.0, subarray_height_m=7.0 * RADIATOR_PITCH_M),
        )
    )
    rows.append(
        stagger_variant_row(
            "8 rows shrunk, s = H'/4",
            staggered_layout(
                0.25, subarray_height_m=2.0 * RX_SOURCE_SUBARRAY_HEIGHT_M / 2.25
            ),
        )
    )
    return rows


def print_stagger_variant_table(rows: list[dict[str, object]]) -> None:
    """Coherent-mode information about the vertical alias versus offset."""
    print("Alternating column stagger variants (own vertical alias, H = 18.81 mm)")
    print(
        "  variant                    H [mm]  edge   1-rho   horiz rho"
        "  subarray gain  aperture height"
    )
    for row in rows:
        print(
            f"  {str(row['name']):26s}"
            f" {float(str(row['subarray_height_mm'])):6.2f}"
            f" {float(str(row['vertical_edge_deg'])):5.1f}°"
            f" {float(str(row['one_minus_rho'])):7.3f}"
            f" {float(str(row['horizontal_rho'])):9.3f}"
            f" {float(str(row['subarray_gain_change_db'])):+11.2f} dB"
            f" {float(str(row['aperture_height_mm'])):11.1f} mm"
        )


def two_way_gain_db(
    tx: RectangularArrayAntenna, u: FloatArray, v: FloatArray
) -> FloatArray:
    """TX gain plus single-subarray RX gain; the common RX constant is omitted."""
    return np.asarray(tx.gain_dbi_uv(u, v), dtype=float) + subarray_relative_gain_db(
        u, v
    )


def competitor_rows(
    tx: RectangularArrayAntenna,
    quadrants: tuple[TxQuadrant, ...],
    options: tuple[LayoutOption, ...],
    true_directions: tuple[tuple[str, float, float], ...],
    *,
    grid_samples: int = COMPETITOR_GRID_SAMPLES,
    rcs_ceiling_dbsm: float = COMPETITOR_RCS_CEILING_DBSM,
    rho_floor: float = COMPETITOR_RHO_FLOOR,
) -> list[dict[str, object]]:
    """Local maxima of coherent RX correlation that a bounded RCS cannot reject.

    Ordinary four-element sidelobes of every layout sit near -10 to -11 dB, so
    the default floor deliberately shows only stronger competitors plus the
    strongest of those sidelobes; it is a screen, not a probability.
    """
    axis = np.linspace(-1.0, 1.0, grid_samples)
    u, v = np.meshgrid(axis, axis, indexing="xy")
    visible = u**2 + v**2 <= 1.0
    gain = np.where(visible, two_way_gain_db(tx, u, v), -999.0)
    rows: list[dict[str, object]] = []
    for name, true_u, true_v in true_directions:
        reference_gain = float(two_way_gain_db(tx, np.array(true_u), np.array(true_v)))
        required_rcs = reference_gain - gain
        true_signature = quadrant_signature(quadrants, (true_u, true_v))
        for option in options:
            reference = channel_steering_vectors(option.layout, true_u, true_v)
            steering = channel_steering_vectors(option.layout, u, v)
            rho = np.abs(np.einsum("c,cij->ij", np.conj(reference), steering)) ** 2
            rho = np.where(visible, rho / reference.size**2, 0.0)
            peaks = (rho == maximum_filter(rho, size=15)) & (rho > rho_floor)
            for i, j in np.argwhere(peaks & (required_rcs <= rcs_ceiling_dbsm)):
                if abs(u[i, j] - true_u) < 0.02 and abs(v[i, j] - true_v) < 0.02:
                    continue
                mimo_rho = float(
                    normalized_correlation(
                        true_signature,
                        quadrant_signature(quadrants, (u[i, j], v[i, j])),
                    )
                ) * float(rho[i, j])
                rows.append(
                    dict(
                        true_direction=name,
                        layout=option.name,
                        u=float(u[i, j]),
                        v=float(v[i, j]),
                        rx_rho_db=float(10 * np.log10(rho[i, j])),
                        required_rcs_dbsm=float(required_rcs[i, j]),
                        mimo_rho_db=float(10 * np.log10(max(mimo_rho, 1e-30))),
                    )
                )
    return rows


def print_competitor_table(rows: list[dict[str, object]]) -> None:
    print(
        "Coherent-mode competitors (RX correlation peaks) requiring at most "
        f"+{COMPETITOR_RCS_CEILING_DBSM:g} dBsm; ordinary sidelobes near -10 dB"
    )
    print(
        "  true direction   layout       (u, v)            RX rho   req. RCS  MIMO rho"
    )
    for row in rows:
        print(
            f"  {str(row['true_direction']):16s} {str(row['layout']):12s}"
            f" ({float(str(row['u'])):+.3f}, {float(str(row['v'])):+.3f})"
            f" {float(str(row['rx_rho_db'])):8.2f} dB"
            f" {float(str(row['required_rcs_dbsm'])):6.1f} dBsm"
            f" {float(str(row['mimo_rho_db'])):8.2f} dB"
        )


@dataclass(frozen=True)
class InBeamCompetitorMap:
    """Strongest coherent-mode competitor for every in-beam true direction."""

    true_axis: FloatArray
    coherent_rho: FloatArray  # (layouts, true_u, true_v): strongest RX competitor
    mimo_at_coherent_competitor: FloatArray  # combined TX x RX rho at that direction
    mimo_worst: FloatArray  # strongest combined TX x RX competitor, searched separately


def in_beam_competitor_maps(
    tx: RectangularArrayAntenna,
    quadrants: tuple[TxQuadrant, ...],
    options: tuple[LayoutOption, ...],
    *,
    limit: float = IN_BEAM_LIMIT,
    samples: int = IN_BEAM_SAMPLES,
    grid_samples: int = IN_BEAM_GRID_SAMPLES,
    rcs_ceiling_dbsm: float = IN_BEAM_RCS_CEILING_DBSM,
) -> InBeamCompetitorMap:
    """Map the strongest competitors outside the true lobe, coherent and MIMO.

    Competitors are visible directions outside the true direction's own
    old-URA cell that could explain the noiseless coherent signal with at most
    ``rcs_ceiling_dbsm`` more RCS. Directions inside the own cell are ordinary
    local angle error, not aliases, whatever the layout. The MIMO competitor
    is searched separately over the same admissible set; the strongest
    coherent competitor is not in general the strongest MIMO competitor
    (review finding, 2026-09-10).
    """
    axis = np.linspace(-1.0, 1.0, grid_samples)
    u, v = np.meshgrid(axis, axis, indexing="xy")
    visible = u**2 + v**2 <= 1.0
    gain = np.where(visible, two_way_gain_db(tx, u, v), -999.0)
    fields = quadrant_fields_uv(quadrants, u, v)
    fields_power = np.maximum(np.sum(np.abs(fields) ** 2, axis=0), 1e-30)
    true_axis = np.linspace(-limit, limit, samples)
    coherent = np.zeros((len(options), samples, samples))
    mimo_at_coherent = np.zeros_like(coherent)
    mimo_worst = np.zeros_like(coherent)
    for index, option in enumerate(options):
        steering = channel_steering_vectors(option.layout, u, v)
        for i, true_u in enumerate(true_axis):
            for j, true_v in enumerate(true_axis):
                reference = channel_steering_vectors(option.layout, true_u, true_v)
                rho = np.abs(np.einsum("c,cij->ij", np.conj(reference), steering)) ** 2
                rho = rho / reference.size**2
                required = (
                    float(two_way_gain_db(tx, np.array(true_u), np.array(true_v)))
                    - gain
                )
                outside = (np.abs(u - true_u) >= 0.5 * PERIOD_U) | (
                    np.abs(v - true_v) >= 0.5 * PERIOD_V
                )
                admissible = visible & outside & (required <= rcs_ceiling_dbsm)
                candidate = np.where(admissible, rho, 0.0)
                best = np.unravel_index(int(np.argmax(candidate)), candidate.shape)
                coherent[index, i, j] = candidate[best]
                true_fields = quadrant_signature(quadrants, (true_u, true_v))
                tx_rho = np.abs(
                    np.einsum("q,qij->ij", np.conj(true_fields), fields)
                ) ** 2 / (np.sum(np.abs(true_fields) ** 2) * fields_power)
                combined = np.where(admissible, tx_rho * rho, 0.0)
                mimo_at_coherent[index, i, j] = combined[best]
                mimo_worst[index, i, j] = float(np.max(combined))
    return InBeamCompetitorMap(true_axis, coherent, mimo_at_coherent, mimo_worst)


def print_in_beam_summary(
    maps: InBeamCompetitorMap, options: tuple[LayoutOption, ...]
) -> None:
    inside = np.abs(maps.true_axis) <= TX_HALF_POWER_V
    box = np.ix_(inside, inside)
    print(
        "Worst in-beam competitor within the TX 3 dB region (|u|,|v| <= 0.109), "
        f"RCS ceiling +{IN_BEAM_RCS_CEILING_DBSM:g} dBsm"
    )
    for index, option in enumerate(options):
        coherent = maps.coherent_rho[index][box]
        mimo_at = maps.mimo_at_coherent_competitor[index][box]
        mimo_worst = maps.mimo_worst[index][box]
        print(
            f"  {option.name:12s} max coherent rho {10 * np.log10(max(coherent.max(), 1e-30)):6.2f} dB;"
            f" fraction of directions with a competitor >= -3 dB: "
            f"{np.mean(coherent >= 0.5):.2f}, >= -1 dB: {np.mean(coherent >= 10 ** -0.1):.2f};"
            f" MIMO rho at that competitor, max {10 * np.log10(max(mimo_at.max(), 1e-30)):6.2f} dB;"
            f" worst MIMO competitor {10 * np.log10(max(mimo_worst.max(), 1e-30)):6.2f} dB"
        )


def plot_in_beam_maps(
    maps: InBeamCompetitorMap, options: tuple[LayoutOption, ...], path: Path
) -> None:
    fig, axes = plt.subplots(2, len(options), figsize=(13.5, 8.6))
    extent = (
        maps.true_axis[0],
        maps.true_axis[-1],
        maps.true_axis[0],
        maps.true_axis[-1],
    )
    images = []
    for index, option in enumerate(options):
        for row, (data, floor, title) in enumerate(
            (
                (maps.coherent_rho[index], -15.0, "coherent mode"),
                (maps.mimo_worst[index], -35.0, "four-quadrant MIMO"),
            )
        ):
            ax = axes[row, index]
            image = ax.imshow(
                np.maximum(10 * np.log10(np.maximum(data.T, 1e-30)), floor),
                origin="lower",
                extent=extent,
                cmap="magma",
                vmin=floor,
                vmax=0.0,
                aspect="equal",
            )
            images.append(image)
            ax.add_patch(
                Rectangle(
                    (-TX_HALF_POWER_V, -TX_HALF_POWER_V),
                    2 * TX_HALF_POWER_V,
                    2 * TX_HALF_POWER_V,
                    fill=False,
                    edgecolor="cyan",
                    linestyle="--",
                    linewidth=1.0,
                )
            )
            ax.set_title(f"{option.name}: {title}")
            ax.set_xlabel("true u")
            ax.set_ylabel("true v")
    fig.colorbar(images[0], ax=axes[0, :].tolist(), fraction=0.03, pad=0.02).set_label(
        "strongest competitor: coherent RX correlation [dB]"
    )
    fig.colorbar(images[1], ax=axes[1, :].tolist(), fraction=0.03, pad=0.02).set_label(
        "strongest MIMO competitor: combined TX x RX correlation [dB]"
    )
    fig.suptitle(
        "Strongest alias competitor for every in-beam true direction\n"
        f"competitors outside the own old-URA cell needing at most "
        f"+{IN_BEAM_RCS_CEILING_DBSM:g} dBsm, searched separately per mode; "
        "cyan: TX 3 dB region",
        fontsize=14,
    )
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  saved {path}")


# --- Multi-frame resolution events ---------------------------------------------


def simulate_multi_frame_event(
    bank: HypothesisBank,
    true_rx: ComplexArray,
    true_quadrants: ComplexArray,
    *,
    coherent_snr_db: float,
    mimo_to_coherent_snr: float,
    energies: FloatArray,
    update_counts: tuple[int, ...],
    trials: int,
    phase_rms_deg: float = 0.0,
    column_group_phase_deg: float = 0.0,
    seed: int = SEED,
) -> npt.NDArray[np.int64]:
    """Wrong-lobe counts for K coherent frames plus one MIMO measurement.

    Coherent frames have independent noise and a fixed target; an unknown
    complex amplitude is fitted per frame, so frame scores add. This is the
    K-frame generalization of ``rx_resolution_experiment.simulate_event``.
    ``column_group_phase_deg`` is a systematic, uncalibrated phase applied to
    the true response of RX columns two and four; the bank stays nominal.
    """
    true_rx = np.asarray(
        true_rx
        * np.exp(1j * np.radians(column_group_phase_deg) * ALTERNATE_COLUMN_MASK),
        dtype=np.complex128,
    )
    if trials < 1 or min(update_counts) < 1:
        raise ValueError("positive trials and update counts are required")
    if np.any(energies < 0) or mimo_to_coherent_snr <= 0 or phase_rms_deg < 0:
        raise ValueError("energies/phase RMS must be nonnegative, SNR ratio positive")
    rng = np.random.default_rng(seed)
    decision_rng = np.random.default_rng(seed + 1)
    errors = np.zeros((len(update_counts), energies.size), dtype=np.int64)
    snr = 10 ** (coherent_snr_db / 10)
    quadrant_norm = np.linalg.norm(true_quadrants)
    quadrant_sum = np.sum(true_quadrants)
    if abs(quadrant_sum) == 0 or quadrant_norm == 0:
        raise ValueError("the event must have nonzero coherent and MIMO illumination")
    for start in range(0, trials, 1000):
        count = min(1000, trials - start)
        rx_errors = np.exp(
            1j * np.radians(phase_rms_deg) * rng.standard_normal((count, true_rx.size))
        )
        tx_errors = np.exp(
            1j * np.radians(phase_rms_deg) * rng.standard_normal((count, 4))
        )
        rx_signal = true_rx[None, :] * rx_errors
        tx_fields = true_quadrants[None, :] * tx_errors
        coherent_signal = (
            rx_signal * (np.sum(tx_fields, axis=1) / quadrant_sum)[:, None]
        )
        mimo_signal = (
            tx_fields[:, :, None] * rx_signal[:, None, :] / quadrant_norm
        ).reshape(count, -1)
        cumulative = np.zeros((count, bank.coherent.shape[1]))
        coherent_scores: list[FloatArray] = []
        for _ in range(max(update_counts)):
            data = np.sqrt(snr) * coherent_signal + complex_noise(
                rng, (count, true_rx.size)
            )
            cumulative = cumulative + np.abs(data @ bank.coherent.conj()) ** 2
            coherent_scores.append(np.asarray(cumulative, dtype=float))
        mimo_noise_projection = (
            complex_noise(rng, (count, mimo_signal.shape[1])) @ bank.mimo.conj()
        )
        mimo_signal_projection = mimo_signal @ bank.mimo.conj()
        for row, update_count in enumerate(update_counts):
            for column, energy in enumerate(energies):
                scores = coherent_scores[update_count - 1]
                if energy > 0:
                    scores = (
                        scores
                        + np.abs(
                            np.sqrt(energy * snr * mimo_to_coherent_snr)
                            * mimo_signal_projection
                            + mimo_noise_projection
                        )
                        ** 2
                    )
                chosen = choose_cells(scores, bank.cell_starts, decision_rng)
                errors[row, column] += np.count_nonzero(chosen != bank.true_cell)
    return errors


def run_multi_frame_events(trials: int) -> list[dict[str, object]]:
    tx = load_tx_antenna()
    quadrants = split_tx_quadrants(tx)
    records: list[dict[str, object]] = []
    for case in CASES:
        fields = quadrant_fields_uv(quadrants, np.asarray(case.u), np.asarray(case.v))
        ratio = 10 ** (
            (
                float(
                    mimo_tx_gain_dbi(quadrants, np.asarray(case.u), np.asarray(case.v))
                )
                - float(tx.gain_dbi_uv(case.u, case.v))
            )
            / 10
        )
        for option in LAYOUT_OPTIONS:
            bank = build_bank(
                case,
                option.layout,
                tx,
                quadrants,
                u_seed_fraction=BANK_U_SEED_FRACTION,
            )
            rx = normalize_columns(
                channel_steering_vectors(
                    option.layout, np.array([case.u]), np.array([case.v])
                )
            )[:, 0]
            for snr_db in COHERENT_SNR_DB:
                for scenario, phase_rms, group_phase in RX_ERROR_SCENARIOS:
                    errors = simulate_multi_frame_event(
                        bank,
                        rx,
                        fields,
                        coherent_snr_db=snr_db,
                        mimo_to_coherent_snr=ratio,
                        energies=ENERGIES,
                        update_counts=COHERENT_UPDATE_COUNTS,
                        trials=trials,
                        phase_rms_deg=phase_rms,
                        column_group_phase_deg=group_phase,
                    )
                    for row, update_count in enumerate(COHERENT_UPDATE_COUNTS):
                        upper = error_upper_bound(errors[row], trials)
                        meets = np.flatnonzero(upper <= 0.01)
                        records.append(
                            dict(
                                case=case.name,
                                layout=option.name,
                                coherent_snr_db=snr_db,
                                rx_error=scenario,
                                phase_rms_deg=phase_rms,
                                column_group_phase_deg=group_phase,
                                coherent_updates=update_count,
                                candidate_lobes=len(bank.cell_ids),
                                errors=errors[row].tolist(),
                                error_upper_95=upper.tolist(),
                                first_sampled_energy_with_upper_error_below_1pct=(
                                    float(ENERGIES[meets[0]]) if meets.size else None
                                ),
                            )
                        )
            print(f"  {case.name}, {option.name}: {len(bank.cell_ids)} lobes done")
    return records


def print_event_summary(records: list[dict[str, object]], trials: int) -> None:
    print("Wrong-lobe probability after K coherent frames without MIMO, and first")
    print("sampled MIMO energy (after K frames) whose 95% upper error bound is <= 1%")
    print(
        "  case             layout       SNR  RX error            K   P(err) no MIMO   energy"
    )
    for record in records:
        errors = np.asarray(record["errors"], dtype=float)
        print(
            f"  {str(record['case']):16s} {str(record['layout']):12s}"
            f" {float(str(record['coherent_snr_db'])):3.0f}"
            f" {str(record['rx_error']):18s}"
            f" {int(str(record['coherent_updates'])):2d}"
            f" {errors[0] / trials:14.4f}"
            f"   {record['first_sampled_energy_with_upper_error_below_1pct']}"
        )


def plot_vertical_edge(
    records: list[dict[str, object]], path: Path, trials: int
) -> None:
    """Vertical-edge event: error versus MIMO energy per layout and frame count."""
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 8.0), sharex=True, sharey=True)
    colors = {1: "C0", 2: "C1", 4: "C3"}
    for record in records:
        if record["case"] != CASES[0].name:
            continue
        row = COHERENT_SNR_DB.index(float(str(record["coherent_snr_db"])))
        column = [option.name for option in LAYOUT_OPTIONS].index(str(record["layout"]))
        ax = axes[row, column]
        errors = np.asarray(record["errors"], dtype=int)
        upper = error_upper_bound(errors, trials)
        updates = int(str(record["coherent_updates"]))
        scenario = str(record["rx_error"])
        linestyle = {"nominal": "-", "10° random": "--", "+15° column group": ":"}[
            scenario
        ]
        ax.plot(
            ENERGIES,
            np.where(errors > 0, errors / trials, np.nan),
            color=colors[updates],
            linestyle=linestyle,
            marker="o",
            markersize=3,
            label=(
                f"{updates} coherent frame{'s' if updates > 1 else ''}"
                f"{'' if scenario == 'nominal' else ', ' + scenario}"
            ),
        )
        ax.scatter(
            ENERGIES[errors == 0],
            upper[errors == 0],
            marker="v",
            color=colors[updates],
            s=25,
        )
        ax.set_title(
            f"{record['layout']} | nominal SNR {record['coherent_snr_db']:g} dB"
        )
    for ax in axes.flat:
        ax.set_xscale("symlog", linthresh=0.125, base=2)
        ax.set_yscale("log")
        ax.set_ylim(3e-5, 1.0)
        ticks = [0.0, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0]
        ax.set_xticks(ticks, [f"{energy:g}" for energy in ticks])
        ax.axhline(0.01, color="0.4", linestyle=":", linewidth=1)
        ax.grid(True, alpha=0.25, which="both")
        ax.set_xlabel("additional MIMO illumination [baseline CPI equivalents]")
        ax.set_ylabel("wrong-lobe decision probability")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.05))
    fig.suptitle(
        "Vertical-edge resolution event: K coherent frames + on-demand MIMO\n"
        "URA versus height/8 and height/4 alternating column stagger",
        fontsize=14,
    )
    fig.text(
        0.5,
        0.015,
        f"Fixed 1 m² target in a known gate; {trials:,} trials; independent frame "
        "noise; unknown amplitude per update; ▼: zero errors at 95% upper bound\n"
        "Candidate lobes seeded at half u-periods to include the diagonal "
        "near-alias family; nominal dictionary under all RX error scenarios\n"
        "Ideal energy scaling, not latency; no fluctuation, motion or detection "
        "threshold; height/4 is a study construct, the sketch used one pitch",
        ha="center",
        fontsize=8,
        color="0.3",
    )
    fig.tight_layout(rect=(0, 0.15, 1, 0.92))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  saved {path}")


def _in_beam_max_db(values: FloatArray, true_axis: FloatArray) -> float:
    inside = np.abs(true_axis) <= TX_HALF_POWER_V
    return float(10 * np.log10(max(float(values[np.ix_(inside, inside)].max()), 1e-30)))


def run(output_dir: Path, *, trials: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    tx = load_tx_antenna()
    quadrants = split_tx_quadrants(tx)
    print_tx_taper_diagnostics(tx)
    variants = stagger_variant_rows()
    print_stagger_variant_table(variants)
    competitors = competitor_rows(
        tx, quadrants, LAYOUT_OPTIONS, COMPETITOR_TRUE_DIRECTIONS
    )
    print_competitor_table(competitors)
    maps = in_beam_competitor_maps(tx, quadrants, LAYOUT_OPTIONS)
    print_in_beam_summary(maps, LAYOUT_OPTIONS)
    plot_in_beam_maps(
        maps, LAYOUT_OPTIONS, output_dir / "stagger_in_beam_competitors.png"
    )
    print("Multi-frame resolution events")
    records = run_multi_frame_events(trials)
    print_event_summary(records, trials)
    summary = dict(
        seed=SEED,
        trials=trials,
        energy_cpi_equivalents=ENERGIES.tolist(),
        coherent_update_counts=list(COHERENT_UPDATE_COUNTS),
        notes=(
            "Fixed-RCS known-target events; K coherent frames with independent "
            "noise plus one MIMO integration; candidate lobes seeded at half "
            "u-periods; nominal dictionary; not latency, fluctuation or "
            "publication confidence. Height/4 is a study construct."
        ),
        rx_error_scenarios=[list(item) for item in RX_ERROR_SCENARIOS],
        stagger_variants=variants,
        competitors=competitors,
        in_beam_worst_rho_db={
            option.name: dict(
                coherent=_in_beam_max_db(maps.coherent_rho[index], maps.true_axis),
                mimo_at_coherent_competitor=_in_beam_max_db(
                    maps.mimo_at_coherent_competitor[index], maps.true_axis
                ),
                mimo_worst=_in_beam_max_db(maps.mimo_worst[index], maps.true_axis),
            )
            for index, option in enumerate(LAYOUT_OPTIONS)
        },
        records=records,
    )
    (output_dir / "stagger_amount_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    plot_vertical_edge(records, output_dir / "stagger_amount_vertical_edge.png", trials)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=20000)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "generated" / "experimental" / "on_demand",
    )
    args = parser.parse_args()
    run(args.output_dir, trials=args.trials)


if __name__ == "__main__":
    main()
