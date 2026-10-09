"""Capture loading, spectra, legs and controls for the 2026-09-11 CARKIT walk.

The raw capture is the offline PSI-style conversion of the Hallesaker walk: one
JSON/bin pair per CPI, real int16 ADC samples ordered [chirp, sample, RX], in
the recording's ``tx1-1`` subfolder. The recording's location is taken from
``--data``, else ``$CARKIT_WALK_DATA``, else
``$CARKIT_DATA_ROOT/2026-09-11_walk_hallesaker``.

All spectra use periodic Blackman windows on both axes, as in Viktor's
processing, and are normalized by the window sum, so a tone's peak amplitude is
independent of window and padding. Only the physical (positive) half of the
real-sampled range spectrum is used. The outdoor captures use other windows;
see outdoor_common.py.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.fft import fft, fftshift, rfft
from scipy.signal.windows import blackman

import carkit_common
from carkit_common import N_RX, SPEED_OF_LIGHT, STUDY_DIR, FloatArray

ComplexArray = npt.NDArray[np.complexfloating[Any, Any]]
BoolArray = npt.NDArray[np.bool_]
IntArray = npt.NDArray[np.int64]

GENERATED_DIR = STUDY_DIR / "generated" / "walk"
DATA_ENV = "CARKIT_WALK_DATA"
DEFAULT_DATA_DIR = carkit_common.default_data_dir("2026-09-11_walk_hallesaker")
# The walk's subfolder in the recording.
CASE = "tx1-1"

# RF centre of the sampled sweep: start + slope * pre-payload + half the sampled
# bandwidth, matching the report. Used only to convert Doppler to velocity.
CARRIER_HZ = 76.374237e9
PADDING = 4
# Far-quarter noise: the farthest quarter of the range axis, native Doppler bins
# with |v| at least this, per RX.
FAR_RANGE_FRACTION = 0.75
NOISE_ABS_VELOCITY_MIN_MPS = 1.0

# Contiguous walk legs with a reliably tracked reflector (inclusive CPI indices).
LEGS: dict[str, tuple[int, int]] = {"outbound": (26, 70), "inbound": (89, 127)}
# The tracked peak is trusted as the reflector position from FIRST_CONTROL_FRAME
# through LAST_TRACKED_FRAME; later CPIs are treated as post-walk controls.
FIRST_CONTROL_FRAME = 26
LAST_TRACKED_FRAME = 160
CONTROL_EXCLUSION_M = 8.0

REFERENCE_RANGE_M = 100.0
REFERENCE_RCS_DBSM = 10.0
# RX gain of the walk: gain code 0 for all receivers of the recorded mode
# (provenance/configuration.json), checked by load_capture. walk_model.py uses
# it without the raw data.
RX_GAIN_DB = 3.0
# Walking reflector relative to the nominal 10 dBsm lab reference (Slack,
# 2026-09-28). Results are scaled back to 10 dBsm, the RCS used by the model.
WALKING_RCS_DBSM = 11.27
RCS_CORRECTION_DB = WALKING_RCS_DBSM - REFERENCE_RCS_DBSM
# Report value for comparison: fixed-R^-4 fit of an RX magnitude sum at 100 m.
REPORT_SNR_DB = 36.57


def data_argument(parser: argparse.ArgumentParser) -> None:
    """Add the optional recording directory argument."""
    carkit_common.data_argument(parser, DATA_ENV, DEFAULT_DATA_DIR)


def resolve_data_dir(data: Path | None) -> Path:
    """Return the recording directory from argument, environment or default."""
    return carkit_common.resolve_data_dir(data, DATA_ENV, DEFAULT_DATA_DIR)


@dataclass(frozen=True)
class Capture:
    """Validated layout and waveform of one directory of CPI pairs."""

    root: Path
    json_paths: tuple[Path, ...]
    binary_paths: tuple[Path, ...]
    shape: tuple[int, int, int]
    sample_rate_hz: float
    chirp_period_s: float
    slope_hz_per_s: float
    start_frequency_hz: float
    sampled_bandwidth_hz: float
    pre_payload_s: float
    rx_gain_db: float

    @property
    def n_frames(self) -> int:
        return len(self.json_paths)

    @property
    def n_chirps(self) -> int:
        return self.shape[0]

    @property
    def n_samples(self) -> int:
        return self.shape[1]

    def load(self, frame: int) -> FloatArray:
        """Load one CPI as float64 [chirp, sample, RX] without other changes."""
        raw = np.fromfile(self.binary_paths[frame], dtype="<i2")
        return np.asarray(raw.reshape(self.shape), dtype=float)

    def range_axis(self, padding: int = PADDING) -> FloatArray:
        """Physical range for a real-sample range FFT of ``padding`` x length."""
        beat_hz = np.fft.rfftfreq(padding * self.n_samples, 1 / self.sample_rate_hz)
        return np.asarray(SPEED_OF_LIGHT * beat_hz / (2 * self.slope_hz_per_s))

    def native_velocity(self) -> FloatArray:
        """Radial velocity of unpadded, unshifted Doppler bins."""
        doppler_hz = np.fft.fftfreq(self.n_chirps, self.chirp_period_s)
        return np.asarray(SPEED_OF_LIGHT * doppler_hz / (2 * CARRIER_HZ))

    def padded_velocity(self, n_chirps: int | None = None) -> FloatArray:
        """Radial velocity of a ``PADDING`` x padded, centred Doppler FFT."""
        count = PADDING * (n_chirps or self.n_chirps)
        doppler_hz = fftshift(np.fft.fftfreq(count, self.chirp_period_s))
        return np.asarray(SPEED_OF_LIGHT * doppler_hz / (2 * CARRIER_HZ))

    def beat_frequency_hz(self, range_m: npt.ArrayLike) -> FloatArray:
        """Beat frequency of a target at ``range_m``."""
        return np.asarray(
            2 * self.slope_hz_per_s * np.asarray(range_m, dtype=float) / SPEED_OF_LIGHT
        )


def _number(mapping: dict[str, Any], key: str) -> float:
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be numeric")
    return float(value)


def load_capture(data: Path | None = None, *, verify: bool = False) -> Capture:
    """Load and validate the capture layout; ``verify`` also checks SHA-256."""
    root = resolve_data_dir(data) / CASE
    json_paths = tuple(sorted(root.glob("cpi_*.json")))
    if not json_paths:
        raise ValueError(f"no cpi_*.json files found under {root}")
    first = json.loads(json_paths[0].read_text())
    sample_format = first["sample_format"]
    waveform = first["waveform"]
    if sample_format["dtype"] != "int16" or sample_format["byte_order"] != "little":
        raise ValueError("only little-endian int16 input is supported")
    if sample_format["axes"] != ["chirp", "sample", "rx"]:
        raise ValueError("expected axes [chirp, sample, rx]")
    shape = tuple(int(value) for value in sample_format["shape"])
    if len(shape) != 3 or shape[2] != N_RX:
        raise ValueError(f"unexpected sample shape {shape}")
    expected_bytes = math.prod(shape) * np.dtype("<i2").itemsize

    binary_paths = []
    for expected_cpi, json_path in enumerate(json_paths):
        metadata = json.loads(json_path.read_text())
        if int(metadata["cpi"]) != expected_cpi:
            raise ValueError(f"non-contiguous CPI numbering at {json_path}")
        if (
            metadata["sample_format"] != sample_format
            or metadata["waveform"] != waveform
        ):
            raise ValueError(f"layout or waveform changes at {json_path}")
        binary_path = root / str(metadata["file"])
        if not binary_path.is_file() or binary_path.stat().st_size != expected_bytes:
            raise ValueError(f"missing or incorrectly sized binary {binary_path}")
        if verify:
            digest = hashlib.sha256(binary_path.read_bytes()).hexdigest()
            if digest != metadata["sha256"]:
                raise ValueError(f"SHA-256 mismatch for {binary_path}")
        binary_paths.append(binary_path)

    return Capture(
        root=root,
        rx_gain_db=active_rx_gain_db(root),
        json_paths=json_paths,
        binary_paths=tuple(binary_paths),
        shape=(shape[0], shape[1], shape[2]),
        sample_rate_hz=_number(waveform, "sample_rate_msps") * 1e6,
        chirp_period_s=_number(waveform, "chirp_period_us") * 1e-6,
        slope_hz_per_s=_number(waveform, "slope_hz_per_s"),
        start_frequency_hz=_number(waveform, "carkit_start_frequency_hz"),
        sampled_bandwidth_hz=_number(waveform, "adc_bandwidth_hz"),
        pre_payload_s=_number(waveform, "pre_payload_us") * 1e-6,
    )


def active_rx_gain_db(root: Path) -> float:
    """RX gain of the recorded mode, from Infineon's configuration.

    ``provenance/configuration.json`` holds every mode's receiver settings;
    ``operation.current_mode`` is the one recorded. All receivers must share
    one gain code, which carkit_common.RX_GAIN_STEPS_DB turns into dB.
    """
    configuration = json.loads((root / "provenance" / "configuration.json").read_text())
    operation = configuration["operation"]
    mode = operation["modes"][int(operation["current_mode"])]
    codes = {int(receiver["gain"]) for receiver in mode["receivers"]}
    if len(codes) != 1:
        raise ValueError(f"RX gain codes differ between receivers: {sorted(codes)}")
    gain = carkit_common.RX_GAIN_STEPS_DB[codes.pop()]
    if gain != RX_GAIN_DB:
        raise ValueError(f"recorded RX gain {gain} dB, expected {RX_GAIN_DB} dB")
    return gain


def window(length: int) -> FloatArray:
    """Periodic Blackman window."""
    return np.asarray(blackman(length, sym=False), dtype=float)


def window_enbw_bins(length: int) -> float:
    """Equivalent noise bandwidth of the periodic Blackman window in bins."""
    weights = window(length)
    return float(length * np.sum(weights**2) / np.sum(weights) ** 2)


def range_spectrum(raw: FloatArray, padding: int = PADDING) -> ComplexArray:
    """Windowed, normalized real-sample range FFT along the sample axis."""
    weights = window(raw.shape[1])
    return np.asarray(
        rfft(raw * weights[None, :, None], n=padding * raw.shape[1], axis=1, workers=-1)
        / weights.sum()
    )


def native_doppler(spectrum: ComplexArray) -> ComplexArray:
    """Windowed, normalized, unpadded and unshifted slow-time FFT (axis 0)."""
    weights = window(spectrum.shape[0])
    shape = [1] * spectrum.ndim
    shape[0] = weights.size
    return np.asarray(
        fft(spectrum * weights.reshape(shape), axis=0, workers=-1) / weights.sum()
    )


def padded_doppler(spectrum: ComplexArray) -> ComplexArray:
    """Windowed, normalized, ``PADDING`` x padded and centred slow-time FFT."""
    weights = window(spectrum.shape[0])
    shape = [1] * spectrum.ndim
    shape[0] = weights.size
    transformed = fft(
        spectrum * weights.reshape(shape),
        n=PADDING * weights.size,
        axis=0,
        workers=-1,
    )
    return np.asarray(fftshift(transformed, axes=0) / weights.sum())


def leg_frames(leg: str) -> IntArray:
    """Inclusive CPI indices of one walk leg."""
    first, last = LEGS[leg]
    return np.arange(first, last + 1, dtype=np.int64)


def leg_of(frame: int) -> str:
    """Name of the walk leg containing ``frame``, or an empty string."""
    for name, (first, last) in LEGS.items():
        if first <= frame <= last:
            return name
    return ""


def control_frames(
    tracked_range_m: FloatArray,
    range_m: float,
    exclusion_m: float = CONTROL_EXCLUSION_M,
) -> BoolArray:
    """CPIs usable as reflector-free controls at ``range_m``.

    Controls start at FIRST_CONTROL_FRAME. Through LAST_TRACKED_FRAME, a CPI is
    excluded when its tracked reflector lies within ``exclusion_m``; later CPIs
    are post-walk controls. Those contain passing traffic, so estimators over
    controls must be robust (medians), not plain means.
    """
    frames = np.arange(tracked_range_m.size)
    tracked = frames <= LAST_TRACKED_FRAME
    nearby = tracked & (np.abs(tracked_range_m - range_m) <= exclusion_m)
    return np.asarray((frames >= FIRST_CONTROL_FRAME) & ~nearby)


@dataclass(frozen=True)
class Track:
    """Per-CPI target cell and per-RX values written by walk_extract.py."""

    frame: IntArray
    range_m: FloatArray
    velocity_mps: FloatArray
    selected: BoolArray
    magnitude_sum_snr_db: FloatArray
    rx_signal_power: FloatArray
    rx_far_snr_db: FloatArray

    def leg_mask(self, leg: str) -> BoolArray:
        first, last = LEGS[leg]
        return np.asarray((self.frame >= first) & (self.frame <= last))


def read_track(path: Path = GENERATED_DIR / "extract" / "per_frame.csv") -> Track:
    """Read the per-frame output of walk_extract.py."""
    if not path.is_file():
        raise SystemExit(f"{path} not found; run walk_extract.py first")
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    channels = range(1, N_RX + 1)
    return Track(
        frame=np.array([int(row["frame"]) for row in rows], dtype=np.int64),
        range_m=np.array([float(row["range_m"]) for row in rows]),
        velocity_mps=np.array([float(row["velocity_mps"]) for row in rows]),
        selected=np.array([row["selected"] == "True" for row in rows]),
        magnitude_sum_snr_db=np.array(
            [float(row["magnitude_sum_snr_db"]) for row in rows]
        ),
        rx_signal_power=np.array(
            [
                [
                    10 ** (float(row[f"rx{channel}_signal_power_db"]) / 10)
                    for channel in channels
                ]
                for row in rows
            ]
        ),
        rx_far_snr_db=np.array(
            [
                [float(row[f"rx{channel}_far_snr_db"]) for channel in channels]
                for row in rows
            ]
        ),
    )
