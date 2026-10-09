"""Capture loading, constants and estimators for the chamber captures.

Two sessions in the measurement chamber with our firmware and the chamber's
10 dBsm reference reflector (Microwave Factory MTR76P10-T5DW-100, 10 dBsm at
76.5 GHz), ten CPIs per case.

2026-09-29 (``archive/remove-lannik-embedded-220-gde2d009b``), our host tool's
calibration routine, all within 16 s, the reflector at an apparent 2.46 m:

- ``01-ddma``: all eight TX in DDMA, TX t stepping its phase by (t - 1) x 45 deg
  per chirp; the routine derives its calibration from these CPIs;
- ``02-single-tx``: TX1 alone;
- ``03-coherent``: all eight TX with that calibration's phases (recorded in the
  sidecars) and no phase step, a TX beam towards the reflector.

Waveform: 2048 samples at 25 MS/s (81.92 us), 900 MHz centred at 77.0 GHz,
256 chirps at 500 us, 20 dB TX backoff, RX gain 0 dB. The reflector's beat
frequency, 181 kHz, lies below the high-pass corner.

2026-10-09 (``release/omega/mifu2025-rc2_20261006-77-g7349c1fa``), the
reflector at an apparent 2.21 m, as on 2026-09-30 (TX1_CASES, NOTX_CASES):

- ``notx-1``..``notx-3``: no TX, 900 MHz in 10.24 us (512 samples at 50 MS/s,
  87.9 MHz/us), RX gain +3 dB, between the other captures;
- ``mode-1``: TX1, that steep chirp, 10 dB backoff, RX gain +3 dB: the
  reflector at 1.29 MHz, above the high-pass;
- ``mode-2`` and ``mode-3``: TX1, the 2026-09-29 waveform, RX gain +3 dB, 0 and
  10 dB backoff: the reflector at 162 kHz;
- ``01-ddma``, ``02-single-tx``, ``03-coherent``: the calibration routine with
  the 2026-09-29 waveform, 10 dB backoff, RX gain 0 dB. Its TX1-alone stage
  failed: the reflector is 25-30 dB weaker than TX1's line in DDMA and varies
  by several dB from CPI to CPI.

The format is our firmware's and loads with window_common.load_capture. The
locations are taken from ``--data``, else ``$CARKIT_CHAMBER_DATA`` /
``$CARKIT_CHAMBER_1009_DATA``, else ``$CARKIT_DATA_ROOT/2026-09-29_calibration`` /
``$CARKIT_DATA_ROOT/2026-10-09_lab_reflector``.

Windows: periodic Blackman-Harris in range, as in the window and field steps,
and also in Doppler. The reflector's line lies up to about 95 dB above the
noise per cell with the eight-TX beam, where Hann's sidelobes would still leak
into remote Doppler. Both are normalized by their sums.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.optimize import least_squares
from scipy.signal import get_window

import carkit_common
from carkit_common import STUDY_DIR, BoolArray, ComplexArray, FloatArray, db
from field_common import (
    CALIBRATION_RX_PHASE_DEG,
    RX_X_M,
    find_peak,
    static_power_profile,
    static_samples,
)
from radarperf.phase_noise import SingleReturnPhaseNoise
from window_common import (
    Capture,
    load_capture,
    range_spectrum,
    range_window,
    read_sidecar,
    slow_time_spectrum,
)

GENERATED_DIR = STUDY_DIR / "generated" / "chamber"
DATA_ENV = "CARKIT_CHAMBER_DATA"
DEFAULT_DATA_DIR = carkit_common.default_data_dir("2026-09-29_calibration")
DATA_1009_ENV = "CARKIT_CHAMBER_1009_DATA"
DEFAULT_1009_DIR = carkit_common.default_data_dir("2026-10-09_lab_reflector")
GENERATED_1009_DIR = GENERATED_DIR / "2026-10-09"

DDMA_CASE = "01-ddma"
SINGLE_CASE = "02-single-tx"
COHERENT_CASE = "03-coherent"
CASES = (SINGLE_CASE, DDMA_CASE, COHERENT_CASE)
# 2026-10-09: TX1 with the steep chirp at 10 dB backoff, and with the
# 2026-09-29 waveform at 0 and 10 dB backoff; no TX with the steep chirp.
STEEP_CASE = "mode-1"
FULL_POWER_CASE = "mode-2"
BACKOFF_CASE = "mode-3"
TX1_CASES = (STEEP_CASE, FULL_POWER_CASE, BACKOFF_CASE)
NOTX_CASES = ("notx-1", "notx-2", "notx-3")

# The chamber reflector: 10 dBsm at 76.5 GHz (manufacturer's product page), and
# the inner edge an ideal triangular trihedral of that RCS would have, 77.8 mm
# (NOTES, Reflector; not measured), for its finite-aperture factor
# (trihedral_factor).
REFLECTOR_RCS_DBSM = 10.0
REFLECTOR_EDGE_M = 0.0778
# Apparent ranges searched for the reflector, and for its double bounce
# (radar -> reflector -> radar front -> reflector -> radar) as multiples of it.
REFLECTOR_SEARCH_M = (1.5, 3.5)
DOUBLE_BOUNCE_SEARCH = (1.85, 2.1)
# The lab comparison of the home-made reflector with the chamber reflector
# (NOTES, Reflector; inputs/rcs-comparison.png): TX1 resolved in DDMA,
# the radar turned towards each on the turntable, the chamber reflector at
# 2.22 m, the home-made one (100 mm inner edge) at 2.51 m and about 15 deg to
# the side; P x R^4 came out 1.27 dB higher for the home-made one.
LAB_COMPARISON_RANGES_M = (2.22, 2.51)
LAB_COMPARISON_RATIO_DB = 1.27
HOME_MADE_EDGE_M = 0.100
# Static profiles are padded this many times in range.
PADDING = 16
# Remote Doppler: slow-time bins at least this far from every TX line.
LINE_GUARD_HZ = 60.0

# TX phase centres [m] (x, y), TX1..TX8, Infineon numbering, from the element
# outlines of the H&Scarkit drawing of the FARAD-IV antenna plate (l2-sp
# matlab/Users/patrik/pa_260916_antenna_centers.m, getCarkitFaradIvGeometry),
# as field_common.RX_X_M for the RX, whose y is 11.152 mm.
TX_POSITION_M = (
    np.array(
        [
            [23.818, 58.955],
            [13.039, 58.955],
            [43.222, 58.955],
            [54.002, 58.955],
            [54.002, 41.312],
            [62.624, 50.133],
            [71.250, 56.015],
            [71.250, 38.370],
        ]
    )
    * 1e-3
)

# The positive-frequency range bin of our real-sampled beat signal carries
# minus the received RF phase: a TX shifter's +theta shows there as -theta.
# Calibration records of our host tool, in its conventions: rx_phase_deg is the
# correction multiplied into the range bins as exp(+j phase), so the received
# RF phase of RX r relative to RX1; tx_phase_deg is the phase each TX's shifter
# is set to, so minus the received RF phase of TX t relative to TX1. Records
# by creation time (UTC), as (TX, RX, where it comes from):
CALIBRATION_RECORDS: dict[str, tuple[FloatArray, FloatArray, str]] = {
    "2026-09-29T09:28:19Z": (
        np.array(
            [
                0.0,
                153.31389475497767,
                -133.62237957451194,
                7.348851825015724,
                5.077243210633405,
                9.665282991372505,
                -32.084240597053906,
                12.824049500665765,
            ]
        ),
        np.array(
            [
                0.0,
                17.241059878483053,
                -22.90053084484068,
                -60.75461130025001,
                105.7631810090322,
                -14.5291109975488,
                -9.494832920417236,
                123.80054994142671,
            ]
        ),
        "chamber, reflector at 2.46 m (2026-09-29 sidecars)",
    ),
    "2026-09-29T12:19:12Z": (
        np.array(
            [
                0.0,
                154.36539608509227,
                -133.33105722187366,
                8.313076766980032,
                4.138424932576317,
                9.849121387726532,
                -30.270605959735907,
                13.52792520949955,
            ]
        ),
        np.array(
            [
                0.0,
                17.66923918117864,
                -22.772063016168197,
                -60.86348356821182,
                105.86009130614916,
                -14.4844807966125,
                -9.137963431121129,
                124.02623724143884,
            ]
        ),
        "chamber three hours later, 200 MHz waveform (l2-sp projects/psi/firmware/"
        "host/calibrations/lab-77ghz-20260929.json, 761ce343)",
    ),
    "2026-09-30T08:14:19Z": (
        np.array(
            [
                0.0,
                129.22766403829374,
                -133.57573557709176,
                16.00721291632973,
                -42.29314299700459,
                -4.103300589056489,
                -19.75952610272323,
                -28.668737576205352,
            ]
        ),
        CALIBRATION_RX_PHASE_DEG,
        "reflector at 2.21 m (2026-09-30 window sidecars)",
    ),
}

# Viktor's report (inputs/CARKIT report.pdf, 2026-09-22), Infineon's firmware,
# reflector at about 2.2 m, 20 dB backoff. Table 2: TX power relative to TX1
# [dB]. Figures 1 and 2: phase corrections relative to TX1 / RX1 [deg] in the
# report's convention (corrected = measured x weight, so the received RF phase,
# like rx_phase_deg), at sampled centre frequencies 76.50, 76.75, ...,
# 78.00 GHz, digitized from the page rendered at 300 dpi: marker centroids by
# their tab10 colour, axes calibrated on the gridlines (about +-0.5 deg).
REPORT_TX_POWER_DB = np.array([0.00, -0.58, 0.53, -0.69, 0.76, -0.34, -0.36, 0.18])
REPORT_FREQUENCIES_HZ = 76.5e9 + 0.25e9 * np.arange(7)
REPORT_TX_CORRECTION_DEG = np.array(
    [
        [0.0] * 7,
        [-129.9, -135.1, -138.1, -139.5, -139.5, -141.3, -146.6],
        [113.2, 117.8, 120.6, 121.4, 122.8, 128.1, 135.2],
        [-22.2, -26.7, -29.0, -29.9, -31.0, -33.3, -38.4],
        [18.1, 20.1, 22.1, 23.1, 25.4, 27.8, 28.8],
        [13.5, -2.8, -14.1, -25.3, -38.4, -50.7, -60.0],
        [40.4, 24.0, 2.1, -14.9, -24.9, -36.1, -51.4],
        [23.5, 12.5, 4.3, -2.1, -10.0, -17.1, -20.8],
    ]
)
REPORT_RX_CORRECTION_DEG = np.array(
    [
        [0.0] * 7,
        [-1.5, 3.2, 8.7, 15.0, 21.0, 25.2, 29.8],
        [-51.8, -45.8, -39.5, -33.1, -25.8, -18.8, -11.5],
        [-97.6, -92.6, -87.0, -79.3, -71.3, -63.6, -56.1],
        [67.4, 70.5, 75.0, 78.3, 83.3, 87.4, 90.7],
        [-62.1, -60.5, -58.3, -54.3, -50.5, -47.6, -44.0],
        [-58.3, -64.0, -68.6, -72.4, -79.3, -87.4, -92.6],
        [78.1, 76.2, 73.7, 71.9, 70.7, 70.0, 70.7],
    ]
)

# CTRX8188F analog high-pass filter: second order, 300 kHz at its -6 dB point
# (+-10 %), target datasheet rev. 0.20, Table 31; cut-offs 300-4800 kHz by
# RX_HP_FC per ramp segment (user manual rev. 0.20, Table 120). The manual
# models its phase as 180 deg - 2 atan(f / f_c) (section 2.3.8.1): two
# coincident first-order poles, whose -6 dB point is the pole frequency.
HIGH_PASS_NOMINAL_HZ = 300e3


def data_argument(parser: argparse.ArgumentParser) -> None:
    """Add the optional raw-data directory argument."""
    carkit_common.data_argument(parser, DATA_ENV, DEFAULT_DATA_DIR)


def resolve_data_dir(data: Path | None) -> Path:
    """Return the raw data directory from argument, environment or default."""
    return carkit_common.resolve_data_dir(data, DATA_ENV, DEFAULT_DATA_DIR)


def load(case: str, data: Path | None, *, verify: bool = False) -> Capture:
    """Load one chamber case."""
    return load_capture(case, resolve_data_dir(data), verify=verify)


def data_1009_argument(parser: argparse.ArgumentParser) -> None:
    """Add the optional raw-data directory argument for 2026-10-09."""
    carkit_common.data_argument(parser, DATA_1009_ENV, DEFAULT_1009_DIR)


def load_1009(case: str, data: Path | None, *, verify: bool = False) -> Capture:
    """Load one 2026-10-09 chamber case."""
    root = carkit_common.resolve_data_dir(data, DATA_1009_ENV, DEFAULT_1009_DIR)
    return load_capture(case, root, verify=verify)


def measured_high_pass_corner_hz() -> float:
    """The high-pass corner chamber_tx1.py measured on the reflector."""
    path = GENERATED_1009_DIR / "tx1" / "summary.json"
    if not path.is_file():
        raise SystemExit(f"{path} not found; run chamber_tx1.py first")
    corner: float = json.loads(path.read_text())["high_pass"]["corner_khz"] * 1e3
    return corner


def sidecar(capture: Capture) -> dict[str, Any]:
    """The first CPI's sidecar, for fields the Capture does not carry."""
    return read_sidecar(capture.binary_paths[0].with_suffix(".json"))


