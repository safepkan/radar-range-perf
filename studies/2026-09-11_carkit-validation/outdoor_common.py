"""Capture loading, windows and constants for the 2026-09-22 outdoor captures.

The raw data are four directories, one per waveform and nominal reflector
distance, each with ten CPIs of real int16 ADC samples ordered [chirp, sample,
RX], a JSON sidecar per CPI and a manifest. Their location is taken from
``--data``, else ``$CARKIT_OUTDOOR_DATA``, else
``$CARKIT_DATA_ROOT/2026-09-22_phase_noise_outdoor_reflector``.

Range spectra and per-chirp amplitudes use a periodic Blackman-Harris window,
and slow-time spectra a periodic Hann window. Both are normalized by the window
sum, so a tone's peak amplitude is independent of the window. Only the physical
(positive) half of the real-sampled range spectrum is used. The walk uses other
windows; see walk_common.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.fft import fft, rfft
from scipy.signal import get_window

import carkit_common
from carkit_common import N_RX, SPEED_OF_LIGHT, STUDY_DIR, ComplexArray, FloatArray

GENERATED_DIR = STUDY_DIR / "generated" / "outdoor"
DATA_ENV = "CARKIT_OUTDOOR_DATA"
DEFAULT_DATA_DIR = carkit_common.default_data_dir(
    "2026-09-22_phase_noise_outdoor_reflector"
)

# Folder name -> nominal reflector distance. The folder names are the only
# record of the setting; apparent ranges come from the data.
CASES: dict[str, float] = {
    "400MHz-5m": 5.0,
    "400MHz-10m": 10.0,
    "800MHz-5m": 5.0,
    "800MHz-10m": 10.0,
}
ADC_BITS = 12

# The reflector is the strongest static return in this window around the
# nominal distance.
REFLECTOR_GATE_M = (-2.0, 3.0)
# Remote Doppler: excludes the carrier, its window response and slow drift.
FAR_DOPPLER_HZ = 5000.0


def data_argument(parser: argparse.ArgumentParser) -> None:
    """Add the optional raw-data directory argument."""
    carkit_common.data_argument(parser, DATA_ENV, DEFAULT_DATA_DIR)


def resolve_data_dir(data: Path | None) -> Path:
    """Return the raw data directory from argument, environment or default."""
    return carkit_common.resolve_data_dir(data, DATA_ENV, DEFAULT_DATA_DIR)


def _number(mapping: dict[str, Any], key: str) -> float:
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be numeric")
    return float(value)


@dataclass(frozen=True)
class Capture:
    """Validated layout and waveform of one case directory."""

    case: str
    root: Path
    binary_paths: tuple[Path, ...]
    shape: tuple[int, int, int]
    sample_rate_hz: float
    chirp_period_s: float
    slope_hz_per_s: float
    center_frequency_hz: float
    sampled_bandwidth_hz: float
    pre_payload_s: float
    rx_gain_db: float

    @property
    def n_frames(self) -> int:
        return len(self.binary_paths)

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

    def range_axis(self, padding: int = 1) -> FloatArray:
        """Apparent range of a real-sample range FFT of ``padding`` x length."""
        beat_hz = np.fft.rfftfreq(padding * self.n_samples, 1 / self.sample_rate_hz)
        return np.asarray(SPEED_OF_LIGHT * beat_hz / (2 * self.slope_hz_per_s))

    def doppler_axis(self) -> FloatArray:
        """Slow-time frequency of unshifted native Doppler bins."""
        return np.asarray(np.fft.fftfreq(self.n_chirps, self.chirp_period_s))

    def far_doppler(self) -> npt.NDArray[np.bool_]:
        """Unshifted native Doppler bins with |f_D| above FAR_DOPPLER_HZ."""
        return np.asarray(np.abs(self.doppler_axis()) > FAR_DOPPLER_HZ)

    def beat_frequency_hz(self, range_m: npt.ArrayLike) -> FloatArray:
        """Beat frequency of a return at apparent ``range_m``."""
        return np.asarray(
            2 * self.slope_hz_per_s * np.asarray(range_m, dtype=float) / SPEED_OF_LIGHT
        )


def load_capture(
    case: str, data: Path | None = None, *, verify: bool = False
) -> Capture:
    """Load and validate one case directory; ``verify`` also checks SHA-256."""
    root = resolve_data_dir(data) / case
    manifest = json.loads((root / "manifest.json").read_text())
    entries = manifest["captures"]
    if not entries:
        raise ValueError(f"no captures listed in {root / 'manifest.json'}")
    first = json.loads((root / entries[0]["metadata_file"]).read_text())
    waveform = first["actual_waveform"]
    if first["dtype"] != "<i2" or first["sample_type"] != "real":
        raise ValueError("only real little-endian int16 input is supported")
    if first["axis_order"] != ["chirp", "sample", "rx"]:
        raise ValueError("expected axes [chirp, sample, rx]")
    shape = tuple(int(value) for value in first["shape"])
    if len(shape) != 3 or shape[2] != N_RX:
        raise ValueError(f"unexpected sample shape {shape}")
    expected_bytes = math.prod(shape) * np.dtype("<i2").itemsize

    binary_paths = []
    for index, entry in enumerate(entries):
        metadata = json.loads((root / entry["metadata_file"]).read_text())
        if int(entry["index"]) != index:
            raise ValueError(f"non-contiguous capture numbering in {root}")
        for key in ("dtype", "sample_type", "axis_order", "shape", "actual_waveform"):
            if metadata[key] != first[key]:
                raise ValueError(f"{key} changes at {entry['metadata_file']}")
        binary_path = root / str(entry["data_file"])
        size = binary_path.stat().st_size if binary_path.is_file() else -1
        if not size == expected_bytes == metadata["bytes"] == entry["bytes"]:
            raise ValueError(f"missing or incorrectly sized binary {binary_path}")
        if verify:
            digest = hashlib.sha256(binary_path.read_bytes()).hexdigest()
            if not digest == metadata["sha256"] == entry["sha256"]:
                raise ValueError(f"SHA-256 mismatch for {binary_path}")
        binary_paths.append(binary_path)

    gains = {float(gain) for gain in waveform["rx_gain_db"]}
    if len(gains) != 1:
        raise ValueError("RX gains differ between channels")
    return Capture(
        case=case,
        root=root,
        binary_paths=tuple(binary_paths),
        shape=(shape[0], shape[1], shape[2]),
        sample_rate_hz=_number(first["settings"], "sample_rate_msps") * 1e6,
        chirp_period_s=_number(waveform, "chirp_period_us") * 1e-6,
        slope_hz_per_s=_number(waveform, "slope_hz_per_s"),
        center_frequency_hz=_number(waveform, "adc_center_frequency_hz"),
        sampled_bandwidth_hz=_number(waveform, "adc_bandwidth_hz"),
        pre_payload_s=_number(waveform, "pre_payload_us") * 1e-6,
        rx_gain_db=gains.pop(),
    )


def range_window(length: int) -> FloatArray:
    """Periodic Blackman-Harris window for fast time."""
    return np.asarray(get_window("blackmanharris", length), dtype=float)


def doppler_window(length: int) -> FloatArray:
    """Periodic Hann window for slow time."""
    return np.asarray(get_window("hann", length), dtype=float)


def range_spectrum(raw: FloatArray, padding: int = 1) -> ComplexArray:
    """Windowed, normalized real-sample range FFT along axis 1."""
    weights = range_window(raw.shape[1])
    shape = [1] * raw.ndim
    shape[1] = weights.size
    return np.asarray(
        rfft(raw * weights.reshape(shape), n=padding * raw.shape[1], axis=1)
        / weights.sum()
    )


def slow_time_spectrum(
    values: npt.ArrayLike, weights: FloatArray | None = None
) -> ComplexArray:
    """Windowed, normalized, unshifted FFT along axis 0 (slow time)."""
    array = np.asarray(values)
    weights = doppler_window(array.shape[0]) if weights is None else weights
    shape = [1] * array.ndim
    shape[0] = weights.size
    return np.asarray(fft(array * weights.reshape(shape), axis=0) / weights.sum())


def chirp_gains(
    raw: FloatArray, beat_hz: FloatArray, sample_rate_hz: float
) -> ComplexArray:
    """Per-chirp complex amplitude of each return, [chirp, return, RX].

    The range spectrum at each return's exact beat frequency, with the
    Blackman-Harris range window.
    """
    return carkit_common.chirp_gains(
        raw, beat_hz, sample_rate_hz, range_window(raw.shape[1])
    )


def read_summary(step: str) -> dict[str, Any]:
    """Read the summary.json written by an earlier pipeline step."""
    path = GENERATED_DIR / step / "summary.json"
    if not path.is_file():
        raise SystemExit(f"{path} not found; run outdoor_{step}.py first")
    summary: dict[str, Any] = json.loads(path.read_text())
    return summary
