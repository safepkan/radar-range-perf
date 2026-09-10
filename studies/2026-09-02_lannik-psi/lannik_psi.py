"""Range-performance baseline for Lannik Psi.

This study started with config 3 from the 2026-06-22 configuration comparison.
It now uses the proposed complex excitation taper for the complete Lannik Psi
TX aperture while retaining the original evaluation scenario. Run it from the
repo root with::

    venv/bin/python studies/2026-09-02_lannik-psi/lannik_psi.py

It writes "Pd + Pacq vs range", TX/RX/two-way antenna patterns and static Pd
coverage maps to the study-local ``generated/`` directory, prints diagnostics
and, under an interactive Matplotlib backend, opens the figures.

Scenario
--------
* Target: 1 m^2 RCS, Swerling 1, at boresight.
* Acquisition: closing at 15 m/s, 20 Hz frame rate, 2-of-3 confirmation.
* Pfa = 1e-6.

The initial range is far enough that single-scan Pd is solidly zero at the start
of the run. The plot is zoomed to the product's detection range.

Changes from the 2026-06-22 config-3 baseline
----------------------------------------------
* TX antenna: the previous 17 dBi per-channel placeholder plus ideal 8-channel
  coherent-TX directivity has been replaced by the proposed 23.5 dBi complete
  aperture pattern. Relative to one TX channel's power, the old TX contribution
  was 17 + 20 log10(8) = 35.1 dB; the current contribution is the 23.5 dBi
  aperture plus 10 log10(8) = 32.5 dB of total TX power. The 2.5 dB reduction
  explains the boresight Pd=90% range changing from 614 m to 531 m (range scales
  with the fourth root of power).
* RX antenna: the previous 17 dBi constant-gain channel placeholder has been
  replaced by an analytical uniform rectangular subarray pattern plus the
  steered array factor of a parametric eight-channel URA. The baseline uses the
  supplied 2.42 x 4.83-lambda rectangular subarrays in a densely packed 4 x 2
  layout. Ideal coherent combination of 8 RX channels remains in processing,
  giving 30.5 dBi effective boresight RX gain.
* Front end, waveform and evaluation scenario: unchanged.
* Boresight range checkpoints (Pd=50%/90%; Pacq=50%/90%): the June baseline was
  994/614 m and 1474/1372 m; after introducing only the TX aperture it was
  859/531 m and 1264/1174 m; with the current supplied-size RX subarrays it is
  1114/688 m and 1662/1549 m. The 2.42-lambda square candidate gave 937/578 m
  and 1384/1288 m. Adding multiple RX beams does not change those boresight
  checkpoints; it extends the modeled angular coverage. Extend this list when
  later model changes affect the result.

Modelling notes
---------------
* The TX model is the complete 16 x 16 aperture. Its amplitude and phase taper
  comes from ``inputs/antenna_arr_77_TX_rev_A.mat``. The complete supplied
  presentation, MATLAB loader and TX/RX data are archived under ``inputs/``.
  The full-aperture pattern uses the supplied complex excitation but does not
  depend on the apparent channel labels in the file. Processing assumes 8
  coherent, equal-full-power MMIC channels when calculating total TX power. The
  current physical direction is to divide each quadrant excitation into two
  equal-power feeds without attenuation; the file's channel labels are not
  treated as the resulting geometry. See ``NOTES.md``.
* The FFT array factor is normalized to fixed total TX power. A 6.45 dBi
  radiator gain is inferred from the presentation's approximate 23.5 dBi
  tapered sum-beam directivity. Processing adds the power from 8 active TX
  channels but does not add a second ideal TX array-directivity term.
* RX is modelled in two layers. An analytical uniformly illuminated rectangular
  aperture supplies the per-channel subarray pattern. A parametrized channel
  URA then forms an interleaved set of u/v-steered beams; the ideal 8-channel
  coherent peak gain remains in processing. Detection uses the best-gain beam
  independently at each look direction. This is an optimistic upper bound:
  multiple-testing Pfa effects, correlated noise between beams and
  implementation limits are not yet modelled.
* One 64-beam RX set is used throughout. It consists of an 8 x 4 grid sampling
  the boresight-centered fundamental array-factor period plus an equally sized
  half-cell-offset grid. Because steering vectors repeat between periods, this
  set supplies the same best array-factor envelope throughout visible u/v
  space; the RX subarray pattern still weights each periodic replica. Red
  dashed plot markers identify the principal-region edges; detections outside
  them have an angular alias inside them under the current RX model.
* Boresight SNR is independent of the chirp slope; the slope only sets the
  maximum unambiguous range. The 2 MHz/us slope was not specified in the source
  study and is assumed so the unambiguous range clears the detection range.
* Phase noise and clutter are not modelled. The TX radiator element pattern is
  also treated as constant, so far-out lobes should not yet be interpreted as a
  complete installed-antenna prediction.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from matplotlib.axes import Axes
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle
from matplotlib.projections.polar import PolarAxes
from scipy.io import loadmat

from radarperf import (
    AntennaPair,
    Antenna,
    BeamCombination,
    ConstantRcsTarget,
    FmcwWaveform,
    Geometry,
    MultiBeamUniformArrayAntenna,
    Radar,
    RadialApproach,
    RectangularArrayAntenna,
    StandardProcessing,
    UniformArrayAntenna,
    UniformRectangularApertureAntenna,
    frontend,
    probability_of_detection,
    sweeps,
)
from radarperf.plotting import (
    is_non_interactive_backend,
    plot_pattern_cuts,
    plot_pattern_uv,
)
from radarperf.sweeps import AcquisitionSweep, Map2D
from radarperf.units import SPEED_OF_LIGHT

# --- Scenario (unchanged from the 2026-06-22 comparison) --------------------

CENTER_FREQUENCY_HZ = 77.0e9
TARGET = ConstantRcsTarget(rcs=1.0, swerling=1, name="1 m^2 Swerling-1")
CLOSING_SPEED_MPS = 15.0
FRAME_TIME_S = 1.0 / 20.0  # 20 Hz frame rate
CONFIRM = (2, 3)  # 2-of-3 sliding confirmation
PFA = 1.0e-6
INITIAL_RANGE_M = 3000.0
DETECTION_LEVELS = (0.5, 0.9)

SCENARIO_TEXT = (
    "1 m^2 RCS, Swerling 1, boresight  |  closing 15 m/s, 20 Hz frame, "
    "2-of-3 confirm  |  Pfa 1e-6"
)

# --- Antenna ---------------------------------------------------------------

INPUT_DIR = Path(__file__).parent / "inputs"
TX_DATA_PATH = INPUT_DIR / "antenna_arr_77_TX_rev_A.mat"
# The supplied weights contribute 17.05 dB at boresight. Adding 6.45 dBi per
# radiator reproduces the presentation's approximate 23.5 dBi tapered sum
# directivity. It also gives 21.5 dBi for a uniform 32-radiator subarray and
# 30.5 dBi for the uniform 256-radiator aperture, consistent with the
# presentation's approximate 21 dBi and 31 dBi figures.
RADIATOR_GAIN_DBI = 6.45
APERTURE_FFT_SIZE = 2048
# Reference values inferred from the supplied RX aperture. Each original
# channel occupied four by eight radiator pitches. The continuous-aperture
# efficiency is calibrated to reproduce that model's 21.50 dBi subarray gain.
RX_SOURCE_RADIATOR_PITCH_M = 2.3513137254901964e-3
RX_SOURCE_SUBARRAY_WIDTH_M = 4.0 * RX_SOURCE_RADIATOR_PITCH_M
RX_SOURCE_SUBARRAY_HEIGHT_M = 8.0 * RX_SOURCE_RADIATOR_PITCH_M
RX_SOURCE_SUBARRAY_GAIN_DBI = RADIATOR_GAIN_DBI + 10.0 * np.log10(32.0)
RX_APERTURE_EFFICIENCY = 10.0 ** (RX_SOURCE_SUBARRAY_GAIN_DBI / 10.0) / (
    4.0
    * np.pi
    * RX_SOURCE_SUBARRAY_WIDTH_M
    * RX_SOURCE_SUBARRAY_HEIGHT_M
    / (SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ) ** 2
)
RX_BEAM_SEPARATION_DEG = 3.0
# Maximum desired spacing. Exact u/v spacings divide the array-factor periods
# into integer counts so that the grid wraps seamlessly at principal-cell edges.
RX_BEAM_SEPARATION_UV = float(np.sin(np.radians(RX_BEAM_SEPARATION_DEG)))
PD_MAP_LEVELS = (0.5, 0.9)
PD_MAP_ANGLE_SAMPLES = 241
PD_MAP_RANGE_SAMPLES = 401
PD_MAP_TRANSVERSE_SAMPLES = 301
PD_MAP_RANGE_LIMIT_M = 1500.0
PD_MAP_TRANSVERSE_LIMIT_M = 200.0

CutPlaneName = Literal["horizontal", "vertical", "diagonal"]


@dataclass(frozen=True)
class SteeringGrid:
    """Two interleaved grids sampling one periodic RX steering cell."""

    u: npt.NDArray[np.float64]
    v: npt.NDArray[np.float64]
    primary_count: int
    primary_u_count: int
    primary_v_count: int
    separation_u: float
    separation_v: float
    period_u: float
    period_v: float


@dataclass(frozen=True)
class RxAntennaLayout:
    """Parametric RX subarray and channel-array geometry."""

    subarray_width_m: float
    subarray_height_m: float
    horizontal_count: int
    vertical_count: int
    horizontal_spacing_m: float | None = None
    vertical_spacing_m: float | None = None
    vertical_offsets_by_horizontal_m: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        for name, extent_m in (
            ("subarray_width_m", self.subarray_width_m),
            ("subarray_height_m", self.subarray_height_m),
        ):
            if not np.isfinite(extent_m) or extent_m <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        for name, count in (
            ("horizontal_count", self.horizontal_count),
            ("vertical_count", self.vertical_count),
        ):
            if count < 1:
                raise ValueError(f"{name} must be >= 1")
        for name, spacing_m, extent_m in (
            (
                "horizontal_spacing_m",
                self.horizontal_spacing_m,
                self.subarray_width_m,
            ),
            (
                "vertical_spacing_m",
                self.vertical_spacing_m,
                self.subarray_height_m,
            ),
        ):
            if spacing_m is not None and (
                not np.isfinite(spacing_m) or spacing_m < extent_m
            ):
                raise ValueError(f"{name} must be finite and at least the extent")
        if self.vertical_offsets_by_horizontal_m is not None:
            if len(self.vertical_offsets_by_horizontal_m) != self.horizontal_count:
                raise ValueError(
                    "vertical_offsets_by_horizontal_m must contain one offset "
                    "per horizontal channel position"
                )
            if not bool(np.all(np.isfinite(self.vertical_offsets_by_horizontal_m))):
                raise ValueError("vertical_offsets_by_horizontal_m must be finite")

    @property
    def channel_horizontal_spacing_m(self) -> float:
        """Horizontal channel-center spacing, densely packed by default."""
        if self.horizontal_spacing_m is None:
            return self.subarray_width_m
        return self.horizontal_spacing_m

    @property
    def channel_vertical_spacing_m(self) -> float:
        """Vertical channel-center spacing, densely packed by default."""
        if self.vertical_spacing_m is None:
            return self.subarray_height_m
        return self.vertical_spacing_m

    @property
    def channel_count(self) -> int:
        """Total number of RX channels."""
        return self.horizontal_count * self.vertical_count

    @property
    def channel_center_positions_m(
        self,
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Return flattened horizontal and vertical channel phase centers."""
        horizontal_axis = (
            np.arange(self.horizontal_count, dtype=float)
            - 0.5 * (self.horizontal_count - 1)
        ) * self.channel_horizontal_spacing_m
        vertical_axis = (
            np.arange(self.vertical_count, dtype=float)
            - 0.5 * (self.vertical_count - 1)
        ) * self.channel_vertical_spacing_m
        horizontal, vertical = np.meshgrid(
            horizontal_axis, vertical_axis, indexing="ij"
        )
        if self.vertical_offsets_by_horizontal_m is not None:
            vertical += np.asarray(self.vertical_offsets_by_horizontal_m, dtype=float)[
                :, None
            ]
        return (
            np.asarray(horizontal.ravel(), dtype=float),
            np.asarray(vertical.ravel(), dtype=float),
        )

    @property
    def overall_width_m(self) -> float:
        """Edge-to-edge width of the complete RX aperture."""
        horizontal, _ = self.channel_center_positions_m
        return float(np.ptp(horizontal) + self.subarray_width_m)

    @property
    def overall_height_m(self) -> float:
        """Edge-to-edge height of the complete RX aperture."""
        _, vertical = self.channel_center_positions_m
        return float(np.ptp(vertical) + self.subarray_height_m)


