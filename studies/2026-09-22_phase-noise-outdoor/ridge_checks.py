"""Check Doppler-window leakage and normalize strong-return ridges individually.

Run after analyze.py and diagnostics.py; raw inputs are read only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import get_window

from analyze import db
from radarperf.units import SPEED_OF_LIGHT


def check(folder: Path, summary: dict[str, Any]) -> dict[str, Any]:
    nc, ns, _ = summary["shape"]
    rx = int(summary["rx"]) - 1
    fs = float(summary["sample_rate_hz"])
    period = float(summary["waveform"]["chirp_period_us"]) * 1e-6
    slope = float(summary["waveform"]["slope_hz_per_s"])
    ranges = np.asarray(summary["phase_return_ranges_m"])
    native_ranges = np.fft.rfftfreq(ns, 1 / fs) * SPEED_OF_LIGHT / (2 * slope)
    bins = np.argmin(abs(native_ranges[:, None] - ranges), axis=0)
    wr = np.asarray(get_window("blackmanharris", ns))
    hann = np.asarray(get_window("hann", nc))
    bh = np.asarray(get_window("blackmanharris", nc))
    enbw_ratio = (np.sum(bh**2) / bh.sum() ** 2) / (np.sum(hann**2) / hann.sum() ** 2)
    keep = abs(np.fft.fftfreq(nc, period)) > 5000
    poly = np.polynomial.polynomial.polyvander(np.linspace(-1, 1, nc), 3)
    projector = np.linalg.pinv(poly)
    tones = (
        np.exp(
            -2j
            * np.pi
            * (2 * slope * ranges[:, None] / SPEED_OF_LIGHT)
            * np.arange(ns)
            / fs
        )
        * wr
        / wr.sum()
    )
    values = []
    for path in sorted(folder.glob("frame-*.bin")):
        meta = json.loads(path.with_suffix(".json").read_text())
        x = np.fromfile(path, dtype=meta["dtype"]).reshape(meta["shape"])[:, :, rx]
        native = (np.fft.rfft(x * wr, axis=1) / wr.sum())[:, bins]
        amplitude = abs(native)
        phase = np.unwrap(np.angle(native), axis=0)
        smooth = (poly @ (projector @ amplitude)) * np.exp(
            1j * (poly @ (projector @ phase))
        )
        rd = np.fft.fft(native * hann[:, None], axis=0) / hann.sum()
        rd_bh = np.fft.fft(native * bh[:, None], axis=0) / bh.sum()
        leakage = np.fft.fft(smooth * hann[:, None], axis=0) / hann.sum()
        exact = x @ tones.T
        phi = np.unwrap(np.angle(exact), axis=0)
        amp = abs(exact) / np.mean(abs(exact), axis=0) - 1
        phi -= poly @ (projector @ phi)
        amp -= poly @ (projector @ amp)
        phi_fft = np.fft.fft(phi * hann[:, None], axis=0) / hann.sum()
        amp_fft = np.fft.fft(amp * hann[:, None], axis=0) / hann.sum()
        values.append(
            np.stack(
                (
                    abs(rd[0]) ** 2,
                    np.mean(abs(rd[keep]) ** 2, axis=0),
                    np.mean(abs(rd_bh[keep]) ** 2, axis=0) / enbw_ratio,
                    np.mean(abs(leakage[keep]) ** 2, axis=0),
                    np.mean(abs(phi_fft[keep]) ** 2, axis=0),
                    np.mean(abs(amp_fft[keep]) ** 2, axis=0),
                )
            )
        )
    mean = np.mean(values, axis=0)
    return {
        "case": folder.name,
        "rx": rx + 1,
        "band": "Mean power per Hann Doppler bin, |Doppler| > 5 kHz",
        "returns": [
            {
                "range_m": float(r),
                "peak_db_counts2": float(db(mean[0, k])),
                "ridge_dbc_own_peak": float(db(mean[1, k] / mean[0, k])),
                "bh_vs_hann_enbw_corrected_db": float(db(mean[2, k] / mean[1, k])),
                "smooth_leakage_dbc": float(db(mean[3, k] / mean[0, k])),
                "phase_over_amplitude_db": float(db(mean[4, k] / mean[5, k])),
            }
            for k, r in enumerate(ranges)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("local/phase_noise_outdoor")
    )
    args = parser.parse_args()
    results = []
    for path in sorted(args.output.glob("*MHz-*m.json")):
        summary = json.loads(path.read_text())
        results.append(check(args.input / summary["case"], summary))
    rendered = json.dumps(results, indent=2) + "\n"
    (args.output / "ridge_checks.json").write_text(rendered)
    print(rendered)


if __name__ == "__main__":
    main()
