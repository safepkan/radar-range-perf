"""Figures for docs/phase_noise.md.

Writes the page's figures to docs/figures/phase_noise (or --output-dir). They
use the CTRX8188F typical CW table, held constant outside its 10 kHz-10 MHz
points, and a waveform like the CARKIT window captures: a 10.24 us payload of
512 samples at 50 MS/s, 11.67 MHz/us, with Hann windows unless stated.

- delay_filter.png: the shared-LO delay filter 4 sin²(pi f tau) and the
  residual it leaves of the CW table, for three ranges.
- per_chirp_error.png: the LO's frequency-error PSD f² L(f), and what the
  payload average keeps of it for two windows and two payload lengths.
- coherence_loss.png: the Doppler integration loss against range for several
  per-chirp frequency errors, with the CW value's exact delay filter.
- range_doppler.png: the expected range-Doppler phase noise of one strong
  stationary return at 150.5 m, on a range bin (phase_noise_fft), with a
  range cut away from its Doppler and a Doppler cut at its range.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import numpy as np  # noqa: E402
from scipy.signal import get_window  # noqa: E402

from radarperf import FmcwWaveform, SystemLosses  # noqa: E402
from radarperf.phase_noise import (  # noqa: E402
    SingleReturnPhaseNoise,
    chirp_frequency_error_psd,
    chirp_frequency_error_rms_hz,
    ctrx8188f_phase_noise,
    phase_noise_fft,
)
from radarperf.units import SPEED_OF_LIGHT, linear_to_db  # noqa: E402

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1] / "docs" / "figures" / "phase_noise"
)

# Chart colours from the reference palette, as in the CARKIT report: surface,
# text inks, grid, a neutral band, categorical slots and an ordinal blue ramp.
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
BAND = "#f0efec"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
ORDINAL = ("#86b6ef", "#3987e5", "#1c5cab", "#0d366b")
ORDINAL_5 = ("#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b")

OFFSET_BAND_HZ = (1.0, 20e6)
SOURCE = ctrx8188f_phase_noise(rf_band="76-77", extrapolation="constant")


def waveform(n_samples: int = 512, chirp_period_s: float = 36e-6) -> FmcwWaveform:
    return FmcwWaveform.from_slope(77e9, 11.67e12, 50e6, n_samples, 256, chirp_period_s)


def style_axes(ax: Any) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(TEXT_SECONDARY)
    ax.tick_params(colors=TEXT_SECONDARY, labelcolor=TEXT, labelsize=8)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def label_axes(ax: Any, xlabel: str, ylabel: str, title: str) -> None:
    ax.set_xlabel(xlabel, color=TEXT, fontsize=9)
    ax.set_ylabel(ylabel, color=TEXT, fontsize=9)
    ax.set_title(title, color=TEXT, fontsize=9.5, loc="left")


def offset_axis(ax: Any, low: float, high: float) -> None:
    ax.set_xscale("log")
    ax.set_xlim(low, high)
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(
            lambda f, _: f"{f / 1e6:g} MHz" if f >= 1e6 else f"{f / 1e3:g} kHz"
        )
    )


def legend(ax: Any, **kwargs: Any) -> None:
    ax.legend(frameon=False, fontsize=8, labelcolor=TEXT, **kwargs)


def save(fig: Any, path: Path) -> None:
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    print(f"wrote {path}")


def delay_filter(output_dir: Path) -> None:
    offsets = np.geomspace(1e4, 1e7, 20000)
    ranges = (2.3, 25.0, 150.0)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), facecolor=SURFACE)
    for ax in axes:
        style_axes(ax)
        offset_axis(ax, 1e4, 1e7)
    axes[1].plot(
        offsets,
        SOURCE.ssb_db(offsets),
        color=TEXT_SECONDARY,
        linestyle="--",
        linewidth=1.5,
        label="LO, CW table",
    )
    for range_m, colour in zip(ranges, (ORDINAL[0], ORDINAL[2], ORDINAL[3])):
        model = SingleReturnPhaseNoise.from_range(range_m, shared=SOURCE)
        delay = (
            f"{model.delay_s * 1e9:.3g} ns"
            if model.delay_s < 1e-6
            else f"{model.delay_s * 1e6:.2g} µs"
        )
        label = f"{range_m:g} m, τ = {delay}"
        axes[0].plot(
            offsets,
            linear_to_db(model.cancellation(offsets)),
            color=colour,
            linewidth=1.5,
            label=label,
        )
        axes[1].plot(
            offsets,
            linear_to_db(model.residual_psd_per_hz(offsets)),
            color=colour,
            linewidth=1.5,
            label=f"{range_m:g} m",
        )
    axes[0].set_ylim(-70, 10)
    axes[1].set_ylim(-150, -70)
    label_axes(
        axes[0],
        "Offset from the return",
        "4 sin²(πfτ) [dB]",
        "(a) The delay filter",
    )
    label_axes(
        axes[1],
        "Offset from the return",
        "Phase noise [dBc/Hz]",
        "(b) What it leaves of the LO's phase noise",
    )
    legend(axes[0], loc="upper left")
    legend(axes[1], loc="upper right")
    fig.tight_layout()
    save(fig, output_dir / "delay_filter.png")


def per_chirp_error(output_dir: Path) -> None:
    offsets = np.geomspace(1e3, 1e7, 4000)
    frequency_error = offsets**2 * SOURCE.ssb_linear_per_hz(offsets)
    fig, ax = plt.subplots(figsize=(7.0, 4.2), facecolor=SURFACE)
    style_axes(ax)
    offset_axis(ax, 1e3, 1e7)
    ax.plot(
        offsets,
        linear_to_db(frequency_error),
        color=TEXT_SECONDARY,
        linestyle="--",
        linewidth=1.5,
        label="LO's frequency error, f² L(f)",
    )
    cases = (
        (512, "hann", "10.24 µs payload, Hann", BLUE),
        (512, "blackmanharris", "10.24 µs payload, Blackman–Harris", ORANGE),
        (2048, "hann", "40.96 µs payload, Hann", AQUA),
    )
    for n_samples, window, label, colour in cases:
        wf = waveform(n_samples, chirp_period_s=n_samples / 50e6 + 26e-6)
        df = chirp_frequency_error_rms_hz(
            SOURCE, wf, offset_band_hz=OFFSET_BAND_HZ, range_window=window
        )
        weights = np.asarray(get_window(window, n_samples))
        response = (
            np.abs(
                np.exp(-2j * np.pi * np.outer(offsets, np.arange(n_samples)) / 50e6)
                @ weights
            )
            / weights.sum()
        ) ** 2
        ax.plot(
            offsets,
            linear_to_db(frequency_error * response + 1e-30),
            color=colour,
            linewidth=1.5,
            label=f"{label}: δf = {df / 1e3:.2f} kHz",
        )
    ax.set_ylim(-20, 30)
    label_axes(
        ax,
        "Offset frequency f",
        "Frequency-error density [dB Hz²/Hz]",
        "What the payload average keeps of the LO's frequency error",
    )
    legend(ax, loc="lower left")
    fig.tight_layout()
    save(fig, output_dir / "per_chirp_error.png")


def coherence_loss(output_dir: Path) -> None:
    ranges = np.geomspace(50, 2000, 300)
    fig, ax = plt.subplots(figsize=(7.0, 4.2), facecolor=SURFACE)
    style_axes(ax)
    wf = waveform()
    cw = chirp_frequency_error_rms_hz(SOURCE, wf, offset_band_hz=OFFSET_BAND_HZ)
    values = (cw, 3.5e3, 5.9e3, 10e3, 21e3)
    for df, colour in zip(values, ORDINAL_5):
        loss = SystemLosses(chirp_frequency_error_rms_hz=df).coherence_loss_db(ranges)
        ax.plot(ranges, loss, color=colour, linewidth=1.5)
        ax.text(
            ranges[-1] * 1.03,
            float(np.asarray(loss)[-1]),
            f"{df / 1e3:.2g} kHz",
            fontsize=8,
            color=TEXT,
            va="center",
        )
    exact_ranges = np.geomspace(50, 2000, 40)
    exact = np.array(
        [
            chirp_frequency_error_rms_hz(
                SOURCE, wf, offset_band_hz=OFFSET_BAND_HZ, range_m=float(r)
            )
            for r in exact_ranges
        ]
    )
    sigma = 2 * np.pi * exact * 2 * exact_ranges / SPEED_OF_LIGHT
    ax.plot(
        exact_ranges,
        10 * math.log10(math.e) * sigma**2,
        color=TEXT_SECONDARY,
        linestyle="--",
        linewidth=1.5,
        label=f"{cw / 1e3:.2g} kHz from the CW table, exact delay filter",
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(50, 2000)
    ax.set_ylim(1e-4, 20)
    xticks = [50, 100, 200, 500, 1000, 2000]
    ax.set_xticks(xticks)
    ax.set_xticklabels([str(t) for t in xticks])
    ax.xaxis.set_minor_formatter(mticker.NullFormatter())
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
    label_axes(
        ax,
        "Range [m]",
        "Doppler integration loss [dB]",
        "Loss against range for per-chirp frequency errors δf (rms)",
    )
    legend(ax, loc="upper left")
    fig.tight_layout()
    save(fig, output_dir / "coherence_loss.png")


def range_doppler(output_dir: Path) -> None:
    wf = waveform()
    # On range bin 120 (150.5 m), so that its cell holds the per-chirp error
    # exactly; between bins the window's straddle mixes in.
    beat_hz = 120 * wf.sample_rate_hz / wf.n_samples
    model = SingleReturnPhaseNoise(beat_hz / wf.effective_slope_hz_per_s, shared=SOURCE)
    result = phase_noise_fft(
        model,
        wf,
        offset_band_hz=OFFSET_BAND_HZ,
        sampling="real_phase_averaged",
        range_window="hann",
        doppler_window="hann",
    )
    noise = result.phase_noise_dbc
    peak_range = int(np.argmax(np.max(result.carrier_power, axis=0)))
    remote = np.abs(result.doppler_hz) > 0.25 / wf.chirp_repetition_time_s
    # The per-chirp error alone: its phase PSD over slow time times the
    # Doppler window's noise bandwidth, relative to the return's peak.
    df_psd = chirp_frequency_error_psd(
        SOURCE,
        wf,
        result.doppler_hz,
        offset_band_hz=OFFSET_BAND_HZ,
        range_window="hann",
        range_m=model.range_m,
    )
    doppler_bin_hz = 1 / wf.cpi_duration_s
    pedestal = (
        (2 * np.pi * model.delay_s) ** 2
        * df_psd
        * doppler_bin_hz
        * result.doppler_enbw_bins
    )

    fig = plt.figure(figsize=(10.5, 6.8), facecolor=SURFACE)
    grid = fig.add_gridspec(2, 2, height_ratios=(0.9, 1.0))
    ax_map = fig.add_subplot(grid[0, :])
    ax_range = fig.add_subplot(grid[1, 0])
    ax_doppler = fig.add_subplot(grid[1, 1])
    ax_map.set_facecolor(SURFACE)
    mesh = ax_map.pcolormesh(
        result.range_m,
        result.doppler_hz / 1e3,
        noise,
        vmin=-90,
        vmax=-50,
        cmap="Blues",
        shading="nearest",
        rasterized=True,
    )
    colourbar = fig.colorbar(mesh, ax=ax_map, pad=0.01)
    colourbar.set_label("Phase noise [dBc per cell]", color=TEXT, fontsize=9)
    colourbar.ax.tick_params(labelsize=8, colors=TEXT_SECONDARY, labelcolor=TEXT)
    outline: Any = colourbar.outline  # typed as a Spine in matplotlib's stubs
    outline.set_visible(False)
    ax_map.tick_params(colors=TEXT_SECONDARY, labelcolor=TEXT, labelsize=8)
    for side in ax_map.spines.values():
        side.set_visible(False)
    label_axes(
        ax_map,
        "Range [m]",
        "Doppler [kHz]",
        f"(a) Expected phase noise of a strong stationary return at "
        f"{model.range_m:.1f} m (its own peak is 0 dBc)",
    )

    style_axes(ax_range)
    ax_range.plot(
        result.range_m,
        linear_to_db(np.mean(result.phase_noise_power[remote], axis=0))
        - linear_to_db(result.carrier_peak_power),
        color=BLUE,
        linewidth=1.5,
    )
    ax_range.set_xlim(0, result.range_m[-1])
    ax_range.set_ylim(-90, -50)
    label_axes(
        ax_range,
        "Range [m]",
        "Phase noise [dBc per cell]",
        "(b) Away from its Doppler: the skirt",
    )

    style_axes(ax_doppler)
    ax_doppler.plot(
        result.doppler_hz / 1e3,
        result.carrier_dbc[:, peak_range],
        color=TEXT_SECONDARY,
        linewidth=1.5,
        label="the return itself",
    )
    ax_doppler.plot(
        result.doppler_hz / 1e3,
        noise[:, peak_range],
        color=BLUE,
        linewidth=1.5,
        label="phase noise",
    )
    ax_doppler.plot(
        result.doppler_hz / 1e3,
        linear_to_db(pedestal),
        color=ORANGE,
        linestyle="--",
        linewidth=1.5,
        label="per-chirp error alone",
    )
    ax_doppler.set_xlim(result.doppler_hz[0] / 1e3, result.doppler_hz[-1] / 1e3)
    ax_doppler.set_ylim(-90, 5)
    label_axes(
        ax_doppler,
        "Doppler [kHz]",
        "Power [dBc per cell]",
        f"(c) At its range ({result.range_m[peak_range]:.1f} m): the pedestal",
    )
    legend(ax_doppler, loc="center right")
    fig.tight_layout()
    save(fig, output_dir / "range_doppler.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    delay_filter(args.output_dir)
    per_chirp_error(args.output_dir)
    coherence_loss(args.output_dir)
    range_doppler(args.output_dir)


if __name__ == "__main__":
    main()