@dataclass(frozen=True)
class CoverageCut:
    """One plane through boresight used for static Pd coverage maps."""

    name: CutPlaneName
    title: str
    transverse_label: str


COVERAGE_CUTS = (
    CoverageCut("horizontal", "Horizontal plane", "lateral offset y [m] (left +)"),
    CoverageCut("vertical", "Vertical plane", "vertical offset z [m] (up +)"),
    CoverageCut(
        "diagonal",
        "45° diagonal plane",
        "diagonal offset s [m] (left/up +)",
    ),
)


@dataclass(frozen=True)
class Product:
    """The Lannik Psi baseline plus short notes for reports."""

    name: str
    radar: Radar
    waveform: FmcwWaveform
    front_end_note: str
    waveform_note: str
    processing_note: str


# Explicit alternatives retained for study comparisons. The supplied rectangle
# is again the main baseline now that track-directed MIMO appears capable of
# resolving its closer vertical aliases without giving up 3 dB of RX gain.
RX_SUPPLIED_LAYOUT = RxAntennaLayout(
    subarray_width_m=RX_SOURCE_SUBARRAY_WIDTH_M,
    subarray_height_m=RX_SOURCE_SUBARRAY_HEIGHT_M,
    horizontal_count=4,
    vertical_count=2,
)
RX_SQUARE_LAYOUT = RxAntennaLayout(
    subarray_width_m=RX_SOURCE_SUBARRAY_WIDTH_M,
    subarray_height_m=RX_SOURCE_SUBARRAY_WIDTH_M,
    horizontal_count=2,
    vertical_count=4,
)
# Provisional internal sketch (2026-09-08): alternate the vertical position of
# two-channel columns. The difference between the two column positions is one
# eighth of the rectangular subarray height; symmetric offsets keep the whole
# layout centered without affecting its array-factor power.
RX_EXPERIMENTAL_STAGGERED_LAYOUT = RxAntennaLayout(
    subarray_width_m=RX_SOURCE_SUBARRAY_WIDTH_M,
    subarray_height_m=RX_SOURCE_SUBARRAY_HEIGHT_M,
    horizontal_count=4,
    vertical_count=2,
    vertical_offsets_by_horizontal_m=(
        RX_SOURCE_SUBARRAY_HEIGHT_M / 16.0,
        -RX_SOURCE_SUBARRAY_HEIGHT_M / 16.0,
        RX_SOURCE_SUBARRAY_HEIGHT_M / 16.0,
        -RX_SOURCE_SUBARRAY_HEIGHT_M / 16.0,
    ),
)
RX_LAYOUT = RX_SUPPLIED_LAYOUT


def load_element_list(path: Path) -> npt.NDArray[np.complex128]:
    """Load and validate the common MATLAB antenna element-list table."""
    contents = loadmat(path)
    if "antenna_arr" not in contents:
        raise ValueError(f"{path} does not contain antenna_arr")
    element_list = np.asarray(contents["antenna_arr"], dtype=complex)
    if element_list.ndim != 2 or element_list.shape[1] < 6:
        raise ValueError("antenna_arr must be a 2-D table with at least 6 columns")
    if np.any(np.abs(element_list[:, 1:3].imag) > 0.0):
        raise ValueError("antenna coordinates must be real")
    if np.any(np.abs(element_list[:, 5].imag) > 0.0):
        raise ValueError("antenna channel indices must be real")
    channels = np.asarray(element_list[:, 5].real, dtype=int)
    if not np.array_equal(np.unique(channels), np.arange(1, 9)):
        raise ValueError("expected subarray channel indices 1 through 8")
    return np.asarray(element_list, dtype=np.complex128)


def load_tx_antenna(path: Path = TX_DATA_PATH) -> RectangularArrayAntenna:
    """Load the proposed TX coordinate/excitation list into a rectangular grid."""
    element_list = load_element_list(path)

    horizontal_positions_m = np.asarray(element_list[:, 1].real, dtype=float)
    vertical_positions_m = np.asarray(element_list[:, 2].real, dtype=float)
    excitations = np.asarray(element_list[:, 4], dtype=complex)

    return RectangularArrayAntenna.from_element_list(
        horizontal_positions_m,
        vertical_positions_m,
        excitations,
        center_frequency_hz=CENTER_FREQUENCY_HZ,
        element_gain_dbi=RADIATOR_GAIN_DBI,
        fft_size=APERTURE_FFT_SIZE,
    )


def build_rx_antenna(layout: RxAntennaLayout) -> UniformArrayAntenna:
    """Build the analytical uniform subarray and boresight channel URA."""
    if layout.channel_count != 8:
        raise ValueError("Lannik Psi RX layout must contain eight channels")
    if layout.vertical_offsets_by_horizontal_m is not None:
        raise ValueError(
            "the main range model does not yet support staggered RX phase centers; "
            "use rx_layout_experiment.py for the provisional layout analysis"
        )
    subarray = UniformRectangularApertureAntenna(
        layout.subarray_width_m,
        layout.subarray_height_m,
        center_frequency_hz=CENTER_FREQUENCY_HZ,
        aperture_efficiency=RX_APERTURE_EFFICIENCY,
    )
    return UniformArrayAntenna(
        subarray,
        horizontal_count=layout.horizontal_count,
        vertical_count=layout.vertical_count,
        horizontal_spacing_m=layout.channel_horizontal_spacing_m,
        vertical_spacing_m=layout.channel_vertical_spacing_m,
        center_frequency_hz=CENTER_FREQUENCY_HZ,
    )