def tx_phase_steps_deg(capture: Capture) -> FloatArray:
    """Per-chirp phase step of each enabled TX [deg] (DDMA codes; 0 otherwise)."""
    steps = sidecar(capture)["actual_waveform"]["tx_phase_step_deg"]
    return np.asarray(steps, dtype=float)


def reflector_beat(capture: Capture) -> float:
    """Beat frequency of the reflector: the strongest zero-Doppler peak within
    REFLECTOR_SEARCH_M, refined on the mean over CPIs of the static samples.

    Under DDMA the static samples keep TX1's line, at zero Doppler, which
    locates the reflector as well as the beam does.
    """
    profile = static_power_profile(capture, 8)
    range_m = capture.range_axis(8)
    inside = (range_m >= REFLECTOR_SEARCH_M[0]) & (range_m <= REFLECTOR_SEARCH_M[1])
    coarse = float(
        capture.beat_frequency_hz(range_m[inside][np.argmax(profile[inside])])
    )
    statics = [static_samples(capture.load(frame)) for frame in range(capture.n_frames)]
    beat, _ = find_peak(np.mean(statics, axis=0), capture.sample_rate_hz, coarse)
    return beat


def reflector_gains(capture: Capture, beat_hz: float, bands: int = 1) -> ComplexArray:
    """Per-chirp complex amplitudes at ``beat_hz``, [band, frame, chirp, RX].

    The payload split into ``bands`` equal sub-bands, each with its own
    Blackman-Harris window (carkit_common.chirp_gains). A sub-band's phase is
    referred to its own first sample, which turns all channels alike.
    """
    nc, ns, _ = capture.shape
    length = ns // bands
    weights = range_window(length)
    out = []
    for frame in range(capture.n_frames):
        raw = capture.load(frame)
        x = raw - raw.mean(axis=(0, 1), keepdims=True)
        out.append(
            [
                carkit_common.chirp_gains(
                    x[:, k * length : (k + 1) * length],
                    np.array([beat_hz]),
                    capture.sample_rate_hz,
                    weights,
                )[:, 0]
                for k in range(bands)
            ]
        )
    return np.asarray(np.transpose(np.asarray(out), (1, 0, 2, 3)))


