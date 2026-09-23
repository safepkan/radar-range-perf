"""Read-only analysis of the outdoor reflector captures; outputs stay separate.

Run with the repository venv and MPLBACKEND=Agg. Raw captures are not bundled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from scipy.signal import find_peaks, get_window

from radarperf.units import SPEED_OF_LIGHT

FloatArray = npt.NDArray[np.float64]
ComplexArray = npt.NDArray[np.complex128]


def db(value: npt.ArrayLike) -> FloatArray:
    return np.asarray(10 * np.log10(np.maximum(value, 1e-30)))


def analyze(folder: Path, output: Path, rx: int) -> dict[str, Any]:
    manifest = json.loads((folder / "manifest.json").read_text())
    first = json.loads((folder / manifest["captures"][0]["metadata_file"]).read_text())
    nc, ns, nrx = first["shape"]
    assert first["axis_order"] == ["chirp", "sample", "rx"]
    assert first["dtype"] == "<i2" and first["sample_type"] == "real"
    assert 0 <= rx < nrx
    wf = first["actual_waveform"]
    fs = float(first["settings"]["sample_rate_msps"]) * 1e6
    slope = float(wf["slope_hz_per_s"])
    period = float(wf["chirp_period_us"]) * 1e-6
    wr = np.asarray(get_window("blackmanharris", ns))
    wd = np.asarray(get_window("hann", nc))
    fr = np.fft.rfftfreq(ns, 1 / fs)
    ranges = fr * SPEED_OF_LIGHT / (2 * slope)
    fd = np.fft.fftshift(np.fft.fftfreq(nc, period))
    high_fr = np.fft.rfftfreq(ns * 8, 1 / fs)
    high_ranges = high_fr * SPEED_OF_LIGHT / (2 * slope)
    nominal = float(folder.name.split("-")[1].removesuffix("m"))
    gate = (ranges >= nominal - 2) & (ranges <= nominal + 3)
    high_gate = (high_ranges >= nominal - 2) & (high_ranges <= nominal + 3)
    rd_sum = np.zeros((nc, ns // 2 + 1))
    single_sum = np.zeros((ns // 2 + 1, nrx))
    coherent_sum = np.zeros((ns * 4 + 1, nrx))
    residual_blocks: list[FloatArray] = []
    raw_cov = np.zeros((ns, ns))
    residual_cov = np.zeros((ns, ns))
    positive_cov = np.zeros((ns // 2 - 1, ns // 2 - 1), dtype=complex)
    high_cov = np.zeros((ns, ns), dtype=complex)
    high_positive_cov = np.zeros_like(positive_cov)
    rx_noise_cov = np.zeros((ns // 2 + 1, nrx, nrx), dtype=complex)
    fast_fd = np.fft.fftfreq(nc, period)
    high_mask = np.abs(fast_fd) > 5000
    frame_metrics: list[dict[str, Any]] = []
    rx_peak: list[FloatArray] = []
    rx_off: list[FloatArray] = []
    frame_mean: list[FloatArray] = []
    for capture in manifest["captures"]:
        meta = json.loads((folder / capture["metadata_file"]).read_text())
        assert meta["actual_waveform"] == wf
        assert meta["shape"] == first["shape"]
        assert meta["dtype"] == first["dtype"]
        assert meta["axis_order"] == first["axis_order"]
        binary = (folder / capture["data_file"]).read_bytes()
        assert len(binary) == meta["bytes"] == capture["bytes"]
        assert hashlib.sha256(binary).hexdigest() == meta["sha256"] == capture["sha256"]
        x = (
            np.frombuffer(binary, dtype=meta["dtype"])
            .reshape(meta["shape"])
            .astype(float)
        )
        assert x.size * 2 == len(binary)
        r = np.fft.rfft(x * wr[None, :, None], axis=1) / wr.sum()
        rd = (
            np.fft.fftshift(np.fft.fft(r * wd[:, None, None], axis=0), axes=0)
            / wd.sum()
        )
        power = np.abs(rd) ** 2
        far = rd[np.abs(fd) > 5000]
        rx_noise_cov += np.einsum("drx,dry->rxy", far.conj(), far) / far.shape[0]
        rd_sum += power[:, :, rx]
        single_sum += np.mean(np.abs(r) ** 2, axis=0)
        means = x.mean(axis=0)
        high = np.fft.rfft(means * wr[:, None], n=ns * 8, axis=0) / wr.sum()
        coherent_sum += np.abs(high) ** 2
        peak = np.max(power[nc // 2, gate], axis=0)
        off = np.mean(power[np.abs(fd) > 5000], axis=0)
        rx_peak.append(peak)
        rx_off.append(off)
        one = x[:, :, rx]
        centered = one - one.mean(axis=0)
        residual_blocks.append(centered)
        frame_mean.append(one.mean(axis=0))
        raw_cov += one.T @ one / nc
        residual_cov += centered.T @ centered / (nc - 1)
        positive = np.fft.rfft(centered, axis=1, norm="ortho")[:, 1:-1]
        positive_cov += positive.conj().T @ positive / (nc - 1)
        high_time = np.fft.fft(one * wd[:, None], axis=0)[high_mask] / np.sqrt(
            np.sum(wd**2)
        )
        high_cov += high_time.conj().T @ high_time / high_mask.sum()
        all_fast = np.fft.fft(high_time, axis=1, norm="ortho")[:, 1 : ns // 2]
        high_positive_cov += all_fast.conj().T @ all_fast / high_mask.sum()
        frame_metrics.append(
            {
                "index": capture["index"],
                "min": int(x.min()),
                "max": int(x.max()),
                "rail_samples": int(np.sum((x <= -2048) | (x >= 2047))),
                "peak_power": float(peak[rx]),
                "peak_range_m": float(
                    high_ranges[
                        np.flatnonzero(high_gate)[
                            np.argmax(np.abs(high[high_gate, rx]))
                        ]
                    ]
                ),
                "rx_rms_counts": np.std(x, axis=(0, 1)).tolist(),
            }
        )
    count = len(frame_metrics)
    rd_power = rd_sum / count
    single_power = single_sum / count
    coherent_power = coherent_sum / count
    peak_bin = int(np.flatnonzero(gate)[np.argmax(rd_power[nc // 2, gate])])
    peak_power = float(rd_power[nc // 2, peak_bin])
    high_peak_bin = int(
        np.flatnonzero(high_gate)[np.argmax(coherent_power[high_gate, rx])]
    )
    target_range = float(high_ranges[high_peak_bin])
    target_frequency = float(high_fr[high_peak_bin])
    eig_raw = np.linalg.eigvalsh(raw_cov / count)[::-1]
    eig_real = np.linalg.eigvalsh(residual_cov / count)[::-1]
    eig_positive, vectors = np.linalg.eigh(positive_cov / count)
    eig_positive = eig_positive[::-1]
    eig_high_real, high_vectors = np.linalg.eigh(high_cov.real / count)
    eig_high_positive, high_positive_vectors = np.linalg.eigh(high_positive_cov / count)
    # Projection onto a known target tone estimates chirp-to-chirp complex gain.
    tone = np.exp(-2j * np.pi * target_frequency * np.arange(ns) / fs) * wr / wr.sum()
    fluctuation = np.stack([block @ tone for block in residual_blocks])
    carrier = np.asarray([mean @ tone for mean in frame_mean])
    normalized = fluctuation / carrier[:, None]
    gain_cov = np.cov(np.stack((normalized.real.ravel(), normalized.imag.ravel())))
    peaks, _ = find_peaks(coherent_power[:, rx], distance=8)
    strongest = peaks[np.argsort(coherent_power[peaks, rx])[-12:][::-1]]
    off_power = np.mean(rd_power[np.abs(fd) > 5000], axis=0)
    near_power = np.mean(rd_power[(np.abs(fd) >= 500) & (np.abs(fd) <= 3000)], axis=0)
    roi = (ranges >= 2) & (ranges <= 15) & (np.abs(ranges - target_range) > 1.5)
    rx_noise_cov /= count
    diagonals = np.diagonal(rx_noise_cov, axis1=1, axis2=2).real
    rx_noise_coherence = abs(rx_noise_cov) ** 2 / (
        diagonals[:, :, None] * diagonals[:, None, :]
    )
    pairs = ~np.eye(nrx, dtype=bool)
    summary: dict[str, Any] = {
        "case": folder.name,
        "rx": rx + 1,
        "frames": count,
        "waveform": wf,
        "sample_rate_hz": fs,
        "shape": first["shape"],
        "target_range_m": target_range,
        "target_beat_hz": target_frequency,
        "peak_bin_range_m": float(ranges[peak_bin]),
        "peak_power_counts2": peak_power,
        "peak_power_db_counts2": float(db(peak_power)),
        "far_doppler_target_dbc": float(db(off_power[peak_bin] / peak_power)),
        "near_doppler_target_dbc": float(db(near_power[peak_bin] / peak_power)),
        "far_doppler_background_dbc": float(db(np.median(off_power[roi]) / peak_power)),
        "far_doppler_background_db_counts2": float(db(np.median(off_power[roi]))),
        "background_rx_coherence_median": float(
            np.median(rx_noise_coherence[roi][:, pairs])
        ),
        "target_rx_coherence_median": float(
            np.median(rx_noise_coherence[peak_bin][pairs])
        ),
        "real_residual_eigenvalues_counts2": eig_real.tolist(),
        "positive_residual_eigenvalues_counts2": eig_positive.tolist(),
        "high_doppler_real_eigenvalues_counts2": eig_high_real[::-1].tolist(),
        "high_doppler_positive_eigenvalues_counts2": eig_high_positive[::-1].tolist(),
        "target_gain_covariance": gain_cov.tolist(),
        "target_gain_rms_real": float(np.std(normalized.real)),
        "target_gain_rms_imag": float(np.std(normalized.imag)),
        "strongest_static_returns": [
            {
                "range_m": float(high_ranges[k]),
                "power_db_counts2": float(db(coherent_power[k, rx])),
            }
            for k in strongest
        ],
        "frame_metrics": frame_metrics,
    }
    np.savez_compressed(
        output / f"{folder.name}.npz",
        range_m=ranges,
        doppler_hz=fd,
        rd_power=rd_power,
        peak_power=peak_power,
        single_power=single_power,
        high_range_m=high_ranges,
        coherent_power=coherent_power,
        eig_raw=eig_raw,
        eig_real=eig_real,
        eig_positive=eig_positive,
        positive_eigenvectors=vectors[:, ::-1],
        eig_high_real=eig_high_real[::-1],
        eig_high_positive=eig_high_positive[::-1],
        high_real_vectors=high_vectors[:, ::-1],
        high_positive_vectors=high_positive_vectors[:, ::-1],
        far_doppler_power=off_power,
        near_doppler_power=near_power,
        rx_peak=np.asarray(rx_peak),
        rx_off=np.asarray(rx_off),
        target_gain=normalized,
        target_carrier=carrier,
        rx_noise_cov=rx_noise_cov,
    )
    (output / f"{folder.name}.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "case",
                    "target_range_m",
                    "peak_power_db_counts2",
                    "far_doppler_target_dbc",
                    "near_doppler_target_dbc",
                    "far_doppler_background_dbc",
                    "target_gain_rms_real",
                    "target_gain_rms_imag",
                )
            }
        ),
        flush=True,
    )
    return summary


def plots(output: Path, summaries: list[dict[str, Any]]) -> None:
    fig_static, ast = plt.subplots(2, 1, figsize=(13, 9), layout="constrained")
    fig_maps, amap = plt.subplots(2, 2, figsize=(14, 10), layout="constrained")
    fig_cuts, acut = plt.subplots(2, 2, figsize=(14, 10), layout="constrained")
    fig_cov, acov = plt.subplots(2, 2, figsize=(14, 10), layout="constrained")
    for i, summary in enumerate(summaries):
        case = summary["case"]
        a = np.load(output / f"{case}.npz")
        ranges = a["range_m"]
        doppler = a["doppler_hz"]
        peak = float(a["peak_power"])
        peak_bin = int(np.argmin(np.abs(ranges - summary["target_range_m"])))
        for ax in ast:
            ax.plot(
                a["high_range_m"],
                db(a["coherent_power"][:, summary["rx"] - 1]),
                label=case,
            )
        ax = amap.flat[i]
        im = ax.pcolormesh(
            ranges,
            doppler / 1000,
            db(a["rd_power"] / peak),
            shading="auto",
            vmin=-100,
            vmax=-40,
            rasterized=True,
        )
        ax.set(
            xlim=(0, 40),
            xlabel="Apparent range [m]",
            ylabel="Doppler [kHz]",
            title=f"{case}: RX{summary['rx']}; peak {summary['target_range_m']:.2f} m",
        )
        fig_maps.colorbar(im, ax=ax, label="dBc/bin relative to reflector peak")
        ax = acut.flat[i]
        ax.plot(
            ranges, db(a["rd_power"][len(doppler) // 2] / peak), label="Zero Doppler"
        )
        ax.plot(
            ranges,
            db(a["near_doppler_power"] / peak),
            label="Mean |Doppler| = 0.5–3 kHz",
        )
        ax.plot(
            ranges, db(a["far_doppler_power"] / peak), label="Mean |Doppler| > 5 kHz"
        )
        ax.axvline(summary["target_range_m"], color="gray", linestyle=":")
        ax.set(
            xlim=(0, 40),
            ylim=(-110, 10),
            xlabel="Apparent range [m]",
            ylabel="dBc/bin",
            title=case,
        )
        ax.legend(fontsize=8)
        ax.grid(alpha=0.25)
        ax = acov.flat[i]
        for field, label in (
            ("eig_raw", "Real, uncentered"),
            ("eig_real", "Real, per-CPI mean removed"),
            ("eig_positive", "Positive FFT, per-CPI mean removed"),
        ):
            ax.plot(np.arange(1, a[field].size + 1), db(a[field]), label=label)
        ax.set(
            xscale="log",
            xlabel="Eigenvalue index",
            ylabel="Eigenvalue [dB ADC-count²]",
            title=case,
        )
        ax.legend(fontsize=8)
        ax.grid(alpha=0.25)
        # Per-case Doppler cut and normalized gain diagnostics.
        fig, axes = plt.subplots(2, 2, figsize=(13, 8), layout="constrained")
        axes[0, 0].plot(doppler / 1000, db(a["rd_power"][:, peak_bin] / peak))
        axes[0, 0].set(
            xlabel="Doppler [kHz]",
            ylabel="dBc/bin",
            ylim=(-110, 5),
            title="At reflector range bin",
        )
        axes[0, 1].plot(
            np.arange(a["target_gain"].shape[1]),
            a["target_gain"][0].real,
            label="In-phase (amplitude-like)",
        )
        axes[0, 1].plot(
            np.arange(a["target_gain"].shape[1]),
            a["target_gain"][0].imag,
            label="Quadrature (phase-like)",
        )
        axes[0, 1].set(
            xlabel="Chirp",
            ylabel="Fractional complex gain",
            title="CPI 0; static mean removed",
        )
        axes[0, 1].legend(fontsize=8)
        gain = a["target_gain"].ravel()
        axes[1, 0].scatter(gain.real[::4], gain.imag[::4], s=2, alpha=0.25)
        axes[1, 0].set(
            xlabel="In-phase fluctuation",
            ylabel="Quadrature fluctuation",
            title="All CPIs, one in four samples",
            aspect="equal",
        )
        rv = np.mean(a["rx_peak"], axis=0)
        rp = np.mean(a["rx_off"], axis=0)
        for channel in range(rv.size):
            axes[1, 1].plot(
                ranges, db(rp[:, channel] / rv[channel]), label=f"RX{channel+1}"
            )
        axes[1, 1].set(
            xlim=(0, 20),
            ylim=(-105, -40),
            xlabel="Apparent range [m]",
            ylabel="dBc/bin",
            title="Far-Doppler floor, channels separately",
        )
        axes[1, 1].legend(ncol=2, fontsize=8)
        for ax in axes.flat:
            ax.grid(alpha=0.25)
        fig.suptitle(case)
        fig.savefig(output / f"{case}_details.png", dpi=150)
        plt.close(fig)
    for ax, limit in zip(ast, (16, 50)):
        ax.set(
            xlim=(0, limit),
            ylim=(-30, 55),
            xlabel="Apparent range [m]",
            ylabel="Power [dB ADC-count²]",
        )
        ax.legend()
        ax.grid(alpha=0.25)
    fig_static.suptitle(
        f"Stationary environment: RX{summaries[0]['rx']} coherent range spectra, averaged in power across CPIs"
    )
    fig_cov.suptitle(
        "Fast-time covariance; rectangular window, one RX; no cross-CPI coherence assumed"
    )
    for fig, name in (
        (fig_static, "01_static"),
        (fig_maps, "02_maps"),
        (fig_cuts, "03_cuts"),
        (fig_cov, "04_covariance"),
    ):
        fig.savefig(output / f"{name}.png", dpi=150)
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("local/phase_noise_outdoor")
    )
    parser.add_argument("--rx", type=int, default=1)
    parser.add_argument("--plots-only", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.plots_only:
        summaries = [
            json.loads(p.read_text()) for p in sorted(args.output.glob("*MHz-*m.json"))
        ]
    else:
        summaries = [
            analyze(p, args.output, args.rx - 1)
            for p in sorted(args.input.iterdir())
            if p.is_dir() and (p / "manifest.json").exists()
        ]
    plots(args.output, summaries)


if __name__ == "__main__":
    main()