RxArray = UniformArrayAntenna | MultiBeamUniformArrayAntenna


def rx_array_factor_periods(rx_array: RxArray) -> tuple[float, float]:
    """Return array-factor periods in steering coordinates u and v."""
    wavelength_m = SPEED_OF_LIGHT / rx_array.center_frequency_hz
    return (
        wavelength_m / rx_array.horizontal_spacing_m,
        wavelength_m / rx_array.vertical_spacing_m,
    )


def rx_principal_half_widths(rx_array: RxArray) -> tuple[float, float]:
    """Return half-widths of the boresight-centered principal steering cell."""
    period_u, period_v = rx_array_factor_periods(rx_array)
    return 0.5 * period_u, 0.5 * period_v


def rx_principal_cut_angles_deg(rx_array: RxArray) -> tuple[float, float]:
    """Return principal-region edges in the azimuth and elevation cuts."""
    half_u, half_v = rx_principal_half_widths(rx_array)
    return (
        float(np.degrees(np.arcsin(half_u))),
        float(np.degrees(np.arcsin(half_v))),
    )


def mark_rx_principal_region_uv(ax: Axes, rx_array: RxArray) -> None:
    """Mark the boresight-centered fundamental array-factor cell."""
    half_u, half_v = rx_principal_half_widths(rx_array)
    ax.add_patch(
        Rectangle(
            (-half_u, -half_v),
            2.0 * half_u,
            2.0 * half_v,
            fill=False,
            edgecolor="C3",
            linestyle="--",
            linewidth=1.1,
            label="RX principal-region edges",
            zorder=4,
        )
    )


def mark_rx_principal_cut_edges(ax: Axes, half_angle_deg: float) -> None:
    """Mark the fundamental array-factor interval in one principal cut."""
    ax.axvline(
        -half_angle_deg,
        color="C3",
        linewidth=1.1,
        linestyle="--",
        label="RX principal-region edges",
    )
    ax.axvline(
        half_angle_deg,
        color="C3",
        linewidth=1.1,
        linestyle="--",
    )


