"""Capture loading and constants for the out-of-window captures.

Two recordings from the office window, both with the study's single CARKIT
unit:

- 2026-09-30, our own firmware: eleven case directories named
  <waveform>-<TX>-<backoff>[-suffix], each with up to ten CPIs of real int16
  ADC samples ordered [chirp, sample, RX] and a JSON sidecar per CPI. Their
  location is taken from ``--data``, else ``$CARKIT_WINDOW_DATA``, else
  ``~/Data/carkit/2026-09-30_out-the_window``. Other recordings in this format
  (the 2026-10-02 window captures, the field and highway captures) load the
  same way with ``--data`` and their own case names; a capture's recording is
  the date of its first CPI.
- 2026-08-27, Infineon's firmware and RadarGUI, 8TX DDMA, alternating between
  two modes frame by frame. Recorded in Infineon's packet format and converted
  once by window_convert_infineon.m (l2-sp's CARKIT decoder) to the same sample
  layout with a sidecar per frame. Its location is taken from
  ``--infineon-data``, else ``$CARKIT_WINDOW_INFINEON_DATA``, else
  ``~/Data/carkit/2026-08-27_test_out_of_office_window/converted_adc``. The two
  modes are the cases ``infineon-mode0`` and ``infineon-mode1``.

The windows are the outdoor captures': periodic Blackman-Harris in range (also
for per-chirp amplitudes) and periodic Hann in Doppler, normalized by their sums.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.signal import find_peaks

import carkit_common
from carkit_common import N_RX, SPEED_OF_LIGHT, STUDY_DIR, ComplexArray, FloatArray
from outdoor_common import (  # noqa: F401 (re-exported for the window steps)
    doppler_window as doppler_window,
    range_spectrum as range_spectrum,
    range_window as range_window,
    slow_time_spectrum as slow_time_spectrum,
)

GENERATED_DIR = STUDY_DIR / "generated" / "window"
DATA_ENV = "CARKIT_WINDOW_DATA"
DEFAULT_DATA_DIR = Path.home() / "Data" / "carkit" / "2026-09-30_out-the_window"
INFINEON_ENV = "CARKIT_WINDOW_INFINEON_DATA"
DEFAULT_INFINEON_DIR = (
    Path.home()
    / "Data"
    / "carkit"
    / "2026-08-27_test_out_of_office_window"
    / "converted_adc"
)

# 2026-09-30 case directories. The names are the only record of the intended
# setting; the sidecars say what was configured.
CASES = (
    "long-8TX-0dB",
    "medium-1TX-0dB",
    "medium-1TX-10dB",
    "medium-8TX-0dB",
    "short-1TX-0dB",
    "short-1TX-10dB",
    "short-8TX-0dB",
    "long-1TX-0dB",
    "medium-8TX-0dB-highway",
    "medium-8TX-0dB-2",
    "short-8TX-0dB-2",
)
INFINEON_CASES = ("infineon-mode0", "infineon-mode1")
ALL_CASES = CASES + INFINEON_CASES
ADC_BITS = 12

# Static profiles are padded this many times in range.
PADDING = 8
# Remote Doppler for the receiver background: excludes the static scene, its
# window response and slow motion, but not the traffic, which the channel-
# independent estimate rejects.
FAR_DOPPLER_HZ = 1000.0
# Static returns: nearest range and number kept per case.
MIN_RETURN_RANGE_M = 10.0
MAX_RETURNS = 30


def data_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the optional raw-data directory arguments."""
    carkit_common.data_argument(parser, DATA_ENV, DEFAULT_DATA_DIR)
    parser.add_argument(
        "--infineon-data",
        type=Path,
        default=None,
        help=f"converted 2026-08-27 recording (default: ${INFINEON_ENV} or "
        f"{DEFAULT_INFINEON_DIR})",
    )


