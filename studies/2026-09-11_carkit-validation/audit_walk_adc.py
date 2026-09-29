"""Independent checks of averaging order, local noise and RX spectral nulls.

Uses the original analysis CSV only for target coordinates and selection.
Recomputes signal and noise from ADC samples in the two inspected walk legs.
Run after analyze_walk_adc.py; outputs remain separate under generated/audit.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from scipy.fft import fft, fftshift, rfft
from scipy.signal.windows import blackman

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).parent / "generated/walk_adc/per_frame.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "generated/audit",
    )
    args = parser.parse_args()
    with args.csv.open() as stream:
        rows = list(csv.DictReader(stream))
    ranges = np.array([float(row["range_m"]) for row in rows])
    velocities = np.array([float(row["velocity_mps"]) for row in rows])
    frames = np.array([int(row["frame"]) for row in rows])
    snr = np.array([[float(row[f"rx{i}_snr_db"]) for i in range(1, 9)] for row in rows])
    corrections = np.array(
        [
            [float(row[f"rx{i}_local_to_far_noise_db"]) for i in range(1, 9)]
            for row in rows
        ]
    )
    masks = {
        "selected37": np.array([row["selected"] == "True" for row in rows]),
        "inbound39": (frames >= 89) & (frames <= 127),
        "inbound41": (frames >= 89) & (frames <= 129),
        "outbound45": (frames >= 26) & (frames <= 70),
    }
    range_correction = 40 * np.log10(ranges / 100)
    summary: dict[str, Any] = {"averaging": {}, "adc_checks": {}, "patch_checks": []}
    for name, mask in masks.items():
        item: dict[str, Any] = {"count": int(mask.sum())}
        for label, values in [("far", snr), ("broad_local", snr - corrections)]:
            per_frame_mean = 10 * np.log10(np.mean(10 ** (values / 10), axis=1))
            anchor = per_frame_mean[mask] + range_correction[mask]
            item[label] = {
                "dB_mean_channels_and_frames": float(
                    np.mean(values[mask] + range_correction[mask, None])
                ),
                "linear_mean_channels_then_dB_fit": float(anchor.mean()),
                "linear_mean_channels_and_range_normalized_frames": float(
                    10 * np.log10(np.mean(10 ** (anchor / 10)))
                ),
            }
        summary["averaging"][name] = item

    first = json.loads((args.data / "cpi_0000000000.json").read_text())
    wf = first["waveform"]
    shape = tuple(first["sample_format"]["shape"])
    sample_rate = wf["sample_rate_msps"] * 1e6
    pri = wf["chirp_period_us"] * 1e-6
    slope = wf["slope_hz_per_s"]
    c = 299792458.0
    carrier = 76.374237e9
    range_axis = np.fft.rfftfreq(2048, 1 / sample_rate) * c / (2 * slope)
    velocity_axis = fftshift(np.fft.fftfreq(4096, pri)) * c / (2 * carrier)
    native_velocity = np.fft.fftfreq(1024, pri) * c / (2 * carrier)
    wr = blackman(512, sym=False).astype(np.float32)
    wd = blackman(1024, sym=False).astype(np.float32)
    far = range_axis >= 0.75 * range_axis[-1]
    direct = np.full_like(snr, np.nan)
    target_local = {v: np.full_like(snr, np.nan) for v in (10, 20, 30)}
    checked = masks["inbound41"] | masks["outbound45"]
    peak_examples = {40, 89, 100, 101, 105, 127}
    maximum_power_error_db = 0.0
    hashes_checked = 0
    args.output.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        metadata = json.loads((args.data / f"cpi_{frame:010d}.json").read_text())
        if (
            metadata["waveform"] != wf
            or metadata["sample_format"] != first["sample_format"]
        ):
            raise ValueError(f"metadata varies at frame {frame}")
        contents = (args.data / metadata["file"]).read_bytes()
        if hashlib.sha256(contents).hexdigest() != metadata["sha256"]:
            raise ValueError(f"hash mismatch at frame {frame}")
        hashes_checked += 1
        if not checked[index]:
            continue
        raw = np.frombuffer(contents, dtype="<i2").reshape(shape)
        fr = rfft(raw.astype(np.float32) * wr[None, :, None], n=2048, axis=1) / wr.sum()
        native = fft(fr * wd[:, None, None], axis=0) / wd.sum()
        far_noise = np.mean(
            np.abs(native[np.abs(native_velocity) >= 1][:, far]) ** 2, axis=(0, 1)
        )
        near = np.abs(range_axis - ranges[index]) <= 2.0
        vnear = np.abs(velocity_axis - velocities[index]) <= 1.0
        patch_all_v = (
            fftshift(fft(fr[:, near] * wd[:, None, None], n=4096, axis=0), axes=0)
            / wd.sum()
        )
        patch = patch_all_v[vnear]
        power = np.abs(patch) ** 2
        iv = int(np.argmin(np.abs(velocity_axis[vnear] - velocities[index])))
        ir = int(np.argmin(np.abs(range_axis[near] - ranges[index])))
        central = power[iv, ir]
        direct[index] = 10 * np.log10(central / far_noise)
        maximum_power_error_db = max(
            maximum_power_error_db, float(np.max(np.abs(direct[index] - snr[index])))
        )
        # Same range as target, averaging +/- one unpadded range bin, far in Doppler.
        noise_range = np.abs(range_axis - ranges[index]) <= 4.01 * (
            range_axis[1] - range_axis[0]
        )
        for cutoff, values in target_local.items():
            noise = np.mean(
                np.abs(native[np.abs(native_velocity) >= cutoff][:, noise_range]) ** 2,
                axis=(0, 1),
            )
            values[index] = 10 * np.log10(central / noise)
        if frame in peak_examples:
            integrated = power.sum(axis=(0, 1))
            own_peak = power.max(axis=(0, 1))
            sv = np.linalg.svd(patch.reshape(-1, 8), compute_uv=False) ** 2
            background = native[np.abs(native_velocity) >= 10][:, noise_range].reshape(
                -1, 8
            )
            covariance = background.T @ background.conj() / len(background)
            eigenvalues, eigenvectors = np.linalg.eigh(covariance)
            target = patch[iv, ir]
            alignment = float(
                np.abs(np.vdot(eigenvectors[:, -1], target)) ** 2
                / np.vdot(target, target).real
            )
            reference_range = (np.abs(range_axis - ranges[index]) > 4) & (
                np.abs(range_axis - ranges[index]) < 8
            )
            off_target_noise = np.mean(
                np.abs(native[np.abs(native_velocity) >= 10][:, reference_range]) ** 2,
                axis=(0, 1),
            )
            summary["patch_checks"].append(
                {
                    "frame": int(frame),
                    "central_power_relative_to_strongest_rx_db": (
                        10 * np.log10(central / central.max())
                    ).tolist(),
                    "integrated_patch_relative_to_strongest_rx_db": (
                        10 * np.log10(integrated / integrated.max())
                    ).tolist(),
                    "own_patch_peak_uplift_db": (
                        10 * np.log10(own_peak / central)
                    ).tolist(),
                    "patch_singular_energy_fractions": (sv / sv.sum()).tolist(),
                    "background_largest_eigenvalue_fraction": float(
                        eigenvalues[-1] / eigenvalues.sum()
                    ),
                    "background_dominant_mode_target_alignment_squared": alignment,
                    "background_target_range_over_nearby_range_db": float(
                        10
                        * np.log10(np.mean(np.diag(covariance).real / off_target_noise))
                    ),
                }
            )
        if frame == 100:
            figure, axis = plt.subplots(figsize=(10, 5), constrained_layout=True)
            lines = 10 * np.log10(power[:, ir, :] / central.max())
            for channel in range(8):
                axis.plot(
                    velocity_axis[vnear], lines[:, channel], label=f"RX{channel + 1}"
                )
            axis.axvline(
                velocities[index], color="black", linestyle=":", label="common cell"
            )
            axis.set(
                xlabel="Radial velocity [m/s]",
                ylabel="Power relative to strongest RX at common cell [dB]",
                ylim=(-50, 3),
                title="CPI 100: per-RX Doppler cuts at common target range",
            )
            axis.legend(ncol=3)
            axis.grid(alpha=0.3)
            figure.savefig(args.output / "cpi100_doppler.png", dpi=160)
            plt.close(figure)
        if index % 20 == 0:
            print(f"audited frame {frame}", flush=True)
    summary["adc_checks"] = {
        "sha256_and_metadata_pairs_checked": hashes_checked,
        "maximum_recomputed_cell_snr_difference_db": maximum_power_error_db,
        "target_local_smoothing_half_width_m": float(
            4 * (range_axis[1] - range_axis[0])
        ),
        "target_local_noise_sensitivity": {},
    }
    for cutoff, values in target_local.items():
        result: dict[str, float] = {}
        for name in ("selected37", "inbound39", "inbound41", "outbound45"):
            mask = masks[name]
            perframe = 10 * np.log10(np.mean(10 ** (values[mask] / 10), axis=1))
            result[name] = float(np.mean(perframe + range_correction[mask]) - 1.27)
        summary["adc_checks"]["target_local_noise_sensitivity"][str(cutoff)] = result
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary["averaging"], indent=2))
    print(json.dumps(summary["adc_checks"], indent=2))


if __name__ == "__main__":
    main()