def rx_steering_grid(rx_array: RxArray) -> SteeringGrid:
    """Sample one periodic steering cell with primary and half-offset grids."""
    period_u, period_v = rx_array_factor_periods(rx_array)
    horizontal_count = int(np.ceil(period_u / RX_BEAM_SEPARATION_UV))
    vertical_count = int(np.ceil(period_v / RX_BEAM_SEPARATION_UV))
    separation_u = period_u / horizontal_count
    separation_v = period_v / vertical_count

    primary_u_axis = (
        np.arange(horizontal_count) - horizontal_count // 2
    ) * separation_u
    primary_v_axis = (np.arange(vertical_count) - vertical_count // 2) * separation_v
    primary_u, primary_v = np.meshgrid(primary_u_axis, primary_v_axis, indexing="ij")

    offset_u_axis = primary_u_axis + 0.5 * separation_u
    offset_v_axis = primary_v_axis + 0.5 * separation_v
    offset_u, offset_v = np.meshgrid(offset_u_axis, offset_v_axis, indexing="ij")

    primary_u_flat = np.asarray(primary_u.ravel(), dtype=float)
    primary_v_flat = np.asarray(primary_v.ravel(), dtype=float)
    return SteeringGrid(
        u=np.concatenate((primary_u_flat, offset_u.ravel())),
        v=np.concatenate((primary_v_flat, offset_v.ravel())),
        primary_count=primary_u_flat.size,
        primary_u_count=horizontal_count,
        primary_v_count=vertical_count,
        separation_u=separation_u,
        separation_v=separation_v,
        period_u=period_u,
        period_v=period_v,
    )


def form_rx_beams(
    boresight_array: UniformArrayAntenna,
) -> MultiBeamUniformArrayAntenna:
    """Form the periodic, interleaved best-beam RX envelope."""
    steering = rx_steering_grid(boresight_array)
    return MultiBeamUniformArrayAntenna(
        boresight_array.element,
        horizontal_count=boresight_array.horizontal_count,
        vertical_count=boresight_array.vertical_count,
        horizontal_spacing_m=boresight_array.horizontal_spacing_m,
        vertical_spacing_m=boresight_array.vertical_spacing_m,
        center_frequency_hz=boresight_array.center_frequency_hz,
        steering_u=steering.u,
        steering_v=steering.v,
    )


def lannik_psi(rx_layout: RxAntennaLayout = RX_LAYOUT) -> Product:
    """Build Lannik Psi with the proposed full-aperture TX model."""
    waveform = FmcwWaveform.from_slope(
        center_frequency_hz=CENTER_FREQUENCY_HZ,
        chirp_slope_hz_per_s=2.0e12,  # assumed; sets unambiguous range only
        sample_rate_hz=50.0e6,
        n_samples=1024,
        n_chirps=512,
    )
    tx_antenna = load_tx_antenna()
    rx_boresight_array = build_rx_antenna(rx_layout)
    rx_antenna = form_rx_beams(rx_boresight_array)
    radar = Radar(
        frontend=frontend.ctrx8188f(),
        waveform=waveform,
        processing=StandardProcessing(
            transmit_coherent=True,
            tx_array_gain_in_antenna=True,
            rx_combination=BeamCombination.COHERENT,
        ),
        antenna=AntennaPair(
            tx=tx_antenna,
            rx=rx_antenna,
            name="Lannik Psi proposed antenna",
        ),
        default_pfa=PFA,
    )
    return Product(
        name="Lannik Psi",
        radar=radar,
        waveform=waveform,
        front_end_note="CTRX8188F 8Tx/8Rx + modeled TX/RX apertures",
        waveform_note="1024 x 512 @ 50 MHz",
        processing_note=(
            f"full-aperture TX + best of {rx_antenna.beam_count} coherent RX beams"
        ),
    )


def evaluate(product: Product) -> AcquisitionSweep:
    """Run the baseline closing-target acquisition sweep."""
    approach = RadialApproach(
        initial_range_m=INITIAL_RANGE_M, closing_speed_mps=CLOSING_SPEED_MPS
    )
    return sweeps.acquisition_sweep(
        product.radar,
        TARGET,
        approach,
        frame_time_s=FRAME_TIME_S,
        confirm=CONFIRM,
    )


def outermost_range_at(
    range_m: npt.NDArray[np.float64],
    values: npt.NDArray[np.float64],
    level: float,
) -> float:
    """Largest range whose curve value reaches ``level`` (NaN if never)."""
    mask = values >= level
    if not bool(mask.any()):
        return float("nan")
    return float(range_m[mask].max())


def ranges_at_levels(
    range_m: npt.NDArray[np.float64],
    values: npt.NDArray[np.float64],
) -> dict[float, float]:
    """Outermost ranges at the configured detection-probability levels."""
    return {
        level: outermost_range_at(range_m, values, level) for level in DETECTION_LEVELS
    }


def format_range_m(range_m: float) -> str:
    """Format a range for reports, preserving unavailable values cleanly."""
    if not np.isfinite(range_m):
        return "n/a"
    return f"{range_m:.0f} m"


def format_level_ranges(level_ranges: dict[float, float]) -> str:
    """Format ``50% @ ...`` / ``90% @ ...`` legend text."""
    return ", ".join(
        f"{level:.0%} @ {format_range_m(level_ranges[level])}"
        for level in DETECTION_LEVELS
    )


def nice_ceiling(value: float) -> float:
    """Round a positive range up to a tidy axis limit."""
    if not np.isfinite(value) or value <= 0.0:
        return 50.0
    step = 50.0 if value <= 500.0 else 100.0 if value <= 2000.0 else 250.0
    return float(np.ceil(value / step) * step)


def print_diagnostics(product: Product, acq: AcquisitionSweep) -> None:
    """Print the baseline link/processing budget and detection ranges."""
    assert acq.confirmation_pd is not None
    waveform = product.waveform
    budget = product.radar.processing.budget(
        waveform, product.radar.frontend.n_tx, product.radar.frontend.n_rx
    )
    unambiguous_range_m = waveform.max_unambiguous_range_m

    print(product.name)
    print(f"  front-end / antenna : {product.front_end_note}")
    print(f"  waveform            : {product.waveform_note}")
    print(f"  processing          : {product.processing_note}")
    print(f"  coherent gain       : {budget.coherent_gain_db:6.1f} dB")
    print(
        f"  detector looks      : {budget.n_noncoherent} signal "
        f"+ {budget.n_collapsing} collapsing"
    )
    tx_antenna = product.radar.antenna.tx
    if isinstance(tx_antenna, RectangularArrayAntenna):
        print(
            f"  TX aperture          : {tx_antenna.excitations.shape[0]} x "
            f"{tx_antenna.excitations.shape[1]} radiators"
        )
        print(
            f"  TX array factor      : "
            f"{tx_antenna.array_factor_boresight_gain_db:6.1f} dB boresight"
        )
        print(f"  TX boresight gain    : {tx_antenna.boresight_gain_dbi:6.1f} dBi")
        print(
            f"  TX 3 dB beamwidth    : {tx_antenna.beamwidth_az_deg:4.1f} deg az x "
            f"{tx_antenna.beamwidth_el_deg:4.1f} deg el"
        )
    rx_antenna = product.radar.antenna.rx
    if isinstance(rx_antenna, MultiBeamUniformArrayAntenna):
        coherent_rx_gain_db = 10.0 * np.log10(rx_antenna.element_count)
        if isinstance(rx_antenna.element, UniformRectangularApertureAntenna):
            subarray = rx_antenna.element
            overall_width_m = (
                subarray.horizontal_extent_m
                + (rx_antenna.horizontal_count - 1) * rx_antenna.horizontal_spacing_m
            )
            overall_height_m = (
                subarray.vertical_extent_m
                + (rx_antenna.vertical_count - 1) * rx_antenna.vertical_spacing_m
            )
            print(
                f"  RX subarray extent   : {1e3 * subarray.horizontal_extent_m:4.1f} x "
                f"{1e3 * subarray.vertical_extent_m:4.1f} mm "
                f"({subarray.horizontal_extent_m / waveform.wavelength_m:4.2f} x "
                f"{subarray.vertical_extent_m / waveform.wavelength_m:4.2f} wavelengths)"
            )
        print(
            f"  RX channel array     : {rx_antenna.horizontal_count} x "
            f"{rx_antenna.vertical_count} subarrays"
        )
        if isinstance(rx_antenna.element, UniformRectangularApertureAntenna):
            print(
                f"  RX overall extent    : {1e3 * overall_width_m:4.1f} x "
                f"{1e3 * overall_height_m:4.1f} mm"
            )
        print(
            f"  RX channel spacing   : "
            f"{rx_antenna.horizontal_spacing_m / waveform.wavelength_m:4.2f} x "
            f"{rx_antenna.vertical_spacing_m / waveform.wavelength_m:4.2f} wavelengths"
        )
        print(f"  RX subarray gain     : {rx_antenna.boresight_gain_dbi:6.1f} dBi")
        print(
            f"  RX effective gain    : "
            f"{rx_antenna.boresight_gain_dbi + coherent_rx_gain_db:6.1f} dBi boresight"
        )
        print(
            f"  RX 3 dB beamwidth    : {rx_antenna.beamwidth_az_deg:4.1f} deg az x "
            f"{rx_antenna.beamwidth_el_deg:4.1f} deg el"
        )
        steering = rx_steering_grid(rx_antenna)
        half_u, half_v = rx_principal_half_widths(rx_antenna)
        principal_az_deg, principal_el_deg = rx_principal_cut_angles_deg(rx_antenna)
        print(
            f"  RX AF periods        : {steering.period_u:.4f} u x "
            f"{steering.period_v:.4f} v"
        )
        print(
            f"  RX principal region  : +/-{half_u:.4f} u x +/-{half_v:.4f} v "
            f"(+/-{principal_az_deg:.1f} deg az x "
            f"+/-{principal_el_deg:.1f} deg el)"
        )
        print(
            f"  RX formed beams      : {rx_antenna.beam_count} "
            f"({steering.primary_u_count} x {steering.primary_v_count} primary + "
            f"{steering.primary_u_count} x {steering.primary_v_count} offset)"
        )
        print(
            f"  RX beam separation   : {steering.separation_u:.4f} u x "
            f"{steering.separation_v:.4f} v "
            f"(~{np.degrees(np.arcsin(steering.separation_u)):.1f} deg at boresight)"
        )
    pd_ranges = ranges_at_levels(acq.range_m, acq.pd)
    pacq_ranges = ranges_at_levels(acq.range_m, acq.confirmation_pd)
    pd09 = pd_ranges[0.9]
    print(f"  range resolution    : {waveform.range_resolution_m:6.2f} m")
    print(f"  max unambig. range  : {unambiguous_range_m:6.0f} m")
    for level in DETECTION_LEVELS:
        print(
            f"  Pd {level:.0%} single scan : " f"{format_range_m(pd_ranges[level]):>7}"
        )
    for level in DETECTION_LEVELS:
        print(
            f"  Pacq {level:.0%} (2-of-3)  : "
            f"{format_range_m(pacq_ranges[level]):>7}"
        )
    if np.isfinite(pd09) and unambiguous_range_m < pd09:
        print(
            "  ** WARNING: unambiguous range is below the Pd=0.9 range; "
            "pick a gentler chirp slope."
        )


def plot_product(product: Product, acq: AcquisitionSweep, path: Path) -> None:
    """Plot single-scan Pd and 2-of-3 Pacq vs range and save to ``path``."""
    assert acq.confirmation_pd is not None
    pd_ranges = ranges_at_levels(acq.range_m, acq.pd)
    pacq_ranges = ranges_at_levels(acq.range_m, acq.confirmation_pd)

    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    ax.plot(
        acq.range_m,
        acq.pd,
        label=f"Pd single scan ({format_level_ranges(pd_ranges)})",
    )
    ax.plot(
        acq.range_m,
        acq.confirmation_pd,
        label=f"Pacq 2-of-3 ({format_level_ranges(pacq_ranges)})",
    )
    for level in DETECTION_LEVELS:
        ax.axhline(level, color="0.6", lw=0.8, ls=":")

    edge = outermost_range_at(acq.range_m, acq.pd, 0.02)
    xmax = nice_ceiling(edge * 1.1)
    ax.set_xlim(0.0, xmax)
    ax.set_ylim(0.0, 1.0)

    unambiguous_range_m = product.waveform.max_unambiguous_range_m
    if unambiguous_range_m <= xmax:
        ax.axvline(unambiguous_range_m, color="C3", lw=0.8, ls="--")
        ax.text(
            unambiguous_range_m,
            0.05,
            "max unambiguous range ",
            rotation=90,
            va="bottom",
            ha="right",
            fontsize=7,
            color="C3",
        )

    ax.set_xlabel("range [m]")
    ax.set_ylabel("probability")
    ax.set_title(
        f"{product.name}\n"
        f"{product.front_end_note}\n"
        f"{product.waveform_note}  |  {product.processing_note}",
        fontsize=9,
    )
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower left")
    fig.text(0.5, 0.005, SCENARIO_TEXT, ha="center", fontsize=8, color="0.3")
    fig.tight_layout(rect=(0.0, 0.03, 1.0, 1.0))
    fig.savefig(path, dpi=130)


def _relative_excitation_db(
    excitations: npt.NDArray[np.complex128],
) -> npt.NDArray[np.float64]:
    """Excitation voltage magnitude in dB relative to its maximum."""
    relative = np.abs(excitations) / float(np.max(np.abs(excitations)))
    return np.asarray(20.0 * np.log10(np.maximum(relative, 1.0e-30)), dtype=float)


def _plot_discrete_excitations(
    ax: Axes,
    horizontal: npt.NDArray[np.float64],
    vertical: npt.NDArray[np.float64],
    excitations: npt.NDArray[np.complex128],
    color_norm: Normalize,
    *,
    show_phase: bool,
) -> None:
    """Draw discrete excitation magnitudes and optional relative phasors."""
    relative_db = _relative_excitation_db(excitations)
    ax.scatter(
        horizontal,
        vertical,
        c=relative_db,
        norm=color_norm,
        cmap="viridis",
        s=62.0,
        edgecolors="0.2",
        linewidths=0.25,
        zorder=2,
    )
    if not show_phase:
        return

    boresight_phase = float(np.angle(np.sum(excitations)))
    relative_phase = np.angle(excitations * np.exp(-1.0j * boresight_phase))
    unique_horizontal = np.unique(horizontal)
    unique_vertical = np.unique(vertical)
    spacings = np.concatenate((np.diff(unique_horizontal), np.diff(unique_vertical)))
    phasor_length = 0.30 * float(np.min(spacings))
    ax.quiver(
        horizontal,
        vertical,
        phasor_length * np.cos(relative_phase),
        phasor_length * np.sin(relative_phase),
        angles="xy",
        scale_units="xy",
        scale=1.0,
        pivot="middle",
        color="white",
        edgecolor="black",
        linewidth=0.3,
        width=0.004,
        headwidth=3.5,
        headlength=4.0,
        headaxislength=3.5,
        zorder=3,
    )


def _center_axis(count: int, spacing_wavelengths: float) -> npt.NDArray[np.float64]:
    """Centered uniform channel coordinates in wavelengths."""
    return np.asarray(
        (np.arange(count, dtype=float) - 0.5 * (count - 1)) * spacing_wavelengths,
        dtype=float,
    )


def plot_antenna_geometry(
    tx_antenna: RectangularArrayAntenna,
    rx_antenna: MultiBeamUniformArrayAntenna,
    path: Path,
) -> None:
    """Plot the modeled TX excitations and RX subarray/channel geometry."""
    wavelength_m = SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ
    color_norm = Normalize(vmin=-30.0, vmax=0.0)
    fig, (tx_ax, rx_ax) = plt.subplots(1, 2, figsize=(12.5, 5.8))

    tx_horizontal, tx_vertical = np.meshgrid(
        tx_antenna.horizontal_positions_m / wavelength_m,
        tx_antenna.vertical_positions_m / wavelength_m,
        indexing="ij",
    )
    _plot_discrete_excitations(
        tx_ax,
        np.asarray(tx_horizontal.ravel(), dtype=float),
        np.asarray(tx_vertical.ravel(), dtype=float),
        np.asarray(tx_antenna.excitations.ravel(), dtype=np.complex128),
        color_norm,
        show_phase=True,
    )
    tx_ax.set_title(
        f"TX: {tx_antenna.excitations.shape[0]} × "
        f"{tx_antenna.excitations.shape[1]} discrete radiators"
    )

    rx_horizontal_spacing = rx_antenna.horizontal_spacing_m / wavelength_m
    rx_vertical_spacing = rx_antenna.vertical_spacing_m / wavelength_m
    rx_centers_horizontal = _center_axis(
        rx_antenna.horizontal_count, rx_horizontal_spacing
    )
    rx_centers_vertical = _center_axis(rx_antenna.vertical_count, rx_vertical_spacing)
    rx_center_horizontal, rx_center_vertical = np.meshgrid(
        rx_centers_horizontal, rx_centers_vertical, indexing="ij"
    )

    if isinstance(rx_antenna.element, UniformRectangularApertureAntenna):
        subarray_width = rx_antenna.element.horizontal_extent_m / wavelength_m
        subarray_height = rx_antenna.element.vertical_extent_m / wavelength_m
        uniform_color = plt.get_cmap("viridis")(color_norm(0.0))
        for center_horizontal, center_vertical in zip(
            rx_center_horizontal.ravel(),
            rx_center_vertical.ravel(),
            strict=True,
        ):
            rx_ax.add_patch(
                Rectangle(
                    (
                        center_horizontal - 0.5 * subarray_width,
                        center_vertical - 0.5 * subarray_height,
                    ),
                    subarray_width,
                    subarray_height,
                    facecolor=uniform_color,
                    edgecolor="0.25",
                    linewidth=1.0,
                )
            )
        rx_description = (
            f"uniform {subarray_width:.2f}λ × {subarray_height:.2f}λ subarrays"
        )
    elif isinstance(rx_antenna.element, RectangularArrayAntenna):
        element = rx_antenna.element
        relative_horizontal = (
            element.horizontal_positions_m
            - float(np.mean(element.horizontal_positions_m))
        ) / wavelength_m
        relative_vertical = (
            element.vertical_positions_m - float(np.mean(element.vertical_positions_m))
        ) / wavelength_m
        point_horizontal, point_vertical = np.meshgrid(
            relative_horizontal, relative_vertical, indexing="ij"
        )
        horizontal_pitch = float(np.diff(relative_horizontal)[0])
        vertical_pitch = float(np.diff(relative_vertical)[0])
        subarray_width = relative_horizontal.size * horizontal_pitch
        subarray_height = relative_vertical.size * vertical_pitch
        for center_horizontal, center_vertical in zip(
            rx_center_horizontal.ravel(),
            rx_center_vertical.ravel(),
            strict=True,
        ):
            rx_ax.add_patch(
                Rectangle(
                    (
                        center_horizontal - 0.5 * subarray_width,
                        center_vertical - 0.5 * subarray_height,
                    ),
                    subarray_width,
                    subarray_height,
                    facecolor="none",
                    edgecolor="0.35",
                    linewidth=0.8,
                )
            )
            _plot_discrete_excitations(
                rx_ax,
                np.asarray(point_horizontal.ravel() + center_horizontal, dtype=float),
                np.asarray(point_vertical.ravel() + center_vertical, dtype=float),
                np.asarray(element.excitations.ravel(), dtype=np.complex128),
                color_norm,
                show_phase=True,
            )
        rx_description = (
            f"{relative_horizontal.size} × {relative_vertical.size} "
            "discrete radiators per subarray"
        )
    else:
        subarray_width = rx_horizontal_spacing
        subarray_height = rx_vertical_spacing
        rx_description = "subarray pattern not geometrically resolved"

    rx_ax.scatter(
        rx_center_horizontal,
        rx_center_vertical,
        s=45.0,
        facecolors="white",
        edgecolors="black",
        linewidths=1.3,
        label="channel phase centers",
        zorder=5,
    )
    rx_ax.set_xlim(
        float(np.min(rx_centers_horizontal) - 0.65 * subarray_width),
        float(np.max(rx_centers_horizontal) + 0.65 * subarray_width),
    )
    rx_ax.set_ylim(
        float(np.min(rx_centers_vertical) - 0.65 * subarray_height),
        float(np.max(rx_centers_vertical) + 0.65 * subarray_height),
    )
    rx_ax.set_title(
        f"RX: {rx_antenna.horizontal_count} × {rx_antenna.vertical_count} channels\n"
        f"{rx_description}"
    )
    rx_ax.legend(loc="upper right", fontsize=8)

    for axis in (tx_ax, rx_ax):
        axis.set_xlabel("horizontal aperture coordinate / λ (u axis)")
        axis.set_ylabel("vertical aperture coordinate / λ (v axis)")
        axis.set_aspect("equal")
        axis.grid(True, alpha=0.2)

    scalar_mappable = plt.cm.ScalarMappable(norm=color_norm, cmap="viridis")
    colorbar_ax = fig.add_axes((0.31, 0.13, 0.38, 0.035))
    fig.colorbar(
        scalar_mappable,
        cax=colorbar_ax,
        orientation="horizontal",
        label="excitation voltage magnitude [dB relative to maximum]",
    )
    fig.suptitle("Lannik Psi modeled TX and RX antenna geometries", fontsize=14)
    fig.text(
        0.5,
        0.025,
        "TX arrow direction: excitation phase relative to the coherent boresight "
        "sum | RX white circles: channel phase centers | local aperture coordinates",
        ha="center",
        fontsize=8,
        color="0.3",
    )
    fig.subplots_adjust(left=0.07, right=0.98, bottom=0.27, top=0.84, wspace=0.24)
    fig.savefig(path, dpi=150)
    print(f"  saved {path}")


def plot_antenna_patterns(
    antenna_model: Antenna,
    directory: Path,
    *,
    filename_prefix: str,
    title: str,
    effective_peak_gain_dbi: float,
    beamwidth_label: str = "3 dB BW",
    principal_region_rx: RxArray | None = None,
) -> None:
    """Save one antenna beam's u/v map and horizontal/vertical cuts."""
    uv_path = directory / f"{filename_prefix}_uv.png"
    fig_uv, ax_uv = plt.subplots(figsize=(6.4, 5.2))
    plot_pattern_uv(
        antenna_model,
        ax=ax_uv,
        relative=True,
        dynamic_range_db=50.0,
    )
    ax_uv.set_title(
        f"{title} at {CENTER_FREQUENCY_HZ / 1e9:.1f} GHz\n"
        f"effective peak {effective_peak_gain_dbi:.1f} dBi"
    )
    if principal_region_rx is not None:
        mark_rx_principal_region_uv(ax_uv, principal_region_rx)
        ax_uv.legend(loc="upper right", fontsize=8)
    fig_uv.tight_layout()
    fig_uv.savefig(uv_path, dpi=150)
    print(f"  saved {uv_path}")

    cuts_path = directory / f"{filename_prefix}_cuts.png"
    angles_deg = np.linspace(-90.0, 90.0, 1801)
    ax_az, ax_el = plot_pattern_cuts(
        antenna_model,
        angles_deg=angles_deg,
        relative=True,
    )
    for axis in (ax_az, ax_el):
        axis.set_xlim(-90.0, 90.0)
        axis.set_ylim(-70.0, 2.0)
    if principal_region_rx is not None:
        principal_az_deg, principal_el_deg = rx_principal_cut_angles_deg(
            principal_region_rx
        )
        mark_rx_principal_cut_edges(ax_az, principal_az_deg)
        mark_rx_principal_cut_edges(ax_el, principal_el_deg)
        ax_az.legend(loc="lower center", fontsize=8)
        ax_el.legend(loc="lower center", fontsize=8)
    ax_az.set_title(
        f"horizontal (u) cut, {beamwidth_label} "
        f"{antenna_model.beamwidth_az_deg:.1f}°"
    )
    ax_el.set_title(
        f"vertical (v) cut, {beamwidth_label} " f"{antenna_model.beamwidth_el_deg:.1f}°"
    )
    cuts_figure = plt.gcf()
    cuts_figure.suptitle(f"{title} at {CENTER_FREQUENCY_HZ / 1e9:.1f} GHz")
    cuts_figure.tight_layout()
    cuts_figure.savefig(cuts_path, dpi=150)
    print(f"  saved {cuts_path}")


def _angles_from_uv(
    u: npt.NDArray[np.float64], v: npt.NDArray[np.float64]
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Convert visible direction-cosine arrays to azimuth/elevation."""
    elevation_deg = np.degrees(np.arcsin(v))
    cos_elevation = np.sqrt(np.maximum(1.0 - v**2, 0.0))
    sin_azimuth = np.zeros_like(u)
    np.divide(u, cos_elevation, out=sin_azimuth, where=cos_elevation > 0.0)
    azimuth_deg = np.degrees(np.arcsin(np.clip(sin_azimuth, -1.0, 1.0)))
    return azimuth_deg, elevation_deg


def _rx_beam_detail_axis(
    rx_antenna: MultiBeamUniformArrayAntenna,
) -> npt.NDArray[np.float64]:
    """Common detailed u/v axis spanning the principal cell plus one grid cell."""
    steering = rx_steering_grid(rx_antenna)
    half_u, half_v = rx_principal_half_widths(rx_antenna)
    plot_limit = max(half_u, half_v) + max(steering.separation_u, steering.separation_v)
    return np.linspace(-plot_limit, plot_limit, 401)


def plot_rx_beam_grid(
    rx_antenna: MultiBeamUniformArrayAntenna,
    directory: Path,
) -> None:
    """Plot the periodic steering grid and straddling loss in one principal cell."""
    steering = rx_steering_grid(rx_antenna)
    half_u, half_v = rx_principal_half_widths(rx_antenna)
    u_axis = np.linspace(
        -half_u - 0.5 * steering.separation_u,
        half_u + 0.5 * steering.separation_u,
        401,
    )
    v_axis = np.linspace(
        -half_v - 0.5 * steering.separation_v,
        half_v + 0.5 * steering.separation_v,
        241,
    )
    u_grid, v_grid = np.meshgrid(u_axis, v_axis, indexing="ij")
    azimuth_deg, elevation_deg = _angles_from_uv(u_grid, v_grid)
    rx_gain = np.asarray(rx_antenna.gain_dbi(azimuth_deg, elevation_deg), dtype=float)
    element_gain = np.asarray(
        rx_antenna.element.gain_dbi(azimuth_deg, elevation_deg), dtype=float
    )
    straddling_loss_db = rx_gain - element_gain
    inside_principal = (np.abs(u_grid) <= half_u) & (np.abs(v_grid) <= half_v)
    displayed_loss_db = np.where(inside_principal, straddling_loss_db, np.nan)

    path = directory / "rx_multibeam_grid_uv.png"
    fig, ax = plt.subplots(figsize=(6.5, 5.4))
    mesh = ax.pcolormesh(
        u_axis,
        v_axis,
        displayed_loss_db.T,
        shading="auto",
        vmin=-2.0,
        vmax=0.0,
        cmap="viridis",
    )
    ax.scatter(
        steering.u[: steering.primary_count],
        steering.v[: steering.primary_count],
        s=18,
        facecolors="none",
        edgecolors="C3",
        linewidths=1.0,
        label="primary grid",
    )
    ax.scatter(
        steering.u[steering.primary_count :],
        steering.v[steering.primary_count :],
        s=13,
        color="black",
        marker="x",
        linewidths=0.8,
        label="half-cell offset grid",
    )
    mark_rx_principal_region_uv(ax, rx_antenna)
    ax.set_xlabel("u [-]")
    ax.set_ylabel("v [-]")
    ax.set_aspect("equal")
    ax.set_title(
        f"Lannik Psi RX best-beam straddling loss\n"
        f"one periodic principal region, {rx_antenna.beam_count} beams"
    )
    ax.legend(loc="upper right", fontsize=8)
    fig.colorbar(mesh, ax=ax, label="RX array-factor loss [dB]")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"  saved {path}")

    worst_loss_db = float(np.min(straddling_loss_db[inside_principal]))
    range_loss_percent = 100.0 * (1.0 - 10.0 ** (worst_loss_db / 40.0))
    print(
        f"  worst RX straddling  : {worst_loss_db:.2f} dB over one principal "
        f"region ({range_loss_percent:.1f}% range loss)"
    )


def plot_two_way_patterns(
    tx_antenna: RectangularArrayAntenna,
    rx_antenna: MultiBeamUniformArrayAntenna,
    directory: Path,
) -> None:
    """Save max-over-RX-beams two-way u/v and principal-cut patterns."""
    uv_path = directory / "two_way_multibeam_max_uv.png"
    fig_uv, ax_uv = plt.subplots(figsize=(6.4, 5.2))
    plot_pattern_uv(
        tx_antenna,
        rx_antenna,
        ax=ax_uv,
        relative=True,
        two_way=True,
        dynamic_range_db=70.0,
    )
    ax_uv.set_title(
        f"Lannik Psi two-way pattern, best of {rx_antenna.beam_count} RX beams\n"
        "relative to boresight"
    )
    mark_rx_principal_region_uv(ax_uv, rx_antenna)
    ax_uv.legend(loc="upper right", fontsize=8)
    fig_uv.tight_layout()
    fig_uv.savefig(uv_path, dpi=150)
    print(f"  saved {uv_path}")

    detail_path = directory / "two_way_multibeam_detail_uv.png"
    detail_axis = _rx_beam_detail_axis(rx_antenna)
    fig_detail, ax_detail = plt.subplots(figsize=(6.5, 5.4))
    plot_pattern_uv(
        tx_antenna,
        rx_antenna,
        u=detail_axis,
        v=detail_axis,
        ax=ax_detail,
        relative=True,
        two_way=True,
        dynamic_range_db=12.0,
    )
    ax_detail.scatter(
        rx_antenna.steering_u,
        rx_antenna.steering_v,
        s=10,
        color="black",
        linewidths=0.0,
        label="RX beam centers",
        zorder=3,
    )
    mark_rx_principal_region_uv(ax_detail, rx_antenna)
    ax_detail.set_title(
        f"Lannik Psi detailed two-way pattern\n"
        f"TX plus best of {rx_antenna.beam_count} RX beams"
    )
    ax_detail.legend(loc="upper right", fontsize=8)
    fig_detail.tight_layout()
    fig_detail.savefig(detail_path, dpi=150)
    print(f"  saved {detail_path}")

    cuts_path = directory / "two_way_multibeam_max_cuts.png"
    angles_deg = np.linspace(-90.0, 90.0, 1801)
    ax_az, ax_el = plot_pattern_cuts(
        tx_antenna,
        rx_antenna,
        angles_deg=angles_deg,
        relative=True,
        two_way=True,
    )
    for axis in (ax_az, ax_el):
        axis.set_xlim(-30.0, 30.0)
        axis.set_ylim(-70.0, 2.0)
    principal_az_deg, principal_el_deg = rx_principal_cut_angles_deg(rx_antenna)
    mark_rx_principal_cut_edges(ax_az, principal_az_deg)
    mark_rx_principal_cut_edges(ax_el, principal_el_deg)
    ax_az.legend(loc="lower center", fontsize=8)
    ax_el.legend(loc="lower center", fontsize=8)
    figure = plt.gcf()
    figure.suptitle(
        f"Lannik Psi two-way pattern, best of {rx_antenna.beam_count} RX beams"
    )
    figure.tight_layout()
    figure.savefig(cuts_path, dpi=150)
    print(f"  saved {cuts_path}")

    contribution_path = directory / "tx_rx_multibeam_max_cuts.png"
    contribution_angles_deg = np.linspace(-30.0, 30.0, 1201)
    zeros = np.zeros_like(contribution_angles_deg)
    tx_boresight_dbi = float(tx_antenna.gain_dbi(0.0, 0.0))
    rx_boresight_dbi = float(rx_antenna.gain_dbi(0.0, 0.0))
    tx_cuts = (
        np.asarray(tx_antenna.gain_dbi(contribution_angles_deg, zeros), dtype=float)
        - tx_boresight_dbi,
        np.asarray(tx_antenna.gain_dbi(zeros, contribution_angles_deg), dtype=float)
        - tx_boresight_dbi,
    )
    rx_cuts = (
        np.asarray(rx_antenna.gain_dbi(contribution_angles_deg, zeros), dtype=float)
        - rx_boresight_dbi,
        np.asarray(rx_antenna.gain_dbi(zeros, contribution_angles_deg), dtype=float)
        - rx_boresight_dbi,
    )

    contribution_figure, contribution_axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    for axis, axis_name, tx_cut, rx_cut, principal_edge_deg in zip(
        contribution_axes,
        ("azimuth", "elevation"),
        tx_cuts,
        rx_cuts,
        (principal_az_deg, principal_el_deg),
    ):
        axis.plot(contribution_angles_deg, tx_cut, color="C1", label="TX")
        axis.plot(
            contribution_angles_deg,
            rx_cut,
            color="C0",
            label=f"RX: best of {rx_antenna.beam_count} beams",
        )
        axis.set_xlim(-30.0, 30.0)
        axis.set_ylim(-40.0, 2.0)
        axis.set_xlabel(f"{axis_name} [deg]")
        axis.set_ylabel("relative one-way gain [dB]")
        axis.set_title(f"{axis_name} cut")
        axis.grid(True, alpha=0.3)
        mark_rx_principal_cut_edges(axis, principal_edge_deg)
        axis.legend(fontsize=8)
    contribution_figure.suptitle("Lannik Psi TX and RX pattern contributions")
    contribution_figure.text(
        0.5,
        0.015,
        "Each contribution is relative to its own boresight gain; "
        "their dB sum is the relative two-way gain",
        ha="center",
        fontsize=8,
        color="0.3",
    )
    contribution_figure.tight_layout(rect=(0.0, 0.06, 1.0, 1.0))
    contribution_figure.savefig(contribution_path, dpi=150)
    print(f"  saved {contribution_path}")


def plot_multibeam_range_cuts(
    product: Product,
    tx_antenna: RectangularArrayAntenna,
    rx_antenna: MultiBeamUniformArrayAntenna,
    directory: Path,
) -> None:
    """Show Pd=90% range and discrete-beam ripple on the principal cuts."""
    boresight_range_m = sweeps.coverage_range(
        product.radar,
        TARGET,
        0.9,
        max_range_m=2500.0,
        n_samples=2000,
    )
    principal_az_deg, principal_el_deg = rx_principal_cut_angles_deg(rx_antenna)
    angle_limit_deg = 1.2 * max(principal_az_deg, principal_el_deg)
    angles_deg = np.linspace(-angle_limit_deg, angle_limit_deg, 1801)
    zeros = np.zeros_like(angles_deg)
    tx_az = np.asarray(tx_antenna.gain_dbi(angles_deg, zeros), dtype=float)
    tx_el = np.asarray(tx_antenna.gain_dbi(zeros, angles_deg), dtype=float)
    rx_az = np.asarray(rx_antenna.gain_dbi(angles_deg, zeros), dtype=float)
    rx_el = np.asarray(rx_antenna.gain_dbi(zeros, angles_deg), dtype=float)
    ideal_rx_az = np.asarray(
        rx_antenna.element.gain_dbi(angles_deg, zeros), dtype=float
    )
    ideal_rx_el = np.asarray(
        rx_antenna.element.gain_dbi(zeros, angles_deg), dtype=float
    )
    boresight_two_way_gain = float(
        tx_antenna.gain_dbi(0.0, 0.0) + rx_antenna.gain_dbi(0.0, 0.0)
    )

    def range_from_gain(gain_dbi: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        return np.asarray(
            boresight_range_m * 10.0 ** ((gain_dbi - boresight_two_way_gain) / 40.0),
            dtype=float,
        )

    ranges = (
        range_from_gain(tx_az + rx_az),
        range_from_gain(tx_el + rx_el),
    )
    ideal_ranges = (
        range_from_gain(tx_az + ideal_rx_az),
        range_from_gain(tx_el + ideal_rx_el),
    )

    path = directory / "multibeam_pd90_range_cuts.png"
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.0), sharex="col")
    for column, (axis_name, actual, ideal, principal_edge_deg) in enumerate(
        (
            ("azimuth", ranges[0], ideal_ranges[0], principal_az_deg),
            ("elevation", ranges[1], ideal_ranges[1], principal_el_deg),
        )
    ):
        top = axes[0, column]
        bottom = axes[1, column]
        top.plot(angles_deg, ideal, color="0.45", ls="--", label="continuous steering")
        top.plot(
            angles_deg,
            actual,
            color="C0",
            label=f"{rx_antenna.beam_count}-beam envelope",
        )
        top.set_title(f"{axis_name} cut")
        top.set_ylabel("Pd=90% range [m]")
        top.grid(True, alpha=0.3)
        mark_rx_principal_cut_edges(top, principal_edge_deg)
        top.legend(fontsize=8)
        range_loss_percent = 100.0 * (1.0 - actual / ideal)
        bottom.plot(angles_deg, range_loss_percent, color="C3")
        bottom.set_xlabel(f"{axis_name} [deg]")
        bottom.set_ylabel("range loss vs ideal\ncontinuous steering [%]")
        bottom.grid(True, alpha=0.3)
        mark_rx_principal_cut_edges(bottom, principal_edge_deg)
    fig.suptitle("Lannik Psi multi-beam range envelope")
    assumptions_text = (
        "Assumptions: 1 m² RCS, Swerling 1 | single-scan Pd=90%, Pfa=1e-6 | "
        "free space; no clutter or phase noise\n"
        f"RX: ideal coherent best of {rx_antenna.beam_count} beams | "
        "periodic principal-cell grid plus half-cell offset | "
        "ideal bound: RX steered exactly to each look direction"
    )
    fig.text(0.5, 0.012, assumptions_text, ha="center", fontsize=8, color="0.3")
    fig.tight_layout(rect=(0.0, 0.085, 1.0, 1.0))
    fig.savefig(path, dpi=150)
    print(f"  saved {path}")


def _coverage_cut_angles(
    cut: CoverageCut, angle_deg: npt.NDArray[np.float64]
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Convert signed off-boresight angles in one cut to azimuth/elevation."""
    zeros = np.zeros_like(angle_deg)
    if cut.name == "horizontal":
        return angle_deg, zeros
    if cut.name == "vertical":
        return zeros, angle_deg
    direction_cosine = np.sin(np.radians(angle_deg)) / np.sqrt(2.0)
    return _angles_from_uv(direction_cosine, direction_cosine)


def _coverage_principal_angle_deg(cut: CoverageCut, rx_array: RxArray) -> float:
    """Return the centered principal-region edge in one coverage plane."""
    half_u, half_v = rx_principal_half_widths(rx_array)
    if cut.name == "horizontal":
        limiting_direction_cosine = half_u
    elif cut.name == "vertical":
        limiting_direction_cosine = half_v
    else:
        limiting_direction_cosine = np.sqrt(2.0) * min(half_u, half_v)
    return float(np.degrees(np.arcsin(limiting_direction_cosine)))


def compute_pd_coverage_maps(
    product: Product,
    rx_antenna: MultiBeamUniformArrayAntenna,
    cut: CoverageCut,
) -> tuple[Map2D, Map2D, float]:
    """Compute polar and physical-Cartesian single-scan Pd maps for one cut.

    The study has constant RCS, free space and no clutter, so its SINR separates
    exactly into a ``-40 log10(range)`` term and a direction-only two-way gain
    term. Evaluating the periodic best-beam pattern once on a fine angular grid
    and then interpolating it avoids repeating the same beam calculation at
    every 2-D range/position cell.
    """
    maximum_range_m = min(
        PD_MAP_RANGE_LIMIT_M, product.waveform.max_unambiguous_range_m
    )
    minimum_range_m = max(5.0, product.waveform.range_resolution_m)
    baseline_rx = product.radar.antenna.rx
    if not isinstance(baseline_rx, MultiBeamUniformArrayAntenna):
        raise TypeError("Lannik Psi RX must be a MultiBeamUniformArrayAntenna")
    detail_axis = _rx_beam_detail_axis(baseline_rx)
    angle_limit_deg = float(np.degrees(np.arcsin(float(np.max(np.abs(detail_axis))))))

    gain_angles_deg = np.linspace(-90.0, 90.0, 7201)
    gain_azimuth_deg, gain_elevation_deg = _coverage_cut_angles(cut, gain_angles_deg)
    tx_antenna = product.radar.antenna.tx
    two_way_gain_db = np.asarray(
        tx_antenna.gain_dbi(gain_azimuth_deg, gain_elevation_deg), dtype=float
    ) + np.asarray(
        rx_antenna.gain_dbi(gain_azimuth_deg, gain_elevation_deg), dtype=float
    )
    boresight_index = int(np.argmin(np.abs(gain_angles_deg)))
    relative_gain_db = two_way_gain_db - two_way_gain_db[boresight_index]

    reference_range_m = 100.0
    reference_sinr_db = product.radar.link_budget(
        TARGET, Geometry(range_m=reference_range_m)
    ).sinr_db
    processing_budget = product.radar.processing.budget(
        product.waveform,
        product.radar.frontend.n_tx,
        product.radar.frontend.n_rx,
    )

    def pd_from_sinr(sinr_db: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        return np.asarray(
            probability_of_detection(
                sinr_db,
                PFA,
                swerling=TARGET.swerling,
                n_pulses=processing_budget.n_noncoherent,
                n_collapsing=processing_budget.n_collapsing,
            ),
            dtype=float,
        )

    ranges_m = np.linspace(minimum_range_m, maximum_range_m, PD_MAP_RANGE_SAMPLES)
    angles_deg = np.linspace(-angle_limit_deg, angle_limit_deg, PD_MAP_ANGLE_SAMPLES)
    polar_relative_gain_db = np.interp(angles_deg, gain_angles_deg, relative_gain_db)
    polar_sinr_db = (
        reference_sinr_db
        - 40.0 * np.log10(ranges_m[:, None] / reference_range_m)
        + polar_relative_gain_db[None, :]
    )
    polar_map = Map2D(
        coord1=ranges_m,
        coord2=angles_deg,
        pd=pd_from_sinr(polar_sinr_db),
        sinr_db=polar_sinr_db,
    )

    downranges_m = np.linspace(minimum_range_m, maximum_range_m, PD_MAP_RANGE_SAMPLES)
    transverse_m = np.linspace(
        -PD_MAP_TRANSVERSE_LIMIT_M,
        PD_MAP_TRANSVERSE_LIMIT_M,
        PD_MAP_TRANSVERSE_SAMPLES,
    )
    downrange_grid, transverse_grid = np.meshgrid(
        downranges_m, transverse_m, indexing="ij"
    )
    slant_range_m = np.hypot(downrange_grid, transverse_grid)
    cartesian_angle_deg = np.degrees(np.arctan2(transverse_grid, downrange_grid))
    cartesian_relative_gain_db = np.interp(
        cartesian_angle_deg, gain_angles_deg, relative_gain_db
    )
    cartesian_sinr_db = (
        reference_sinr_db
        - 40.0 * np.log10(slant_range_m / reference_range_m)
        + cartesian_relative_gain_db
    )
    cartesian_map = Map2D(
        coord1=downranges_m,
        coord2=transverse_m,
        pd=pd_from_sinr(cartesian_sinr_db),
        sinr_db=cartesian_sinr_db,
    )
    return polar_map, cartesian_map, angle_limit_deg


def plot_pd_coverage_cut(
    product: Product,
    rx_antenna: MultiBeamUniformArrayAntenna,
    cut: CoverageCut,
    directory: Path,
) -> None:
    """Save paired polar and Cartesian static-Pd coverage views for one cut."""
    polar_map, cartesian_map, angle_limit_deg = compute_pd_coverage_maps(
        product, rx_antenna, cut
    )
    principal_angle_deg = _coverage_principal_angle_deg(cut, rx_antenna)

    fig = plt.figure(figsize=(13.0, 6.2))
    grid = fig.add_gridspec(
        1,
        2,
        left=0.06,
        right=0.97,
        bottom=0.18,
        top=0.82,
        wspace=0.20,
    )
    polar_ax = cast(PolarAxes, fig.add_subplot(grid[0, 0], projection="polar"))
    cartesian_ax = fig.add_subplot(grid[0, 1])

    theta_rad = np.radians(polar_map.coord2)
    polar_mesh = polar_ax.pcolormesh(
        theta_rad,
        polar_map.coord1,
        polar_map.pd,
        shading="auto",
        vmin=0.0,
        vmax=1.0,
        cmap="viridis",
    )
    polar_ax.contour(
        theta_rad,
        polar_map.coord1,
        polar_map.pd,
        levels=PD_MAP_LEVELS,
        colors=("white", "black"),
        linestyles=("--", "-"),
        linewidths=1.1,
    )
    polar_ax.set_theta_zero_location("E")
    polar_ax.set_theta_direction(1)
    polar_ax.set_thetamin(-angle_limit_deg)
    polar_ax.set_thetamax(angle_limit_deg)
    polar_ax.set_ylim(0.0, float(polar_map.coord1[-1]))
    polar_ax.set_rlabel_position(0.75 * angle_limit_deg)
    polar_ax.set_title("Polar: slant range and signed look angle", pad=16.0)
    for signed_angle_deg in (-principal_angle_deg, principal_angle_deg):
        signed_angle_rad = np.radians(signed_angle_deg)
        polar_ax.plot(
            (signed_angle_rad, signed_angle_rad),
            (0.0, float(polar_map.coord1[-1])),
            color="C3",
            linestyle="--",
            linewidth=1.1,
        )

    downrange_grid, transverse_grid = np.meshgrid(
        cartesian_map.coord1, cartesian_map.coord2, indexing="ij"
    )
    within_unambiguous_range = (
        np.hypot(downrange_grid, transverse_grid)
        <= product.waveform.max_unambiguous_range_m
    )
    cartesian_pd = np.where(within_unambiguous_range, cartesian_map.pd, np.nan)
    cartesian_ax.pcolormesh(
        cartesian_map.coord1,
        cartesian_map.coord2,
        cartesian_pd.T,
        shading="auto",
        vmin=0.0,
        vmax=1.0,
        cmap="viridis",
    )
    cartesian_ax.contour(
        cartesian_map.coord1,
        cartesian_map.coord2,
        cartesian_pd.T,
        levels=PD_MAP_LEVELS,
        colors=("white", "black"),
        linestyles=("--", "-"),
        linewidths=1.1,
    )
    cartesian_ax.set_facecolor("0.85")
    cartesian_ax.set_xlabel("downrange x [m]")
    cartesian_ax.set_ylabel(cut.transverse_label)
    cartesian_ax.set_title("Cartesian position (axis scales differ)")
    cartesian_ax.grid(True, alpha=0.2)
    principal_offset_m = cartesian_map.coord1 * np.tan(np.radians(principal_angle_deg))
    cartesian_ax.plot(
        cartesian_map.coord1,
        principal_offset_m,
        color="C3",
        linestyle="--",
        linewidth=1.1,
        label="RX principal-region edges",
    )
    cartesian_ax.plot(
        cartesian_map.coord1,
        -principal_offset_m,
        color="C3",
        linestyle="--",
        linewidth=1.1,
    )
    cartesian_ax.set_ylim(
        -PD_MAP_TRANSVERSE_LIMIT_M,
        PD_MAP_TRANSVERSE_LIMIT_M,
    )
    cartesian_ax.legend(loc="upper right", fontsize=8)

    colorbar_ax = polar_ax.inset_axes((0.18, 0.07, 0.64, 0.045))
    fig.colorbar(
        polar_mesh,
        cax=colorbar_ax,
        orientation="horizontal",
        label="single-scan Pd",
    )
    fig.suptitle(
        f"Lannik Psi single-scan Pd coverage — {cut.title}\n"
        "filled Pd with 50% dashed and 90% solid contours",
        fontsize=13,
    )
    assumptions_text = (
        "Assumptions: 1 m² RCS, Swerling 1 | Pfa=1e-6 | free space; "
        f"no clutter or phase noise | display limited to {PD_MAP_RANGE_LIMIT_M:.0f} m\n"
        f"{product.front_end_note} | {product.waveform_note} | "
        f"ideal coherent best of {rx_antenna.beam_count} periodic RX beams\n"
        f"RX principal edges: ±{principal_angle_deg:.1f}° in this cut | "
        f"effective boresight gain "
        f"{rx_antenna.boresight_gain_dbi + 10.0 * np.log10(rx_antenna.element_count):.1f} dBi"
    )
    if isinstance(rx_antenna.element, UniformRectangularApertureAntenna):
        wavelength_m = SPEED_OF_LIGHT / rx_antenna.center_frequency_hz
        assumptions_text += (
            f" | uniform subarray "
            f"{rx_antenna.element.horizontal_extent_m / wavelength_m:.2f}λ × "
            f"{rx_antenna.element.vertical_extent_m / wavelength_m:.2f}λ "
            f"({1e3 * rx_antenna.element.horizontal_extent_m:.2f} × "
            f"{1e3 * rx_antenna.element.vertical_extent_m:.2f} mm)"
        )
    fig.text(0.5, 0.035, assumptions_text, ha="center", fontsize=8, color="0.3")

    path = directory / f"pd_coverage_{cut.name}.png"
    fig.savefig(path, dpi=150)
    print(f"  saved {path}")


def main() -> None:
    product = lannik_psi()
    generated_dir = Path(__file__).parent / "generated"
    generated_dir.mkdir(exist_ok=True)

    print(f"Scenario: {SCENARIO_TEXT}")
    print(f"Initial range: {INITIAL_RANGE_M:.0f} m\n")

    acquisition = evaluate(product)
    print_diagnostics(product, acquisition)
    path = generated_dir / "pd_pacq_vs_range.png"
    plot_product(product, acquisition, path)
    print(f"\n  saved {path}")
    tx_antenna = product.radar.antenna.tx
    if not isinstance(tx_antenna, RectangularArrayAntenna):
        raise TypeError("Lannik Psi TX must be a RectangularArrayAntenna")
    plot_antenna_patterns(
        tx_antenna,
        generated_dir,
        filename_prefix="tx_sum_beam",
        title="Lannik Psi TX sum beam",
        effective_peak_gain_dbi=tx_antenna.boresight_gain_dbi,
    )
    rx_antenna = product.radar.antenna.rx
    if not isinstance(rx_antenna, MultiBeamUniformArrayAntenna):
        raise TypeError("Lannik Psi RX must be a MultiBeamUniformArrayAntenna")
    plot_antenna_geometry(
        tx_antenna,
        rx_antenna,
        generated_dir / "antenna_geometry_excitations.png",
    )
    boresight_index = int(
        np.argmin(rx_antenna.steering_u**2 + rx_antenna.steering_v**2)
    )
    rx_boresight_beam = rx_antenna.beam(boresight_index)
    plot_antenna_patterns(
        rx_boresight_beam,
        generated_dir,
        filename_prefix="rx_boresight_beam",
        title="Lannik Psi RX boresight beam",
        effective_peak_gain_dbi=(
            rx_antenna.boresight_gain_dbi + 10.0 * np.log10(rx_antenna.element_count)
        ),
    )
    plot_antenna_patterns(
        rx_antenna,
        generated_dir,
        filename_prefix="rx_multibeam_max",
        title=f"Lannik Psi RX max over {rx_antenna.beam_count} beams",
        effective_peak_gain_dbi=(
            rx_antenna.boresight_gain_dbi + 10.0 * np.log10(rx_antenna.element_count)
        ),
        beamwidth_label="individual-beam 3 dB BW",
        principal_region_rx=rx_antenna,
    )
    plot_rx_beam_grid(rx_antenna, generated_dir)
    plot_two_way_patterns(tx_antenna, rx_antenna, generated_dir)
    plot_multibeam_range_cuts(product, tx_antenna, rx_antenna, generated_dir)
    for cut in COVERAGE_CUTS:
        plot_pd_coverage_cut(product, rx_antenna, cut, generated_dir)

    if not is_non_interactive_backend():
        plt.show()


if __name__ == "__main__":
    main()