def band_centres_hz(capture: Capture, bands: int) -> FloatArray:
    """RF frequency at the middle of each sub-band of reflector_gains."""
    length = capture.n_samples // bands
    sample = np.arange(bands) * length + length / 2
    return np.asarray(
        capture.start_frequency_hz
        + capture.slope_hz_per_s * sample / capture.sample_rate_hz
    )


def doppler_window(length: int) -> FloatArray:
    """Periodic Blackman-Harris window for slow time (see the module docstring)."""
    return np.asarray(get_window("blackmanharris", length), dtype=float)


def remote_doppler(capture: Capture) -> BoolArray:
    """Slow-time bins at least LINE_GUARD_HZ from every TX's line.

    Our firmware's DDMA steps TX t's phase by the same amount every chirp, so
    its static returns sit on equidistant lines at multiples of PRF / 8.
    """
    n_lines = (
        len(tx_phase_steps_deg(capture)) if np.any(tx_phase_steps_deg(capture)) else 1
    )
    bin_hz = 1 / (capture.n_chirps * capture.chirp_period_s)
    guard = math.ceil(LINE_GUARD_HZ / bin_hz) - 1
    return carkit_common.away_from_lines(capture.n_chirps, n_lines, guard)


def remote_covariance(capture: Capture) -> ComplexArray:
    """8x8 RX covariance per native range bin [bin, RX, RX] over the
    remote-Doppler cells (remote_doppler) of all CPIs, with Blackman-Harris
    range and Doppler windows."""
    nc, ns, n_rx = capture.shape
    remote = remote_doppler(capture)
    weights = doppler_window(nc)
    covariance = np.zeros((ns // 2 + 1, n_rx, n_rx), dtype=complex)
    for frame in range(capture.n_frames):
        raw = capture.load(frame)
        x = raw - raw.mean(axis=(0, 1), keepdims=True)
        cells = slow_time_spectrum(range_spectrum(x), weights)[remote]
        covariance += np.einsum("drk,drl->rkl", cells, cells.conj())
    return np.asarray(covariance / (capture.n_frames * remote.sum()))


def floor_density(capture: Capture) -> tuple[FloatArray, FloatArray]:
    """Beat frequency per range bin and the channel-independent remote-Doppler
    floor there as a density [counts^2/Hz] (background_split, cell_to_density)."""
    nc, ns, _ = capture.shape
    independent = background_split(remote_covariance(capture))["independent"]
    return (
        capture.beat_frequency_hz(capture.range_axis()),
        cell_to_density(
            independent,
            ns,
            nc,
            capture.sample_rate_hz,
            range_window(ns),
            doppler_window(nc),
        ),
    )


def per_tx_amplitudes(gains: ComplexArray, steps_deg: FloatArray) -> ComplexArray:
    """Each TX's mean complex amplitude from DDMA per-chirp gains [chirp, RX].

    The phase a TX's shifter adds appears with the opposite sign in the
    positive-frequency range bin of our real-sampled beat signal: TX t's
    return advances by -step_t per chirp. Returns [TX, RX].
    """
    n = np.arange(gains.shape[0])
    demodulate = np.exp(1j * np.radians(steps_deg)[:, None] * n[None, :])
    return np.asarray(demodulate @ gains / gains.shape[0])


def background_split(covariance: ComplexArray) -> dict[str, FloatArray]:
    """Per-bin background parts from RX covariances [bin, RX, RX].

    ``total`` is the mean power per RX, ``independent`` the mean of the middle
    four eigenvalues (window_scene's channel-independent floor), ``common`` the
    excess of the total over it, and ``top`` the largest eigenvalue.
    """
    eigenvalues = np.linalg.eigvalsh(covariance)
    n = covariance.shape[-1]
    total = np.real(np.trace(covariance, axis1=-2, axis2=-1)) / n
    independent = eigenvalues[..., 2:6].mean(axis=-1)
    return {
        "total": np.asarray(total),
        "independent": np.asarray(independent),
        "common": np.asarray(total - independent),
        "top": np.asarray(eigenvalues[..., -1]),
    }


def signature_alignment(
    covariance: ComplexArray, signature: ComplexArray
) -> FloatArray:
    """|v1^H a|^2 / |a|^2 of the top eigenvector v1 with a return's per-RX amplitudes."""
    _, vectors = np.linalg.eigh(covariance)
    top = vectors[..., :, -1]
    return np.asarray(
        np.abs(top.conj() @ signature) ** 2 / np.sum(np.abs(signature) ** 2)
    )


def coherent_rx_gain_db(
    covariance: ComplexArray, signature: ComplexArray
) -> FloatArray:
    """SNR gain of combining the RX towards a return, against a background.

    Equal-gain, phase-only weights w = a / |a| towards the per-RX amplitudes a.
    The gain is the combined SNR |w^H a|^2 / (w^H R w) over the mean single-RX
    SNR |a_r|^2 / R_rr, per covariance R [..., RX, RX]: 10 log10(N) for equal
    amplitudes and independent equal noise, 0 dB against a background with the
    return's own spatial signature.
    """
    w = signature / np.abs(signature)
    combined = np.abs(w.conj() @ signature) ** 2 / np.real(
        np.einsum("i,...ij,j->...", w.conj(), covariance, w)
    )
    diagonal = np.real(np.diagonal(covariance, axis1=-2, axis2=-1))
    single = np.mean(np.abs(signature) ** 2 / diagonal, axis=-1)
    return np.asarray(db(combined / single))


def high_pass_db(frequency_hz: npt.ArrayLike, corner_hz: float) -> FloatArray:
    """Two coincident first-order high-pass poles [dB]: -6 dB at ``corner_hz``."""
    f = np.asarray(frequency_hz, dtype=float)
    return np.asarray(-2 * db(1 + (corner_hz / f) ** 2))


def fit_high_pass_corner(
    frequency_hz: FloatArray, response_db: FloatArray, reference_hz: float
) -> tuple[float, float]:
    """Corner of high_pass_db fitted to a response relative to ``reference_hz``.

    Returns the corner and the rms residual [dB].
    """

    def residual(p: FloatArray) -> FloatArray:
        model = high_pass_db(frequency_hz, p[0]) - high_pass_db(reference_hz, p[0])
        return np.asarray(model - response_db)

    fit = least_squares(residual, [HIGH_PASS_NOMINAL_HZ], bounds=(1e3, 1e7))
    return float(fit.x[0]), float(np.sqrt(np.mean(fit.fun**2)))


def real_tone_skirt(
    phase_noise: SingleReturnPhaseNoise, beat_hz: float, if_hz: npt.ArrayLike
) -> FloatArray:
    """Phase-noise skirt of a real-sampled return at ``if_hz`` [1/Hz re carrier].

    A real beat tone cos(2 pi f_b t + phi) is two complex tones at +-f_b, each
    carrying the delay-filtered phase noise. At IF x > f_b the upper sideband of
    the +f_b tone (offset x - f_b) and the sideband of the -f_b tone reaching
    across zero (offset x + f_b) add, relative to the carrier's own bin.
    """
    x = np.asarray(if_hz, dtype=float)
    return np.asarray(
        phase_noise.residual_psd_per_hz(x - beat_hz)
        + phase_noise.residual_psd_per_hz(x + beat_hz)
    )


def cell_to_density(
    cell_power: npt.ArrayLike,
    n_samples: int,
    n_chirps: int,
    sample_rate_hz: float,
    range_weights: FloatArray,
    doppler_weights: FloatArray,
) -> FloatArray:
    """White-noise density [counts^2/Hz, one-sided] from an RD-cell power.

    With sum-normalized windows a white per-sample variance s lands in a cell
    as s x ENBW_r / N_s x ENBW_d / N_c; the real samples spread s over
    0..fs/2. Independent of window, length and sample rate.
    """
    per_sample = (
        np.asarray(cell_power, dtype=float)
        * n_samples
        / carkit_common.enbw_bins(range_weights)
        * n_chirps
        / carkit_common.enbw_bins(doppler_weights)
    )
    return np.asarray(per_sample * 2 / sample_rate_hz)


def delay_fit(
    phase_deg: FloatArray, frequency_hz: FloatArray
) -> tuple[FloatArray, FloatArray]:
    """Delays [s] from received RF phases [band, channel] against RF frequency.

    A path delay tau turns the received RF phase by -2 pi f tau (in the range
    bins, minus that). Unwraps along frequency, fits a line per channel and
    returns -slope / (2 pi) and the rms residual [deg].
    """
    phase = np.unwrap(np.radians(phase_deg), axis=0)
    design = np.column_stack(
        [np.ones_like(frequency_hz), frequency_hz - frequency_hz.mean()]
    )
    solution, *_ = np.linalg.lstsq(design, phase, rcond=None)
    residual = phase - design @ solution
    return (
        np.asarray(-solution[1] / (2 * np.pi)),
        np.asarray(np.degrees(np.sqrt(np.mean(residual**2, axis=0)))),
    )


def trihedral_factor(
    edge_m: float,
    range_m: float,
    half_baseline_m: npt.ArrayLike,
    wavelength_m: float,
    points: int = 401,
) -> ComplexArray:
    """Finite-aperture factor F of a triangular trihedral at short range.

    Triple reflection images the TX through the vertex, and the return reaches
    an RX through the reflector's projected aperture: a regular hexagon of area
    a^2 / sqrt(3), the area in its RCS, one vertex along x. In the paraxial
    form of l2-sp ``matlab/Users/patrik/pa_260916_antenna_centers.md``
    ("Finite-aperture approximation"), for a reflector aimed at the array,

        F(d) = (1 / A) integral_A exp(-j k |p - d|^2 / R) d^2p,

    with d = (r - t) / 2 the half of the TX-to-RX baseline [..., 2]. |F|^2 is the
    pair's power relative to the far-field monostatic return: at d = 0 it is
    the on-axis near-field loss (field_common.near_field_loss_db for a disk),
    and it falls as the RX moves out of the narrow returned beam. The plates'
    angle-dependent truncation, element patterns and polarization are left out.
    """
    area = edge_m**2 / math.sqrt(3)
    side = math.sqrt(2 * area / (3 * math.sqrt(3)))
    axis = (np.arange(points) + 0.5) / points * 2 * side - side
    x, y = np.meshgrid(axis, axis)
    inside = (np.abs(y) <= math.sqrt(3) / 2 * side) & (
        np.abs(y) <= math.sqrt(3) * (side - np.abs(x))
    )
    px, py = x[inside], y[inside]
    d = np.asarray(half_baseline_m, dtype=float)
    k = 2 * math.pi / wavelength_m
    flat = d.reshape(-1, 2)
    values = np.array(
        [
            np.mean(np.exp(-1j * k * ((px - dx) ** 2 + (py - dy) ** 2) / range_m))
            for dx, dy in flat
        ]
    )
    return np.asarray(values.reshape(d.shape[:-1]))


def pair_power_db(
    edge_m: float,
    range_m: float,
    tx_m: FloatArray,
    rx_m: FloatArray,
    wavelength_m: float,
) -> FloatArray:
    """Each TX-RX pair's return [TX, RX] relative to the far-field monostatic
    one [dB]: 20 log10 |F| at half of each baseline (trihedral_factor)."""
    half = (rx_m[None, :, :] - tx_m[:, None, :]) / 2
    return np.asarray(
        20 * np.log10(np.abs(trihedral_factor(edge_m, range_m, half, wavelength_m)))
    )


def rx_positions_m() -> FloatArray:
    """RX phase centres (x, y) [m], from field_common.RX_X_M at y = 11.152 mm."""
    return np.column_stack([RX_X_M, np.full(RX_X_M.size, 11.152e-3)])


def wrap_deg(value: npt.ArrayLike) -> FloatArray:
    return np.asarray((np.asarray(value, dtype=float) + 180) % 360 - 180)


def plane_wave_fit(
    phase_deg: FloatArray, positions_m: FloatArray
) -> tuple[FloatArray, FloatArray]:
    """Fit phase = c + k . p (wrapped) over elements at ``positions_m`` [element, dim].

    Returns the gradient [deg/m] per dimension and the wrapped residual [deg].
    The constant absorbs the reference element; iterates the unwrapping about
    the fit.
    """
    design = np.column_stack([np.ones(len(phase_deg)), positions_m - positions_m[0]])
    target = np.asarray(phase_deg, dtype=float)
    solution = np.zeros(design.shape[1])
    for _ in range(4):
        target = design @ solution + wrap_deg(phase_deg - design @ solution)
        solution, *_ = np.linalg.lstsq(design, target, rcond=None)
    return np.asarray(solution[1:]), wrap_deg(phase_deg - design @ solution)


def gradient_to_angle_deg(gradient_deg_per_m: float, wavelength_m: float) -> float:
    """One-way phase gradient across an aperture -> plane-wave angle [deg]."""
    return math.degrees(math.asin(gradient_deg_per_m * wavelength_m / 360.0))