@dataclass(frozen=True)
class Capture:
    """Validated layout and configuration of one case."""

    case: str
    recording: str
    firmware: str
    binary_paths: tuple[Path, ...]
    sha256: tuple[str, ...]
    timestamps: tuple[str, ...]
    # CPI start times relative to the first CPI, from the board: CPI index
    # times the configured interval (ours), or the frame time stamp (Infineon's).
    cpi_times_s: tuple[float, ...]
    shape: tuple[int, int, int]
    sample_rate_hz: float
    chirp_period_s: float
    slope_hz_per_s: float
    start_frequency_hz: float
    sampled_bandwidth_hz: float
    pre_payload_s: float
    payload_s: float
    flyback_s: float
    wait_s: float
    tx_channels: tuple[int, ...]
    coherent_tx: bool
    tx_backoff_db: float
    rx_setting: str
    # Slow-time lines of a static return, in cycles per chirp: DDMA slots and
    # their count (one slot at zero without DDMA), and the carrier step between
    # chirps, which moves every line by step * delay.
    ddma_slots: tuple[int, ...]
    ddma_length: int
    frequency_step_hz: float
    notes: tuple[str, ...]

    @property
    def n_frames(self) -> int:
        return len(self.binary_paths)

    @property
    def n_chirps(self) -> int:
        return self.shape[0]

    @property
    def n_samples(self) -> int:
        return self.shape[1]

    @property
    def center_frequency_hz(self) -> float:
        """Centre of the sampled sweep."""
        return self.start_frequency_hz + self.sampled_bandwidth_hz / 2

    @property
    def family(self) -> str:
        """Waveform family: short, medium, long or infineon."""
        return self.case.split("-")[0]

    def load(self, frame: int) -> FloatArray:
        """Load one CPI as float64 [chirp, sample, RX] without other changes."""
        raw = np.fromfile(self.binary_paths[frame], dtype="<i2")
        return np.asarray(raw.reshape(self.shape), dtype=float)

    def verify(self) -> None:
        """Check every binary against its sidecar's SHA-256."""
        for path, digest in zip(self.binary_paths, self.sha256):
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError(f"SHA-256 mismatch for {path}")

    def range_axis(self, padding: int = 1) -> FloatArray:
        """Apparent range of a real-sample range FFT of ``padding`` x length."""
        beat_hz = np.fft.rfftfreq(padding * self.n_samples, 1 / self.sample_rate_hz)
        return np.asarray(SPEED_OF_LIGHT * beat_hz / (2 * self.slope_hz_per_s))

    def doppler_axis(self) -> FloatArray:
        """Slow-time frequency of unshifted native Doppler bins."""
        return np.asarray(np.fft.fftfreq(self.n_chirps, self.chirp_period_s))

    def beat_frequency_hz(self, range_m: npt.ArrayLike) -> FloatArray:
        """Beat frequency of a return at apparent ``range_m``."""
        return np.asarray(
            2 * self.slope_hz_per_s * np.asarray(range_m, dtype=float) / SPEED_OF_LIGHT
        )

    def static_lines(self, delay_s: npt.ArrayLike) -> FloatArray:
        """Slow-time lines [return, line] of static returns, cycles per chirp."""
        skew = self.frequency_step_hz * np.asarray(delay_s, dtype=float)
        slots = np.array(self.ddma_slots) / self.ddma_length
        return np.asarray((slots[None, :] + skew[:, None]) % 1)


def resolve_data_dir(data: Path | None) -> Path:
    """Return the 2026-09-30 directory from argument, environment or default."""
    return carkit_common.resolve_data_dir(data, DATA_ENV, DEFAULT_DATA_DIR)


def resolve_infineon_dir(data: Path | None) -> Path:
    """Return the converted 2026-08-27 directory."""
    return carkit_common.resolve_data_dir(data, INFINEON_ENV, DEFAULT_INFINEON_DIR)


def _number(mapping: dict[str, Any], key: str) -> float:
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be numeric")
    return float(value)


def _check_layout(
    shape: tuple[int, ...], axes: list[str], dtype: str, path: Path
) -> tuple[int, int, int]:
    if axes != ["chirp", "sample", "rx"] or len(shape) != 3 or shape[2] != N_RX:
        raise ValueError(f"unexpected layout {axes} {shape} in {path}")
    if dtype not in ("int16", "<i2"):
        raise ValueError(f"unexpected sample type {dtype} in {path}")
    return shape[0], shape[1], shape[2]


