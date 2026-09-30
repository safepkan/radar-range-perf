"""Shared capture loading, spectra and conventions for the outdoor reflector study.

The raw data are four directories, one per waveform and nominal reflector
distance, each with ten CPIs of real int16 ADC samples ordered [chirp, sample,
RX], a JSON sidecar per CPI and a manifest. Their location is taken from
``--data``, else ``$PHASE_NOISE_OUTDOOR_DATA``, else
``~/Data/carkit/2026-09-22_phase_noise_outdoor_reflector``.

Range spectra use a periodic Blackman-Harris window and slow-time spectra a
periodic Hann window. Both are normalized by the window sum, so a tone's peak
amplitude is independent of the window. Only the physical (positive) half of
the real-sampled range spectrum is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.fft import fft, rfft
from scipy.signal import get_window

from radarperf.units import SPEED_OF_LIGHT as SPEED_OF_LIGHT

FloatArray = npt.NDArray[np.float64]
ComplexArray = npt.NDArray[np.complex128]

STUDY_DIR = Path(__file__).parent
GENERATED_DIR = STUDY_DIR / "generated"
DATA_ENV = "PHASE_NOISE_OUTDOOR_DATA"
DEFAULT_DATA_DIR = (
    Path.home() / "Data" / "carkit" / "2026-09-22_phase_noise_outdoor_reflector"
)

# Folder name -> nominal reflector distance. The folder names are the only
# record of the setting; apparent ranges come from the data.
CASES: dict[str, float] = {
    "400MHz-5m": 5.0,
    "400MHz-10m": 10.0,
    "800MHz-5m": 5.0,
    "800MHz-10m": 10.0,
}
N_RX = 8
ADC_BITS = 12

# The reflector is the strongest static return in this window around the
# nominal distance.
REFLECTOR_GATE_M = (-2.0, 3.0)
# Remote Doppler: excludes the carrier, its window response and slow drift.
FAR_DOPPLER_HZ = 5000.0
# Per-CPI polynomial removed from phase and amplitude before slow-time spectra.
DETREND_ORDER = 3
# Adjacent positive-frequency bins averaged together (with their negative
# mirrors) for display only.
DISPLAY_GROUP = 8


def db(value: npt.ArrayLike) -> FloatArray:
    """Convert positive power-like values to dB."""
    return np.asarray(10 * np.log10(np.maximum(value, np.finfo(float).tiny)))


def data_argument(parser: argparse.ArgumentParser) -> None:
    """Add the optional raw-data directory argument."""
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help=f"raw data directory (default: ${DATA_ENV} or {DEFAULT_DATA_DIR})",
    )


def resolve_data_dir(data: Path | None) -> Path:
    """Return the raw data directory from argument, environment or default."""
    root = data or Path(os.environ.get(DATA_ENV, DEFAULT_DATA_DIR))
    if not root.is_dir():
        raise SystemExit(
            f"raw data not found at {root}; pass --data or set ${DATA_ENV}"
        )
    return root


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


def enbw_bins(weights: FloatArray) -> float:
    """Equivalent noise bandwidth of a window in bins."""
    return float(weights.size * np.sum(weights**2) / np.sum(weights) ** 2)


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

    Each chirp is projected onto a Blackman-Harris-windowed tone at the
    return's beat frequency, i.e. the range spectrum evaluated at that exact
    frequency rather than at the nearest bin.
    """
    n_samples = raw.shape[1]
    weights = range_window(n_samples)
    time = np.arange(n_samples) / sample_rate_hz
    tones = np.exp(-2j * np.pi * np.outer(beat_hz, time)) * weights / weights.sum()
    return np.asarray(np.einsum("csr,ks->ckr", raw, tones))


def detrend(values: FloatArray, order: int = DETREND_ORDER) -> FloatArray:
    """Remove a least-squares polynomial along axis 0 from every column."""
    basis = np.polynomial.polynomial.polyvander(
        np.linspace(-1, 1, values.shape[0]), order
    )
    flat = values.reshape(values.shape[0], -1)
    fitted = basis @ np.linalg.lstsq(basis, flat, rcond=None)[0]
    return np.asarray((flat - fitted).reshape(values.shape))


def linear_rate(values: FloatArray, step: float) -> FloatArray:
    """Least-squares slope along axis 0 per unit of ``step`` spacing."""
    time = (np.arange(values.shape[0]) - (values.shape[0] - 1) / 2) * step
    flat = values.reshape(values.shape[0], -1)
    slope = time @ (flat - flat.mean(axis=0)) / np.sum(time**2)
    return np.asarray(slope.reshape(values.shape[1:]))


def cross_channel_power(spectrum: ComplexArray) -> FloatArray:
    """Mean of Re(F_r conj(F_s)) over distinct RX pairs; RX on the last axis.

    Independent per-RX noise averages to zero in expectation, so this
    estimates the power of the component common to all channels.
    """
    n = spectrum.shape[-1]
    total = spectrum.sum(axis=-1)
    own = np.sum(np.abs(spectrum) ** 2, axis=-1)
    return np.asarray((np.abs(total) ** 2 - own) / (n * (n - 1)))


def cross_channel_cross(first: ComplexArray, second: ComplexArray) -> FloatArray:
    """Mean of Re(F_r conj(G_s)) over distinct RX pairs; RX on the last axis."""
    n = first.shape[-1]
    mixed = first.sum(axis=-1) * np.conj(second.sum(axis=-1))
    own = np.sum(first * np.conj(second), axis=-1)
    return np.asarray(((mixed - own) / (n * (n - 1))).real)


def delay_s(range_m: npt.ArrayLike) -> FloatArray:
    """Round-trip delay of apparent (beat-derived) range."""
    return np.asarray(2 * np.asarray(range_m, dtype=float) / SPEED_OF_LIGHT)


def display_groups(
    doppler_hz: FloatArray, values: FloatArray
) -> tuple[FloatArray, FloatArray]:
    """Average unshifted positive/negative mirror bins, then DISPLAY_GROUP bins."""
    n = doppler_hz.size
    positive = np.flatnonzero(doppler_hz > 0)
    groups = positive[: positive.size // DISPLAY_GROUP * DISPLAY_GROUP].reshape(
        -1, DISPLAY_GROUP
    )
    mirrored = 0.5 * (values[groups] + values[(-groups) % n])
    return (
        np.asarray(doppler_hz[groups].mean(axis=1)),
        np.asarray(mirrored.mean(axis=1)),
    )


def read_summary(step: str) -> dict[str, Any]:
    """Read the summary.json written by an earlier pipeline step."""
    path = GENERATED_DIR / step / "summary.json"
    if not path.is_file():
        raise SystemExit(f"{path} not found; run outdoor_{step}.py first")
    summary: dict[str, Any] = json.loads(path.read_text())
    return summary


def write_summary(output: Path, summary: dict[str, Any]) -> None:
    """Write summary.json and echo it."""
    output.mkdir(parents=True, exist_ok=True)
    text = json.dumps(summary, indent=2) + "\n"
    (output / "summary.json").write_text(text)
    print(text, end="")
