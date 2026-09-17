"""Six controlled phase-noise lessons; see docs/phase_noise_tutorial.md.

Run all lessons, or select one with --lesson. Each saves PNG and NPZ files;
index.html provides a local gallery with questions and takeaways. Synthetic
spectra teach individual effects and are not chipset specifications.
The separate phase_noise.py script is the configurable chamber diagnostic.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from html import escape
import json
from pathlib import Path
import tempfile
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import numpy as np

from radarperf import FmcwWaveform
from radarperf.phase_noise import (
    PhaseNoiseResult,
    SingleReturnPhaseNoise,
    TabulatedPhaseNoise,
    ctrx8188f_phase_noise,
    phase_noise_fft,
)
from radarperf.plotting import is_non_interactive_backend
from radarperf.units import SPEED_OF_LIGHT, db_to_linear, linear_to_db

LESSONS = {
    "delay": (
        "01_delay",
        "Why can a nearby return have less phase noise?",
        "Shared noise cancels at short delay. Longer delays produce peaks and nulls; independent residual noise fills the nulls.",
    ),
    "mapping": (
        "02_mapping",
        "How does a frequency feature become a range feature?",
        "A frequency offset maps to c Δf / (2 slope). Steeper chirps compress the same spectral structure into fewer metres.",
    ),
    "windows": (
        "03_windows",
        "Is that skirt phase noise or target leakage?",
        "Changing the FFT window changes deterministic sidelobes strongly. Random phase noise remains, and wider window noise bandwidth can raise its per-bin level.",
    ),
    "doppler": (
        "04_doppler",
        "Why is noise sometimes broad in Doppler and sometimes localized?",
        "Slow phase fluctuations can remain correlated between chirps. Giving each chirp an independent realization spreads that same range noise across Doppler.",
    ),
    "sampling": (
        "05_sampling",
        "What changes when the ADC samples a real signal?",
        "The conjugate beat lobe also contributes noise. The change can be 3 dB for a flat spectrum, but is frequency-dependent for a shaped spectrum.",
    ),
    "visibility": (
        "06_visibility",
        "When does the phase noise become visible?",
        "Keep thermal power fixed while changing return power. A return 10 dB weaker has a phase-noise contribution 10 dB weaker, but the combined floor does not fall by 10 dB.",
    ),
}


def save_lesson(fig: Figure, output_dir: Path, lesson: str, **arrays: Any) -> None:
    """Save numeric data and a short manifest alongside the figure."""
    stem, question, takeaway = LESSONS[lesson]
    fig.savefig(output_dir / f"{stem}.png", dpi=140)
    np.savez(output_dir / f"{stem}.npz", question=question, takeaway=takeaway, **arrays)
    print(f"{stem}: {question}\n  {takeaway}")


def finish_axes(ax: Axes, xlabel: str, ylabel: str) -> None:
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=9)


def delay_lesson(output_dir: Path) -> Figure:
    source = ctrx8188f_phase_noise(extrapolation="constant")
    offsets = np.geomspace(1e2, 1e7, 4000)
    ranges = (2.3, 25.0, 150.0)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), layout="constrained")
    residuals = []
    transfers = []
    for rng in ranges:
        model = SingleReturnPhaseNoise.from_range(rng, shared=source)
        transfer = linear_to_db(model.cancellation(offsets))
        residual = linear_to_db(model.residual_psd_per_hz(offsets))
        axes[0].semilogx(
            offsets, transfer, label=f"{rng:g} m; {model.delay_s * 1e9:.1f} ns"
        )
        axes[1].semilogx(offsets, residual, label=f"{rng:g} m")
        transfers.append(transfer)
        residuals.append(residual)
    axes[1].semilogx(
        offsets, source.ssb_db(offsets), "k--", alpha=0.6, label="assumed source"
    )
    # A separate residual illustrates incomplete cancellation, not an Infineon spec.
    independent = TabulatedPhaseNoise(
        (100.0, 1e7), (-130.0, -130.0), name="synthetic independent residual"
    )
    shared = SingleReturnPhaseNoise.from_range(150, shared=source)
    combined = replace(shared, independent=independent)
    high_offsets = np.linspace(0.5e6, 3.5e6, 4000)
    axes[2].plot(
        high_offsets / 1e6,
        linear_to_db(shared.residual_psd_per_hz(high_offsets)),
        label="shared only",
    )
    combined_db = linear_to_db(combined.residual_psd_per_hz(high_offsets))
    axes[2].plot(
        high_offsets / 1e6, combined_db, label="+ synthetic −130 dBc/Hz residual"
    )
    for ax in axes[:2]:
        ax.axvspan(100, 1e4, color="gray", alpha=0.12)
    axes[0].set_ylim(-120, 10)
    axes[1].set_ylim(-180, -65)
    axes[2].set_ylim(-155, -85)
    axes[0].set_title("A · Shared-source cancellation")
    axes[1].set_title("B · Same source, different delay")
    axes[2].set_title("C · Independent noise fills delay nulls (150 m)")
    finish_axes(axes[0], "offset from return [Hz]", "power transfer [dB]")
    finish_axes(axes[1], "offset from return [Hz]", "SSB density [dBc/Hz]")
    finish_axes(axes[2], "offset from return [MHz]", "SSB density [dBc/Hz]")
    fig.suptitle(
        "1 · Delay changes cancellation, even at the same received power\nInfineon typical CW spectrum assumed shared; gray region: constant extrapolation below 10 kHz"
    )
    save_lesson(
        fig,
        output_dir,
        "delay",
        offset_hz=offsets,
        range_m=ranges,
        transfer_db=np.array(transfers),
        residual_dbc_hz=np.array(residuals),
        high_offset_hz=high_offsets,
        combined_dbc_hz=combined_db,
        source=source.source,
        independent_residual_dbc_hz=-130.0,
    )
    return fig


def mapping_lesson(output_dir: Path, oversample: int) -> Figure:
    source = ctrx8188f_phase_noise(extrapolation="constant")
    model = SingleReturnPhaseNoise.from_range(10, shared=source)
    slopes = (5e12, 20e12)
    offsets = np.geomspace(1e3, 1e6, 500)
    density_db = linear_to_db(model.residual_psd_per_hz(offsets))
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    data: dict[str, Any] = {
        "offset_hz": offsets,
        "residual_dbc_hz": density_db,
        "slopes_hz_per_s": slopes,
        "target_range_m": 10.0,
        "source": source.source,
    }
    for slope in slopes:
        label = f"{slope / 1e12:g} MHz/µs"
        axes[0].semilogx(
            SPEED_OF_LIGHT * offsets / (2 * slope), density_db, label=label
        )
        wf = FmcwWaveform.from_slope(76.5e9, slope, 10e6, 512, 1)
        result = phase_noise_fft(
            model,
            wf,
            offset_band_hz=(1, 1e7),
            range_doppler=False,
            range_window="blackmanharris",
            sampling="complex",
            integration_oversample=oversample,
        )
        # Ideal-carrier reference holds power fixed despite different bin straddle.
        axes[1].plot(
            result.range_m - 10, linear_to_db(result.phase_noise_power[0]), label=label
        )
        key = f"slope_{slope / 1e12:g}"
        data[f"{key}_range_offset_m"] = result.range_m - 10
        data[f"{key}_noise_power"] = result.phase_noise_power
        data[f"{key}_waveform"] = json.dumps(asdict(wf))
    axes[0].set_title("A · Relabel the same spectrum; no FFT yet")
    axes[1].set_title("B · Actual single-chirp FFT noise")
    axes[1].set_xlim(-5, 5)
    axes[1].axvline(0, color="gray", linestyle=":")
    finish_axes(
        axes[0], "positive range offset from return [m]", "SSB density [dBc/Hz]"
    )
    finish_axes(
        axes[1], "range offset from return [m]", "power/bin [dBc to ideal carrier]"
    )
    fig.suptitle(
        "2 · Chirp slope changes where the noise lands in range\nFixed 10 m delay and carrier power; 10 MS/s × 512 samples; complex IF; Blackman–Harris window"
    )
    save_lesson(fig, output_dir, "mapping", **data)
    return fig


def windows_lesson(output_dir: Path, oversample: int) -> Figure:
    source = ctrx8188f_phase_noise(extrapolation="constant")
    model = SingleReturnPhaseNoise.from_range(25, shared=source)
    wf = FmcwWaveform.from_slope(76.5e9, 10e12, 10e6, 512, 1)
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), layout="constrained", sharey=True)
    data: dict[str, Any] = {
        "waveform": json.dumps(asdict(wf)),
        "target_range_m": 25.0,
        "source": source.source,
    }
    for ax, name in zip(axes, ("boxcar", "hann", "blackmanharris")):
        result = phase_noise_fft(
            model,
            wf,
            offset_band_hz=(1, 1e7),
            range_doppler=False,
            range_window=name,
            sampling="complex",
            integration_oversample=oversample,
        )
        ax.plot(
            result.range_m,
            result.carrier_dbc[0],
            "--",
            label="carrier / window leakage",
        )
        ax.plot(result.range_m, result.phase_noise_dbc[0], label="phase noise")
        ax.plot(result.range_m, result.total_dbc[0], alpha=0.65, label="expected total")
        enbw_bins = result.range_enbw_hz / (wf.sample_rate_hz / wf.n_samples)
        ax.set_title(f"{name} · ENBW {enbw_bins:.2f} bins")
        ax.set_xlim(15, 35)
        ax.set_ylim(-130, 5)
        finish_axes(ax, "apparent range [m]", "power/bin [dBc to that window's peak]")
        data["range_m"] = result.range_m
        data[f"{name}_carrier_dbc"] = result.carrier_dbc
        data[f"{name}_noise_dbc"] = result.phase_noise_dbc
        data[f"{name}_peak_power"] = result.carrier_peak_power
        data[f"{name}_enbw_bins"] = enbw_bins
    fig.suptitle(
        "3 · Window sidelobes can hide the phase-noise floor\nSame off-bin 25 m return; complex IF; only the range window changes; no thermal noise"
    )
    save_lesson(fig, output_dir, "windows", **data)
    return fig


def normalized_residual(close_in: bool) -> TabulatedPhaseNoise:
    """Synthetic residuals with equal two-sided variance in 1 Hz–1 MHz."""
    f = (1.0, 50.0, 200.0, 500.0, 1e3, 2e3, 1e4, 1e6)
    levels = (
        (-70.0, -70.0, -70.0, -76.0, -90.0, -110.0, -140.0, -160.0)
        if close_in
        else (-100.0,) * len(f)
    )
    table = TabulatedPhaseNoise(
        f,
        levels,
        name="synthetic close-in residual" if close_in else "synthetic broad residual",
    )
    grid = np.geomspace(1, 1e6, 20000)
    variance = 2 * float(np.trapezoid(table.ssb_linear_per_hz(grid), grid))
    adjustment = float(linear_to_db(1e-4 / variance))
    return replace(table, ssb_dbc_hz=tuple(x + adjustment for x in levels))


def doppler_lesson(output_dir: Path, oversample: int) -> Figure:
    wf = FmcwWaveform.from_slope(76.5e9, 2e12, 2e6, 128, 128, 100e-6)
    # Bin-centered carrier avoids straddle as a second changing variable.
    target_range = SPEED_OF_LIGHT * 0.5e6 / (2 * wf.effective_slope_hz_per_s)
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), layout="constrained")
    data: dict[str, Any] = {
        "waveform": json.dumps(asdict(wf)),
        "target_range_m": target_range,
        "two_sided_residual_variance": 1e-4,
        "offset_band_hz": (1.0, 1e6),
    }
    for col, (close_in, correlation, title) in enumerate(
        (
            (False, "stationary", "Broad residual · stationary"),
            (True, "stationary", "Slow residual · stationary"),
            (True, "independent", "Same slow residual · independent chirps"),
        )
    ):
        spectrum = normalized_residual(close_in)
        model = SingleReturnPhaseNoise.from_range(target_range, independent=spectrum)
        result = phase_noise_fft(model, wf, offset_band_hz=(1, 1e6), range_window="blackmanharris", doppler_window="hann", sampling="complex", chirp_correlation=correlation, integration_oversample=max(oversample, 8))  # type: ignore[arg-type]
        mesh = axes[0, col].pcolormesh(
            result.range_m - target_range,
            result.doppler_hz,
            np.maximum(result.phase_noise_dbc, -115),
            shading="auto",
            vmin=-115,
            vmax=-45,
        )
        axes[0, col].set_xlim(-8, 8)
        axes[0, col].set_xlabel("range offset from return [m]")
        axes[0, col].set_ylabel("Doppler [Hz]")
        axes[0, col].set_title(title)
        fig.colorbar(mesh, ax=axes[0, col], label="phase noise [dBc/bin]")
        index = int(np.argmax(result.carrier_power[result.doppler_hz.size // 2]))
        axes[1, col].plot(
            result.doppler_hz,
            result.phase_noise_dbc[:, index],
            label="noise at target range bin",
        )
        axes[1, col].set_ylim(-115, -40)
        finish_axes(axes[1, col], "Doppler [Hz]", "phase noise [dBc/bin]")
        data["range_m"] = result.range_m
        data["doppler_hz"] = result.doppler_hz
        data[f"case_{col}_noise_dbc"] = result.phase_noise_dbc
        data[f"case_{col}_noise_power"] = result.phase_noise_power
        data[f"case_{col}_spectrum"] = json.dumps(asdict(spectrum))
        data[f"case_{col}_integration_step_hz"] = result.integration_step_hz
    fig.suptitle(
        "4 · Three different range–Doppler structures\nSynthetic independent-path residuals, not Infineon data; equal variance before IF filtering; complex IF; carrier omitted"
    )
    save_lesson(fig, output_dir, "doppler", **data)
    return fig


def sampling_lesson(output_dir: Path, oversample: int) -> Figure:
    wf = FmcwWaveform.from_slope(76.5e9, 2e12, 2e6, 256, 1)
    target_range = SPEED_OF_LIGHT * 62500 / (2 * wf.effective_slope_hz_per_s)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    data: dict[str, Any] = {
        "waveform": json.dumps(asdict(wf)),
        "target_range_m": target_range,
        "offset_band_hz": (1.0, 2e6),
    }
    for col, shaped in enumerate((False, True)):
        spectrum = TabulatedPhaseNoise(
            (1.0, 1e4, 1e5, 3e5, 1e6, 2e6),
            (-90.0, -90.0, -100.0, -120.0, -140.0, -140.0) if shaped else (-110.0,) * 6,
            name="synthetic shaped residual" if shaped else "synthetic flat residual",
        )
        model = SingleReturnPhaseNoise.from_range(target_range, independent=spectrum)
        results: list[PhaseNoiseResult] = []
        for sampling in ("complex", "real_phase_averaged"):
            result = phase_noise_fft(model, wf, offset_band_hz=(1, 2e6), range_doppler=False, range_window="blackmanharris", sampling=sampling, integration_oversample=oversample)  # type: ignore[arg-type]
            keep = result.range_m >= 0
            axes[0, col].plot(
                result.range_m[keep],
                result.phase_noise_dbc[0, keep],
                label=(
                    "real, phase averaged"
                    if sampling == "real_phase_averaged"
                    else "complex IF"
                ),
            )
            results.append(result)
        complex_result, real_result = results
        difference = (
            real_result.phase_noise_dbc[0]
            - complex_result.phase_noise_dbc[0, complex_result.range_m >= 0]
        )
        axes[1, col].plot(real_result.range_m, difference, label="real minus complex")
        axes[1, col].axhline(
            10 * np.log10(2), color="gray", linestyle=":", label="3.01 dB reference"
        )
        axes[1, col].set_ylim(-0.2, 3.4)
        axes[0, col].set_title("Shaped residual" if shaped else "Flat residual")
        for row in range(2):
            axes[row, col].axvline(target_range, color="gray", linestyle=":")
            finish_axes(
                axes[row, col],
                "apparent range [m]",
                (
                    "phase noise [dBc/bin]"
                    if row == 0
                    else "extra noise from real sampling [dB]"
                ),
            )
        data["range_m"] = real_result.range_m
        data[f"case_{col}_real_noise_dbc"] = real_result.phase_noise_dbc
        data[f"case_{col}_complex_noise_dbc"] = complex_result.phase_noise_dbc[
            :, complex_result.range_m >= 0
        ]
        data[f"case_{col}_difference_db"] = difference
        data[f"case_{col}_spectrum"] = json.dumps(asdict(spectrum))
    fig.suptitle(
        f"5 · Real sampling includes the conjugate beat lobe\nSynthetic residuals; on-bin return at {target_range:.3f} m (vertical line); same waveform/window; carrier omitted"
    )
    save_lesson(fig, output_dir, "sampling", **data)
    return fig


def visibility_figure(
    source: TabulatedPhaseNoise,
    *,
    center_frequency_hz: float,
    range_m: float,
    peak_snr_db: float,
    return_drop_db: float,
    integration_oversample: int,
    output_dir: Path,
) -> Figure:
    """Show a specular return with a supplied peak/thermal ratio, not an RCS.

    Thermal power per processed bin is the fixed unit reference. The two
    levels could represent TX backoff or a weaker reflector at the same delay;
    the phase-noise spectrum, receiver gain and processing are held fixed.
    """
    if not np.isfinite([peak_snr_db, return_drop_db]).all() or return_drop_db < 0:
        raise ValueError(
            "visibility levels must be finite; return drop must be non-negative"
        )
    wf = FmcwWaveform.from_slope(center_frequency_hz, 10e12, 10e6, 512, 128, 64e-6)
    model = SingleReturnPhaseNoise.from_range(range_m, shared=source)
    result = phase_noise_fft(
        model,
        wf,
        offset_band_hz=(1.0, 10e6),
        sampling="real_phase_averaged",
        range_window="blackmanharris",
        doppler_window="hann",
        integration_oversample=integration_oversample,
    )
    peak_levels = np.array([peak_snr_db, peak_snr_db - return_drop_db])
    peak_to_thermal = db_to_linear(peak_levels)
    if not np.isfinite(peak_to_thermal).all():
        raise ValueError("visibility peak level is too large")
    # Shape: (return level, Doppler, range). Use one thermal reference for
    # BOTH levels; renormalizing each plot to its own peak would hide the drop.
    pn_to_thermal = (
        peak_to_thermal[:, None, None]
        * result.phase_noise_power
        / result.carrier_peak_power
    )
    carrier_to_thermal = (
        peak_to_thermal[:, None, None]
        * result.carrier_power
        / result.carrier_peak_power
    )
    total_db = linear_to_db(1 + pn_to_thermal + carrier_to_thermal)
    floor_rise_db = linear_to_db(1 + pn_to_thermal)
    row = int(np.argmin(abs(result.doppler_hz)))

    fig, axes = plt.subplots(2, 2, figsize=(14, 9), layout="constrained")
    labels = [
        f"stronger: peak {peak_levels[0]:g} dB above thermal",
        f"{return_drop_db:g} dB weaker: peak {peak_levels[1]:g} dB",
    ]
    colors = ["tab:blue", "tab:orange"]
    for i, (label, color) in enumerate(zip(labels, colors)):
        axes[0, 0].plot(result.range_m, total_db[i, row], color=color, label=label)
        axes[0, 0].plot(
            result.range_m,
            linear_to_db(pn_to_thermal[i, row]),
            color=color,
            linestyle="--",
            alpha=0.7,
            label=f"phase noise only ({'stronger' if i == 0 else 'weaker'})",
        )
        axes[0, 1].plot(result.range_m, floor_rise_db[i, row], color=color, label=label)
    axes[0, 0].axhline(0, color="black", linestyle=":", label="thermal floor")
    axes[0, 0].set_ylim(-20, max(10.0, peak_snr_db + 5))
    axes[0, 0].set_ylabel("power/bin [dB relative to thermal floor]")
    axes[0, 0].set_title("(A) Expected range cut at zero Doppler")
    axes[0, 1].axhline(0, color="black", linestyle=":")
    axes[0, 1].set_ylim(0, max(1.0, float(np.max(floor_rise_db)) * 1.1))
    axes[0, 1].set_ylabel("noise floor rise [dB]")
    axes[0, 1].set_title("(B) Thermal + phase noise; carrier leakage excluded")
    for ax in axes[0]:
        ax.set_xlabel("apparent range [m]")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    vmax = max(1.0, float(np.ceil(np.max(floor_rise_db))))
    for i, ax in enumerate(axes[1]):
        mesh = ax.pcolormesh(
            result.range_m,
            result.velocity_mps,
            floor_rise_db[i],
            shading="auto",
            vmin=0,
            vmax=vmax,
        )
        ax.plot(range_m, 0, "+", color="white", markersize=9)
        ax.set_xlabel("apparent range [m]")
        ax.set_ylabel("Doppler velocity [m/s]")
        ax.set_title(f"({'C' if i == 0 else 'D'}) Noise floor rise: {labels[i]}")
        fig.colorbar(mesh, ax=ax, label="rise above thermal [dB]")
    fig.suptitle(
        f"Visibility of a strong stationary return at {range_m:g} m (illustrative levels)\n"
        "10 MHz/µs; 10 MS/s; 512 samples/chirp; 128 chirps; 64 µs spacing\n"
        f"Real sampling; {source.name}; assumed shared; {source.extrapolation} extrapolation; ideal IF filter"
    )
    save_lesson(
        fig,
        output_dir,
        "visibility",
        range_m=result.range_m,
        doppler_hz=result.doppler_hz,
        velocity_mps=result.velocity_mps,
        peak_snr_db=peak_levels,
        phase_noise_to_thermal=pn_to_thermal,
        carrier_to_thermal=carrier_to_thermal,
        total_db_above_thermal=total_db,
        noise_floor_rise_db=floor_rise_db,
        phase_noise_dbc=result.phase_noise_dbc,
        carrier_dbc=result.carrier_dbc,
        thermal_power_reference=1.0,
        integration_step_hz=result.integration_step_hz,
        offset_band_hz=result.offset_band_hz,
        waveform=str(wf),
        target_range_m=range_m,
        sampling=result.sampling,
        chirp_correlation=result.chirp_correlation,
        source=source.source,
        source_name=source.name,
        extrapolation=source.extrapolation,
        range_window="blackmanharris",
        doppler_window="hann",
    )
    print(f"Visibility scenario: {range_m:g} m; {wf}")
    print(
        f"Assumed peak/thermal ratios: {peak_levels} dB; no RCS or TX power inferred."
    )
    for i, label in enumerate(labels):
        print(
            f"  {label}: max PN/thermal {float(np.max(linear_to_db(pn_to_thermal[i]))):.2f} dB; max noise floor rise {float(np.max(floor_rise_db[i])):.2f} dB"
        )
    return fig


def write_gallery(output_dir: Path, selected: list[str]) -> None:
    sections = []
    for lesson in selected:
        stem, question, takeaway = LESSONS[lesson]
        sections.append(
            f'<section><h2>{escape(question)}</h2><p>{escape(takeaway)}</p><a href="{stem}.png"><img src="{stem}.png" alt="{escape(question)}"></a><p><a href="{stem}.npz">Numeric arrays and settings</a></p></section>'
        )
    page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Phase noise tutorial</title>
<style>body{font:17px/1.6 system-ui,sans-serif;max-width:1400px;margin:40px auto;padding:0 24px;color:#172333;background:#fafbfc}section{margin:48px 0}img{width:100%;background:white}h1,h2{line-height:1.25}a{color:#175c9c}</style>
<h1>Building intuition for radar phase noise</h1><p>Each lesson changes one physical or processing ingredient. These are expected powers, not noisy realizations. Synthetic examples are teaching models; Infineon examples use CW data with explicit assumptions. Full explanations: <code>docs/phase_noise_tutorial.md</code> in the repository.</p>"""
    (output_dir / "index.html").write_text(page + "\n".join(sections) + "</html>")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", choices=("all", *LESSONS), default="all")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "radarperf_phase_noise_tutorial",
    )
    parser.add_argument("--integration-oversample", type=int, default=4)
    parser.add_argument("--visibility-range-m", type=float, default=25.0)
    parser.add_argument("--visibility-peak-snr-db", type=float, default=75.0)
    parser.add_argument("--visibility-drop-db", type=float, default=10.0)
    parser.add_argument("--no-show", action="store_true")
    args = parser.parse_args()
    if args.integration_oversample < 1:
        parser.error("--integration-oversample must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    selected = list(LESSONS) if args.lesson == "all" else [args.lesson]
    figures = []
    for lesson in selected:
        match lesson:
            case "delay":
                fig = delay_lesson(args.output_dir)
            case "mapping":
                fig = mapping_lesson(args.output_dir, args.integration_oversample)
            case "windows":
                fig = windows_lesson(args.output_dir, args.integration_oversample)
            case "doppler":
                fig = doppler_lesson(args.output_dir, args.integration_oversample)
            case "sampling":
                fig = sampling_lesson(args.output_dir, args.integration_oversample)
            case "visibility":
                fig = visibility_figure(
                    ctrx8188f_phase_noise(extrapolation="constant"),
                    center_frequency_hz=76.5e9,
                    range_m=args.visibility_range_m,
                    peak_snr_db=args.visibility_peak_snr_db,
                    return_drop_db=args.visibility_drop_db,
                    integration_oversample=args.integration_oversample,
                    output_dir=args.output_dir,
                )
            case _:
                raise ValueError(f"unknown lesson: {lesson}")
        figures.append(fig)
    write_gallery(args.output_dir, selected)
    print(f"Saved tutorial to {args.output_dir / 'index.html'}")
    if not args.no_show and not is_non_interactive_backend():
        plt.show()
    for fig in figures:
        plt.close(fig)


if __name__ == "__main__":
    main()