def _load_own(case: str, data: Path | None) -> Capture:
    root = resolve_data_dir(data) / case
    sidecars = sorted(root.glob("*.json"))
    if not sidecars:
        raise ValueError(f"no CPI sidecars in {root}")
    metadata = [json.loads(path.read_text()) for path in sidecars]
    first = metadata[0]
    fmt = first["sample_format"]
    if fmt["byte_order"] != "little":
        raise ValueError(f"expected little-endian samples in {root}")
    shape = _check_layout(tuple(fmt["shape"]), fmt["axes"], fmt["dtype"], root)
    expected_bytes = math.prod(shape) * 2
    paths = []
    for entry in metadata:
        for key in ("sample_format", "settings", "actual_waveform", "waveform"):
            if entry[key] != first[key]:
                raise ValueError(f"{key} changes within {root}")
        path = root / str(entry["file"])
        size = path.stat().st_size if path.is_file() else -1
        if not size == expected_bytes == entry["adc_bytes"]:
            raise ValueError(f"missing or incorrectly sized binary {path}")
        paths.append(path)

    actual = first["actual_waveform"]
    settings = first["settings"]
    cpis = [int(entry["cpi"]) for entry in metadata]
    notes = []
    missing = sorted(set(range(int(first["requested_cpis"]))) - set(cpis))
    if missing:
        notes.append(f"CPIs {missing} of {first['requested_cpis']} missing")
    tx_channels = tuple(int(tx) for tx in actual["tx_channels"])
    named = re.search(r"(\d+)TX", case)
    named_tx = int(named.group(1)) if named else len(tx_channels)
    if named_tx != len(tx_channels):
        notes.append(
            f"named {named_tx}TX, configured TX {list(tx_channels)}; firmware "
            f"{first['fw_version']}"
        )
    return Capture(
        case=case,
        recording=str(first["timestamp"])[:10],
        firmware=str(first["fw_version"]),
        binary_paths=tuple(paths),
        sha256=tuple(str(entry["sha256"]) for entry in metadata),
        timestamps=tuple(str(entry["timestamp"]) for entry in metadata),
        cpi_times_s=tuple(
            (int(entry["cpi"]) - cpis[0])
            * _number(first["waveform"], "cpi_start_interval_us")
            * 1e-6
            for entry in metadata
        ),
        shape=shape,
        sample_rate_hz=_number(settings, "sample_rate_msps") * 1e6,
        chirp_period_s=_number(first["waveform"], "chirp_period_us") * 1e-6,
        slope_hz_per_s=_number(actual, "slope_hz_per_s"),
        start_frequency_hz=_number(actual, "adc_start_frequency_hz"),
        sampled_bandwidth_hz=_number(actual, "adc_bandwidth_hz"),
        pre_payload_s=_number(actual, "pre_payload_us") * 1e-6,
        payload_s=_number(actual, "payload_us") * 1e-6,
        flyback_s=_number(actual, "flyback_us") * 1e-6,
        wait_s=_number(actual, "wait_us") * 1e-6,
        tx_channels=tx_channels,
        coherent_tx=bool(settings.get("coherent", False)),
        tx_backoff_db=_number(actual, "tx_backoff_db"),
        rx_setting=f"gain {_number(actual, 'rx_gain_db'):g} dB; high-pass not recorded",
        ddma_slots=(0,),
        ddma_length=1,
        frequency_step_hz=0.0,
        notes=tuple(notes),
    )


def _load_infineon(case: str, data: Path | None) -> Capture:
    root = resolve_infineon_dir(data)
    mode = int(case.removeprefix("infineon-mode"))
    recording = json.loads((root / "recording.json").read_text())
    metadata = [
        entry
        for entry in (
            json.loads(path.read_text()) for path in sorted(root.glob("frame_*.json"))
        )
        if entry["mode"] == mode
    ]
    if not metadata:
        raise ValueError(f"no frames of mode {mode} in {root}")
    first = metadata[0]
    shape = _check_layout(tuple(first["shape"]), first["axes"], first["dtype"], root)
    expected_bytes = math.prod(shape) * 2
    paths = []
    for entry in metadata:
        for key in ("shape", "waveform_config", "tx_config", "rx_config"):
            if entry[key] != first[key]:
                raise ValueError(f"{key} changes within mode {mode} of {root}")
        path = root / str(entry["file"])
        size = path.stat().st_size if path.is_file() else -1
        if size != expected_bytes:
            raise ValueError(f"missing or incorrectly sized binary {path}")
        paths.append(path)

    waveform = first["waveform_config"]
    unit = waveform["unitWaveformConfig"]
    mode_config = first["mode_config"]
    tx = first["tx_config"]
    payload_s = _number(unit, "timePayload_sec")
    phase_length = int(mode_config["phaseModulationLength"])
    slots = tuple(int(slot) for slot in tx["ddmIndex"])
    steps = np.array(tx["phaseStepp_degree"], dtype=float)
    if not np.allclose(steps, np.array(slots) * 360 / phase_length):
        raise ValueError("DDMA phase steps do not match the slot indices")
    return Capture(
        case=case,
        recording="2026-08-27",
        firmware="Infineon CARKIT firmware and RadarGUI",
        binary_paths=tuple(paths),
        sha256=tuple(str(entry["sha256"]) for entry in metadata),
        timestamps=tuple(f"{entry['time_stamp_ms']} ms" for entry in metadata),
        cpi_times_s=tuple(
            (float(entry["time_stamp_ms"]) - float(first["time_stamp_ms"])) * 1e-3
            for entry in metadata
        ),
        shape=shape,
        sample_rate_hz=shape[1] / payload_s,
        chirp_period_s=_number(waveform, "timePri_sec"),
        slope_hz_per_s=_number(unit, "bandWidth_hz") / payload_s,
        start_frequency_hz=_number(waveform, "freqStart_hz"),
        sampled_bandwidth_hz=_number(unit, "bandWidth_hz"),
        pre_payload_s=_number(unit, "timePrepayload_sec"),
        payload_s=payload_s,
        flyback_s=_number(unit, "timeFlyback_sec"),
        wait_s=_number(unit, "timeWait_sec"),
        tx_channels=tuple(
            k + 1 for k in range(8) if int(tx["enabledTxMask"]) & (1 << k)
        ),
        coherent_tx=False,
        tx_backoff_db=_number(mode_config, "backoff_dB"),
        rx_setting=(
            f"high-pass code {first['rx_config']['hpSelection']}, gain code "
            f"{first['rx_config']['gainSelection']}"
        ),
        ddma_slots=slots,
        ddma_length=phase_length,
        frequency_step_hz=_number(waveform, "freqStep_hz"),
        notes=(
            f"converted with l2-sp {str(recording['l2sp_commit'])[:8]}",
            f"{mode_config['numOfDummy']} dummy ramp(s) per frame",
        ),
    )


