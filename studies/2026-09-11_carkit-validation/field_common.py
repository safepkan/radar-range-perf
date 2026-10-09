"""Capture loading, constants and estimators for the field captures.

Captures of 2026-10-01 on a grass football pitch at Lindevi, about 100 m to the
end of the pitch, with our firmware, TX1 and RX gain +3 dB:

- the walk's corner reflector on a small tripod, about 1 m high like the radar,
  placed at nominal 5, 10, 20, 40, 60 and 100 m (indicative distances) and
  captured with the short and then the medium waveform, 15-28 s apart;
- the empty scene with both waveforms;
- ``notx``: the medium waveform with no TX enabled;
- the sky (short waveform, TX1 and uncalibrated 8TX), which field_if.py uses
  for the background;
- runs with the reflector carried towards the radar, four with TX1 and one
  with uncalibrated 8TX, which field_runs.py analyses.

The format is our firmware's, as for the 2026-09-30 window captures, and loads
with window_common.load_capture. The location is taken from ``--data``, else
``$CARKIT_FIELD_DATA``, else ``$CARKIT_DATA_ROOT/2026-10-01_reflector_lindevi``.

The windows are the window steps': periodic Blackman-Harris in range and Hann
in Doppler, normalized by their sums, so a static tone's zero-Doppler
amplitude does not depend on the number of samples or chirps.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.signal import find_peaks

import carkit_common
from carkit_common import (
    INTERFERENCE_BAND_HZ,
    SPEED_OF_LIGHT,
    STUDY_DIR,
    ComplexArray,
    FloatArray,
    db,
    interference_flags,
    noise_figure_db,
)
from radarperf import (
    WINDOW_LOSS_BLACKMAN_HARRIS_DB,
    WINDOW_LOSS_HANN_DB,
    BeamCombination,
    FmcwWaveform,
    Radar,
    StandardProcessing,
    antenna,
    frontend,
)
from window_common import (
    Capture,
    doppler_window,
    load_capture,
    range_spectrum,
    range_window,
    slow_time_spectrum,
)

GENERATED_DIR = STUDY_DIR / "generated" / "field"
DATA_ENV = "CARKIT_FIELD_DATA"
DEFAULT_DATA_DIR = carkit_common.default_data_dir("2026-10-01_reflector_lindevi")

WAVEFORMS = ("medium", "short")
NOMINAL_RANGES_M = (5, 10, 20, 40, 60, 100)
NOTX_CASE = "notx"
# The walking reflector's inner edge, measured 2026-10-01 (NOTES, Reflector).
REFLECTOR_EDGE_M = 0.100
# Search for the reflector: apparent ranges, minimum rise over the empty scene.
SEARCH_RANGE_M = (2.5, 110.0)
MIN_RISE_DB = 10.0
# Peak refinement: half-width in native bins and grid step.
PEAK_HALF_WIDTH_BINS = 1.5
PEAK_STEP_BINS = 1 / 32
# Remote Doppler for the interference flags, as in the window steps.
FAR_DOPPLER_HZ = 1000.0

# RX phase centres along the horizontal axis [m], RX1..RX8, from the element
# outlines of the H&Scarkit drawing of the FARAD-IV antenna plate (l2-sp
# matlab/Users/patrik/pa_260916_antenna_centers.m, getCarkitFaradIvGeometry).
# RX7 and RX8 are swapped in position. Pitch 8.625 mm, 2.2 wavelengths at
# 77 GHz, so an angle is unambiguous only within about +-13 deg.
RX_X_M = (
    np.array([9.816, 18.442, 27.064, 35.687, 44.312, 52.938, 70.186, 61.563]) * 1e-3
)
# RX phases of the calibration record in the 2026-09-30 window sidecars
# (created 2026-09-30T08:14:19Z, reflector at 2.2 m). Multiplying a return's
# per-RX amplitudes by exp(+j phase) aligns them to a plane wave.
CALIBRATION_RX_PHASE_DEG = np.array(
    [
        0.0,
        10.394027063388323,
        -37.83435758210485,
        -83.15509441318403,
        77.59644184398381,
        -53.06149504264598,
        -62.24415403842398,
        78.74864216426543,
    ]
)


def data_argument(parser: argparse.ArgumentParser) -> None:
    """Add the optional raw-data directory argument."""
    carkit_common.data_argument(parser, DATA_ENV, DEFAULT_DATA_DIR)


def resolve_data_dir(data: Path | None) -> Path:
    """Return the raw data directory from argument, environment or default."""
    return carkit_common.resolve_data_dir(data, DATA_ENV, DEFAULT_DATA_DIR)


def load(case: str, data: Path | None, *, verify: bool = False) -> Capture:
    """Load one field case."""
    return load_capture(case, resolve_data_dir(data), verify=verify)


def placement_case(waveform: str, nominal_m: int) -> str:
    return f"{waveform}-{nominal_m}m"


def empty_case(waveform: str) -> str:
    return f"empty-{waveform}"


def static_samples(raw: FloatArray) -> FloatArray:
    """Hann-weighted mean over chirps of the offset-free samples, [sample, RX].

    The range spectrum of this at a tone's beat frequency is the tone's
    zero-Doppler range-Doppler cell, since both transforms are linear.
    """
    centred = raw - raw.mean(axis=(0, 1), keepdims=True)
    weights = doppler_window(raw.shape[0])
    return np.asarray(np.tensordot(weights / weights.sum(), centred, axes=(0, 0)))


def tone_amplitudes(
    samples: npt.ArrayLike, beat_hz: npt.ArrayLike, sample_rate_hz: float
) -> ComplexArray:
    """Blackman-Harris-weighted, sum-normalized DFT at ``beat_hz``, [beat, RX]."""
    values = np.asarray(samples)
    weights = range_window(values.shape[0])
    n = np.arange(values.shape[0])
    kernel = weights[None, :] * np.exp(
        -2j * np.pi * np.atleast_1d(beat_hz)[:, None] * n[None, :] / sample_rate_hz
    )
    return np.asarray(kernel @ values / weights.sum())


def find_peak(
    samples: npt.ArrayLike, sample_rate_hz: float, centre_hz: float
) -> tuple[float, ComplexArray]:
    """Beat frequency of the RX-mean power maximum near ``centre_hz``.

    Searches +-PEAK_HALF_WIDTH_BINS native bins in steps of PEAK_STEP_BINS.
    Returns the beat frequency and the per-RX amplitudes there.
    """
    values = np.asarray(samples)
    bin_hz = sample_rate_hz / values.shape[0]
    offsets = np.arange(
        -PEAK_HALF_WIDTH_BINS, PEAK_HALF_WIDTH_BINS + 1e-9, PEAK_STEP_BINS
    )
    grid = centre_hz + offsets * bin_hz
    amplitudes = tone_amplitudes(values, grid, sample_rate_hz)
    k = int(np.argmax(np.mean(np.abs(amplitudes) ** 2, axis=1)))
    return float(grid[k]), np.asarray(amplitudes[k])


def static_power_profile(capture: Capture, padding: int = 8) -> FloatArray:
    """Zero-Doppler power, mean over RX and CPIs, on a ``padding``-fold grid."""
    total = np.zeros(padding * capture.n_samples // 2 + 1)
    for frame in range(capture.n_frames):
        samples = static_samples(capture.load(frame))
        spectrum = range_spectrum(samples[None], padding)[0]
        total += np.mean(np.abs(spectrum) ** 2, axis=-1)
    return np.asarray(total / capture.n_frames)


def reflector_beat(case_capture: Capture, empty_capture: Capture) -> float:
    """Beat frequency of the reflector: the static peak that rose most over the
    empty scene, within SEARCH_RANGE_M and by at least MIN_RISE_DB."""
    padding = 8
    profile = static_power_profile(case_capture, padding)
    empty = static_power_profile(empty_capture, padding)
    range_m = case_capture.range_axis(padding)
    peaks, _ = find_peaks(db(profile), prominence=6.0)
    peaks = peaks[
        (range_m[peaks] >= SEARCH_RANGE_M[0]) & (range_m[peaks] <= SEARCH_RANGE_M[1])
    ]
    rise = db(profile[peaks]) - db(empty[peaks])
    if peaks.size == 0 or rise.max() < MIN_RISE_DB:
        raise ValueError(f"no reflector found in {case_capture.case}")
    best = peaks[int(np.argmax(rise))]
    return float(case_capture.beat_frequency_hz(range_m[best]))


def matching_samples(
    wide_start_hz: float,
    wide_bandwidth_hz: float,
    wide_samples: int,
    narrow_start_hz: float,
    narrow_bandwidth_hz: float,
) -> slice:
    """Samples of the wider sweep that cover the narrower sweep's RF band.

    Both sample at the same rate, so the selected samples sweep the narrow
    band at the wider sweep's slope: same RF band and range cell, higher beat
    frequency.
    """
    step = wide_bandwidth_hz / wide_samples
    first = round((narrow_start_hz - wide_start_hz) / step)
    count = round(narrow_bandwidth_hz / step)
    if first < 0 or first + count > wide_samples:
        raise ValueError("the narrow sweep is not inside the wide one")
    return slice(first, first + count)


def near_field_loss_db(
    edge_m: float, range_m: npt.ArrayLike, wavelength_m: float
) -> FloatArray:
    """First-order on-axis near-field loss of a triangular trihedral [dB, >= 0].

    |sinc(A / (lambda R))|^2 with sinc(x) = sin(x) / x and A = a^2 / sqrt(3), the
    projected aperture along the axis (NOTES, Reflector; l2-sp
    pa_260916_antenna_centers.md). Both legs' wavefront curvature enters.
    """
    area = edge_m**2 / math.sqrt(3)
    x = area / (wavelength_m * np.asarray(range_m, dtype=float))
    return np.asarray(-db((np.sin(x) / x) ** 2))


def trihedral_aim_loss_db(off_axis_deg: npt.ArrayLike) -> FloatArray:
    """RCS loss of an ideal triangular trihedral aimed ``off_axis_deg`` away
    from the radar [dB, >= 0; inf where no triple bounce returns].

    Geometric optics: sigma = 4 pi A^2 / lambda^2, with A the overlap of the
    aperture projected towards the radar and its point reflection through the
    vertex. With l + m + n = sqrt(3) cos(theta) for the direction cosines
    against the three edges, sigma / sigma_0 = ((3 cos^2 theta - 2) / cos theta)^2,
    independent of edge length and wavelength. Exact for every tilt direction
    to about 22 deg, and towards a plate to the zero at 35.26 deg, where the
    radar is in that plate's plane; towards an edge the loss beyond 22 deg is
    smaller (NOTES, Reflector).
    """
    c = np.cos(np.radians(np.asarray(off_axis_deg, dtype=float)))
    ratio = np.clip((3 * c**2 - 2) / c, 0.0, None) ** 2
    with np.errstate(divide="ignore"):
        return np.asarray(-10 * np.log10(ratio))


def azimuth_deg(amplitudes: ComplexArray, wavelength_m: float) -> tuple[float, float]:
    """Plane-wave azimuth of one return from its per-RX amplitudes.

    Applies the calibration phases, then maximises the normalized array
    response over the unambiguous sector. Returns the angle (its sign is not
    established) and the coherence |sum(steer* z/|z|)| / N, 1 for a perfect
    plane wave.
    """
    z = np.asarray(amplitudes) * np.exp(1j * np.radians(CALIBRATION_RX_PHASE_DEG))
    z = z / np.abs(z)
    limit = math.degrees(math.asin(wavelength_m / (2 * 8.625e-3)))
    grid = np.radians(np.linspace(-limit, limit, 2001))
    steer = np.exp(2j * np.pi * np.outer(np.sin(grid), RX_X_M) / wavelength_m)
    response = np.abs(steer.conj() @ z) / z.size
    k = int(np.argmax(response))
    return float(np.degrees(grid[k])), float(response[k])


def remote_doppler_levels(capture: Capture) -> FloatArray:
    """Per-CPI median remote-Doppler power over INTERFERENCE_BAND_HZ [dB]."""
    far = np.abs(capture.doppler_axis()) > FAR_DOPPLER_HZ
    beat = capture.beat_frequency_hz(capture.range_axis())
    band = (beat > INTERFERENCE_BAND_HZ[0]) & (beat < INTERFERENCE_BAND_HZ[1])
    levels = np.zeros(capture.n_frames)
    for frame in range(capture.n_frames):
        raw = capture.load(frame)
        cells = slow_time_spectrum(
            range_spectrum(raw - raw.mean(axis=(0, 1), keepdims=True))
        )
        levels[frame] = float(
            db(np.median(np.mean(np.abs(cells[far][:, band]) ** 2, axis=-1)))
        )
    return levels


def kept_frames(capture: Capture) -> tuple[list[int], list[int]]:
    """CPIs kept and dropped by the interference flags."""
    flags = interference_flags(remote_doppler_levels(capture))
    return np.flatnonzero(~flags).tolist(), np.flatnonzero(flags).tolist()


def zero_doppler_amplitudes(
    capture: Capture,
    frames: list[int],
    centre_hz: float,
    samples: slice = slice(None),
) -> tuple[float, ComplexArray]:
    """Peak beat frequency near ``centre_hz`` and the per-CPI, per-RX
    zero-Doppler amplitudes there [frame, RX], from the given ``samples``.

    The peak is found on the mean over CPIs of the static samples, which
    stay coherent from CPI to CPI for a fixed radar and reflector.
    """
    static = [static_samples(capture.load(k))[samples] for k in frames]
    beat, _ = find_peak(np.mean(static, axis=0), capture.sample_rate_hz, centre_hz)
    values = np.array(
        [tone_amplitudes(s, beat, capture.sample_rate_hz)[0] for s in static]
    )
    return beat, values


def reference_radar(capture: Capture) -> Radar:
    """walk_model's reference model with a capture's waveform and windows: TX1,
    datasheet TX power, the typical noise figure at the capture's RX gain
    (10 MHz IF), FARAD-IV directivity, no hardware losses, noncoherent RX,
    Blackman-Harris/Hann windows, no straddle or CFAR loss."""
    waveform = FmcwWaveform(
        center_frequency_hz=capture.center_frequency_hz,
        bandwidth_hz=capture.sampled_bandwidth_hz,
        sample_rate_hz=capture.sample_rate_hz,
        n_samples=capture.n_samples,
        n_chirps=capture.n_chirps,
        chirp_repetition_time_s=capture.chirp_period_s,
    )
    return Radar(
        frontend=frontend.ctrx8188f(
            n_tx=1, noise_figure_db=noise_figure_db(capture.rx_gain_db)
        ),
        antenna=antenna.sencity_farad_iv(),
        waveform=waveform,
        processing=StandardProcessing(
            rx_combination=BeamCombination.NONCOHERENT,
            range_window="blackmanharris",
            doppler_window="hann",
            range_fft_size=capture.n_samples,
            doppler_fft_size=capture.n_chirps,
            range_window_loss_db=WINDOW_LOSS_BLACKMAN_HARRIS_DB,
            doppler_window_loss_db=WINDOW_LOSS_HANN_DB,
            range_straddle_loss_db=0.0,
            doppler_straddle_loss_db=0.0,
            cfar_loss_db=0.0,
        ),
    )


def wavelength_m(capture: Capture) -> float:
    return float(SPEED_OF_LIGHT / capture.center_frequency_hz)


def read_summary(step: str) -> dict[str, Any]:
    """Read the summary.json written by an earlier field step."""
    path = GENERATED_DIR / step / "summary.json"
    if not path.is_file():
        raise SystemExit(f"{path} not found; run field_{step}.py first")
    summary: dict[str, Any] = json.loads(path.read_text())
    return summary
