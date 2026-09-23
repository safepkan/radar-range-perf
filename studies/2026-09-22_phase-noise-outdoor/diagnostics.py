"""Model overlays and cross-channel phase diagnostics for analyzed captures."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import get_window

from radarperf import FmcwWaveform
from radarperf.phase_noise import (
    SingleReturnPhaseNoise,
    ctrx8188f_phase_noise,
    phase_noise_fft,
)
from radarperf.units import SPEED_OF_LIGHT

from analyze import db


def run_case(folder: Path, output: Path) -> dict[str, Any]:
    summary_path = output / f"{folder.name}.json"
    summary: dict[str, Any] = json.loads(summary_path.read_text())
    rx = int(summary["rx"]) - 1
    wf = summary["waveform"]
    nc, ns, nrx = summary["shape"]
    fs = summary["sample_rate_hz"]
    # Metadata serializes slightly imprecise timing; 15.9600003826 us is
    # 798 nominal 20 ns ticks. Use that grid for covariance FFT efficiency.
    period = round(wf["chirp_period_us"] * 1e-6 * fs) / fs
    waveform = FmcwWaveform.from_slope(
        wf["adc_center_frequency_hz"], wf["slope_hz_per_s"], fs, ns, nc, period
    )
    model = SingleReturnPhaseNoise.from_range(
        summary["target_range_m"],
        shared=ctrx8188f_phase_noise(rf_band="77-81", extrapolation="constant"),
    )
    pred_path = output / f"{folder.name}_prediction.npz"
    pred = phase_noise_fft(
        model,
        waveform,
        offset_band_hz=(1, 20e6),
        range_window="blackmanharris",
        doppler_window="hann",
        sampling="real_phase_averaged",
    )
    np.savez_compressed(
        pred_path,
        range_m=pred.range_m,
        doppler_hz=pred.doppler_hz,
        phase_noise_dbc=pred.phase_noise_dbc,
        carrier_dbc=pred.carrier_dbc,
    )
    prediction = np.load(pred_path)
    pr = prediction["range_m"]
    pf = prediction["doppler_hz"]
    peak_bin = int(np.argmin(abs(pr - summary["target_range_m"])))
    model_far = np.mean(
        10 ** (prediction["phase_noise_dbc"][abs(pf) > 5000] / 10), axis=0
    )

    wr = np.asarray(get_window("blackmanharris", ns))
    wd = np.asarray(get_window("hann", nc))
    fd = np.fft.fftfreq(nc, period)
    keep = abs(fd) > 5000
    t = np.linspace(-1, 1, nc)
    polynomial = np.polynomial.polynomial.polyvander(t, 3)
    projector = np.linalg.pinv(polynomial)
    selected = [
        p for p in summary["strongest_static_returns"] if 2 < p["range_m"] < 45
    ][:4]
    # Ensure the presumed reflector is first; remaining peaks are scene returns.
    selected = [{"range_m": summary["target_range_m"]}] + [
        p for p in selected if abs(p["range_m"] - summary["target_range_m"]) > 1
    ]
    peak_ranges = np.array([p["range_m"] for p in selected])
    frequencies = 2 * waveform.effective_slope_hz_per_s * peak_ranges / SPEED_OF_LIGHT
    tone = (
        np.exp(-2j * np.pi * frequencies[:, None] * np.arange(ns)[None, :] / fs)
        * wr
        / wr.sum()
    )
    phase_cov = np.zeros((nrx, nrx), dtype=complex)
    amplitude_cov = np.zeros_like(phase_cov)
    return_cov = np.zeros((len(selected), len(selected)), dtype=complex)
    phase_psd = np.zeros(nc)
    amplitude_psd = np.zeros(nc)
    phase_traces = []
    drift_hz = []
    frame_stripe = []
    common_psd = np.zeros(nc)
    frame_common = []
    pair_mask = ~np.eye(nrx, dtype=bool)
    for path in sorted(folder.glob("frame-*.bin")):
        meta = json.loads(path.with_suffix(".json").read_text())
        x = np.fromfile(path, dtype=meta["dtype"]).reshape(meta["shape"]).astype(float)
        gains = np.einsum("csr,ks->ckr", x, tone)
        phase = np.unwrap(np.angle(gains[:, 0]), axis=0)
        amplitude = np.abs(gains[:, 0])
        amplitude = amplitude / np.mean(amplitude, axis=0) - 1
        phase_fit = polynomial @ (projector @ phase)
        phase_residual = phase - phase_fit
        amplitude -= polynomial @ (projector @ amplitude)
        phase_fft = np.fft.fft(phase_residual * wd[:, None], axis=0) / wd.sum()
        amplitude_fft = np.fft.fft(amplitude * wd[:, None], axis=0) / wd.sum()
        phase_cov += phase_fft[keep].conj().T @ phase_fft[keep] / keep.sum()
        common = (
            abs(phase_fft.sum(axis=1)) ** 2 - np.sum(abs(phase_fft) ** 2, axis=1)
        ) / (nrx * (nrx - 1))
        common_psd += common
        frame_common.append(float(np.mean(common[keep])))
        amplitude_cov += amplitude_fft[keep].conj().T @ amplitude_fft[keep] / keep.sum()
        phase_psd += abs(phase_fft[:, rx]) ** 2
        amplitude_psd += abs(amplitude_fft[:, rx]) ** 2
        phase_traces.append(phase_residual[:, rx])
        drift_hz.append(
            float(
                (phase_fit[-1, rx] - phase_fit[0, rx]) / (2 * np.pi * (nc - 1) * period)
            )
        )
        return_phase = np.unwrap(np.angle(gains[:, :, rx]), axis=0)
        return_phase -= polynomial @ (projector @ return_phase)
        return_fft = np.fft.fft(return_phase * wd[:, None], axis=0) / wd.sum()
        return_cov += return_fft[keep].conj().T @ return_fft[keep] / keep.sum()
        frame_stripe.append(float(db(np.mean(abs(phase_fft[keep, rx]) ** 2))))
    count = len(phase_traces)
    phase_cov /= count
    amplitude_cov /= count
    return_cov /= count
    phase_psd /= count
    amplitude_psd /= count
    common_psd /= count
    phase_diag = np.diag(phase_cov).real
    amp_diag = np.diag(amplitude_cov).real
    coherence = abs(phase_cov) ** 2 / (phase_diag[:, None] * phase_diag[None, :])
    return_diag = np.diag(return_cov).real
    return_coherence = abs(return_cov) ** 2 / (
        return_diag[:, None] * return_diag[None, :]
    )
    pair_cov = float(np.mean(phase_cov.real[pair_mask]))
    tau = 2 * summary["target_range_m"] / SPEED_OF_LIGHT
    enbw_bins = nc * np.sum(wd**2) / wd.sum() ** 2
    equivalent_frequency_rms = np.sqrt(max(pair_cov, 0) * keep.sum() / enbw_bins) / (
        2 * np.pi * tau
    )
    summary.update(
        {
            "model_far_doppler_target_dbc": float(db(model_far[peak_bin])),
            "phase_to_amplitude_high_doppler_db": float(
                db(phase_diag[rx] / amp_diag[rx])
            ),
            "phase_channel_coherence_primary_rx": coherence[rx].tolist(),
            "phase_common_high_doppler_dbc": float(db(pair_cov)),
            "phase_total_high_doppler_dbc": float(db(phase_diag[rx])),
            "amplitude_high_doppler_dbc": float(db(amp_diag[rx])),
            "slow_phase_drift_equivalent_hz": drift_hz,
            "phase_frame_high_doppler_dbc": frame_stripe,
            "phase_common_frame_high_doppler_dbc": db(frame_common).tolist(),
            "equivalent_frequency_rms_high_doppler_hz": float(equivalent_frequency_rms),
            "equivalent_frequency_frame_rms_hz": (
                np.sqrt(np.maximum(frame_common, 0) * keep.sum() / enbw_bins)
                / (2 * np.pi * tau)
            ).tolist(),
            "equivalent_frequency_rms_band_hz": [5000, 0.5 / period],
            "phase_return_ranges_m": peak_ranges.tolist(),
            "phase_return_coherence": return_coherence.tolist(),
            "phase_return_high_doppler_dbc": db(return_diag).tolist(),
        }
    )
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    np.savez_compressed(
        output / f"{folder.name}_phase.npz",
        phase_cov=phase_cov,
        amplitude_cov=amplitude_cov,
        return_cov=return_cov,
        return_ranges_m=peak_ranges,
        frequencies_hz=frequencies,
        phase_psd=phase_psd,
        amplitude_psd=amplitude_psd,
        common_phase_psd=common_psd,
        phase_traces=np.asarray(phase_traces),
        doppler_hz=fd,
    )
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "case",
                    "model_far_doppler_target_dbc",
                    "phase_to_amplitude_high_doppler_db",
                    "phase_common_high_doppler_dbc",
                    "phase_channel_coherence_primary_rx",
                    "slow_phase_drift_equivalent_hz",
                )
            }
        ),
        flush=True,
    )
    return summary


def plots(output: Path, summaries: list[dict[str, Any]]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), layout="constrained")
    fig_phase, ap = plt.subplots(2, 2, figsize=(14, 10), layout="constrained")
    fig_eig, ae = plt.subplots(2, 2, figsize=(14, 10), layout="constrained")
    fig_scaling, asc = plt.subplots(1, 2, figsize=(14, 5), layout="constrained")
    for i, s in enumerate(summaries):
        name = s["case"]
        a = np.load(output / f"{name}.npz")
        m = np.load(output / f"{name}_prediction.npz")
        p = np.load(output / f"{name}_phase.npz")
        f = p["doppler_hz"]
        positive_bins = np.flatnonzero(f > 0)
        pos = positive_bins[: len(positive_bins) // 8 * 8].reshape(-1, 8)
        tau = 2 * s["target_range_m"] / SPEED_OF_LIGHT
        common = np.mean(
            0.5 * (p["common_phase_psd"][pos] + p["common_phase_psd"][(-pos) % len(f)]),
            axis=1,
        )
        enbw_hz = 1.5 / (s["shape"][0] * s["waveform"]["chirp_period_us"] * 1e-6)
        asc[0].plot(np.mean(f[pos], axis=1) / 1000, db(common), label=name)
        asc[1].plot(
            np.mean(f[pos], axis=1) / 1000,
            db(common / (2 * np.pi * tau) ** 2 / enbw_hz),
            label=name,
        )
        peak = float(a["peak_power"])
        model = np.mean(
            10 ** (m["phase_noise_dbc"][abs(m["doppler_hz"]) > 5000] / 10), axis=0
        )
        ax = axes.flat[i]
        ax.plot(
            a["range_m"],
            db(a["far_doppler_power"] / peak),
            label="Measured total, |Doppler| > 5 kHz",
        )
        ax.plot(m["range_m"], db(model), label="Reflector-only CW phase-noise model")
        ax.axhline(
            s["far_doppler_background_dbc"],
            color="gray",
            linestyle=":",
            label="Measured background proxy (not proven thermal)",
        )
        ax.set(
            xlim=(0, 16),
            ylim=(-105, -55),
            xlabel="Apparent range [m]",
            ylabel="dBc/bin",
            title=name,
        )
        ax.grid(alpha=0.25)
        ax.legend(fontsize=7)
        ax = ap.flat[i]
        f = p["doppler_hz"]
        # Average adjacent positive/negative Doppler bins in groups of 8 for display.
        for field, label in (
            ("phase_psd", "Detrended phase fluctuations"),
            ("amplitude_psd", "Detrended amplitude fluctuations"),
        ):
            positive_bins = np.flatnonzero(f > 0)
            pos = positive_bins[: len(positive_bins) // 8 * 8].reshape(-1, 8)
            power = 0.5 * (p[field][pos] + p[field][(-pos) % len(f)])
            ax.plot(
                np.mean(f[pos], axis=1) / 1000, db(np.mean(power, axis=1)), label=label
            )
        ax.set(
            xlabel="|Doppler| [kHz]",
            ylabel="Fractional fluctuation power [dB/bin]",
            title=name,
            ylim=(-110, -45),
        )
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
        ax = ae.flat[i]
        for field, label in (
            ("eig_high_real", "Real samples"),
            ("eig_high_positive", "Positive FFT bins"),
        ):
            ax.plot(np.arange(1, len(a[field]) + 1), db(a[field]), label=label)
        ax.set(
            xscale="log",
            xlabel="Eigenvalue index",
            ylabel="Eigenvalue [dB ADC-count²]",
            title=name,
        )
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
    fig.suptitle(
        f"RX{summaries[0]['rx']}: matched processing; model uses apparent reflector delay, upper-band typical CW data\nReal sampling; ideal IF; constant extrapolation outside 10 kHz–10 MHz; integration 1 Hz–20 MHz"
    )
    fig_phase.suptitle(
        "Complex reflector coefficient: phase versus amplitude after per-CPI cubic detrending\nNoise of the coefficient estimate is included; this does not isolate oscillator phase noise"
    )
    fig_eig.suptitle(
        "Covariance restricted to |Doppler| > 5 kHz; Hann slow-time window\nSlow drift/static returns suppressed; rectangular fast-time window"
    )
    for ax in asc:
        ax.set(xlabel="|Doppler| [kHz]", xlim=(1, 31.4))
        ax.legend(fontsize=8)
        ax.grid(alpha=0.25)
    asc[0].set(
        ylabel="Common phase power [dB rad²/bin]",
        ylim=(-95, -55),
        title="Real cross-spectra between RX channels",
    )
    asc[1].set(
        ylabel="Equivalent frequency PSD [dB Hz²/Hz]",
        ylim=(20, 50),
        title="Divide by (2π × apparent delay)² and ENBW",
    )
    fig_scaling.suptitle(
        "Common phase fluctuation versus range and slope; a diagnostic scaling, not a source identification"
    )
    for figure, name in (
        (fig, "05_model"),
        (fig_phase, "06_phase"),
        (fig_eig, "07_high_doppler_covariance"),
        (fig_scaling, "08_delay_scaling"),
    ):
        figure.savefig(output / f"{name}.png", dpi=150)
        plt.close(figure)
    gallery = [
        ("01_static", "Stationary scene and reflector identification"),
        ("02_maps", "Single-RX range–Doppler power relative to each reflector"),
        ("03_cuts", "Zero, near and far Doppler range cuts"),
        ("05_model", "Measured total versus reflector-only CW model"),
        ("06_phase", "Phase and amplitude fluctuations after detrending"),
        ("08_delay_scaling", "Common phase fluctuations and delay scaling"),
        ("04_covariance", "Covariance including slow drift"),
        ("07_high_doppler_covariance", "Covariance with low Doppler excluded"),
    ]
    gallery.extend((f"{s['case']}_details", s["case"]) for s in summaries)
    sections = "\n".join(
        f"<section><h2>{html.escape(title)}</h2>"
        f'<a href="{html.escape(name)}.png"><img loading="lazy" '
        f'src="{html.escape(name)}.png" alt="{html.escape(title)}"></a></section>'
        for name, title in gallery
    )
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Outdoor reflector phase-noise analysis</title>"
        "<style>body{font:17px system-ui;margin:2rem auto;max-width:1500px;"
        "padding:0 1rem;color:#182332}img{width:100%}section{margin:3rem 0}"
        "h1,h2{line-height:1.2}p{max-width:85ch}</style>"
        "<h1>Outdoor reflector captures — 22 September 2026</h1>"
        "<p>The data contains a largely independent background plus correlated, "
        "predominantly phase-like fluctuations concentrated at strong-return ranges. "
        "The common phase component scales closely with apparent delay. Its "
        "hardware origin remains unconfirmed.</p>"
        "<p>Primary spectra use one RX; cross-channel statistics diagnose shared "
        "fluctuations without beamforming. No reflector-absent reference was supplied. "
        "Click a figure for its full-resolution image.</p>" + sections + "</html>\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("local/phase_noise_outdoor")
    )
    args = parser.parse_args()
    summaries = [
        run_case(folder, args.output)
        for folder in sorted(args.input.iterdir())
        if folder.is_dir() and (folder / "manifest.json").exists()
    ]
    plots(args.output, summaries)


if __name__ == "__main__":
    main()