def load_capture(
    case: str,
    data: Path | None = None,
    infineon_data: Path | None = None,
    *,
    verify: bool = False,
) -> Capture:
    """Load and validate one case; ``verify`` also checks SHA-256."""
    if case in INFINEON_CASES:
        capture = _load_infineon(case, infineon_data)
    elif case in CASES or (resolve_data_dir(data) / case).is_dir():
        capture = _load_own(case, data)
    else:
        raise ValueError(f"unknown case {case}")
    if verify:
        capture.verify()
    return capture


def discover_cases(data: Path | None = None) -> tuple[str, ...]:
    """Case directories of a recording in our firmware's format, by first CPI time."""
    root = resolve_data_dir(data)
    found = []
    for folder in root.iterdir():
        sidecars = sorted(folder.glob("*.json")) if folder.is_dir() else []
        if sidecars:
            first = json.loads(sidecars[0].read_text())
            if "sample_format" in first and "actual_waveform" in first:
                found.append((str(first["timestamp"]), folder.name))
    return tuple(name for _, name in sorted(found))


def case_arguments(parser: argparse.ArgumentParser, default: tuple[str, ...]) -> None:
    """Add --cases: a comma-separated list, or 'auto' to discover them in --data."""
    parser.add_argument(
        "--cases",
        default=None,
        help="comma-separated cases, or 'auto' for every case directory in --data "
        f"(default: {', '.join(default)})",
    )


def resolve_cases(
    cases: str | None, data: Path | None, default: tuple[str, ...]
) -> tuple[str, ...]:
    """The cases named by --cases, or the default."""
    if cases is None:
        return default
    if cases == "auto":
        return discover_cases(data)
    return tuple(case.strip() for case in cases.split(",") if case.strip())


def chirp_gains(
    raw: FloatArray, beat_hz: FloatArray, sample_rate_hz: float
) -> ComplexArray:
    """Per-chirp complex amplitude of each return, [chirp, return, RX].

    The range spectrum at each return's exact beat frequency, with the
    Blackman-Harris range window. The per-RX mean is removed first: the ADC
    offsets are 40-95 counts.
    """
    centred = raw - raw.mean(axis=(0, 1), keepdims=True)
    return carkit_common.chirp_gains(
        centred, beat_hz, sample_rate_hz, range_window(raw.shape[1])
    )


def per_chirp_noise(capture: Capture, floor_per_bin: FloatArray) -> FloatArray:
    """Per-chirp, per-RX noise power in the range spectrum from an RD-cell floor.

    The Hann Doppler spectrum, normalized by its sum, holds a white per-chirp
    variance times ENBW / N per cell.
    """
    enbw = carkit_common.enbw_bins(doppler_window(capture.n_chirps))
    return np.asarray(floor_per_bin * capture.n_chirps / enbw)


def static_peaks(
    range_m: FloatArray,
    snr_db: FloatArray,
    min_snr_db: float,
    min_separation_m: float,
    min_range_m: float = MIN_RETURN_RANGE_M,
    max_count: int = MAX_RETURNS,
) -> tuple[FloatArray, FloatArray]:
    """Strongest local maxima of a per-chirp SNR profile, sorted by range."""
    step = float(range_m[1] - range_m[0])
    peaks, _ = find_peaks(
        snr_db,
        height=min_snr_db,
        distance=max(1, int(min_separation_m / step)),
        prominence=3.0,
    )
    peaks = peaks[range_m[peaks] >= min_range_m]
    peaks = np.sort(peaks[np.argsort(snr_db[peaks])[::-1][:max_count]])
    return np.asarray(range_m[peaks]), np.asarray(snr_db[peaks])


def read_summary(step: str) -> dict[str, Any]:
    """Read the summary.json written by an earlier pipeline step."""
    path = GENERATED_DIR / step / "summary.json"
    if not path.is_file():
        raise SystemExit(f"{path} not found; run window_{step}.py first")
    summary: dict[str, Any] = json.loads(path.read_text())
    return summary
