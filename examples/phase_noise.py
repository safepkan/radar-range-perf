"""Single-return diagnostic using the reported chamber acquisition as defaults.

FFT windows and the RF reference remain assumptions; the hardware high-pass
response is not modeled. Use --help to override settings. For the guided
progression, run examples/phase_noise_tutorial.py instead.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

import matplotlib.pyplot as plt
import numpy as np

from radarperf import FmcwWaveform
from radarperf.phase_noise import (
    SingleReturnPhaseNoise,
    ctrx8188f_phase_noise,
    phase_noise_fft,
)
from radarperf.plotting import (
    is_non_interactive_backend,
    plot_phase_noise_cut,
    plot_phase_noise_map,
    plot_phase_noise_spectrum,
)
from radarperf.units import linear_to_db


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--range-m", type=float, default=2.3)
    parser.add_argument(
        "--slope-mhz-us",
        type=float,
        default=400.0 / 10.24,
        help="chirp slope in MHz/us; default is 400 MHz across the 10.24 us payload",
    )
    parser.add_argument("--sample-rate-mhz", type=float, default=50.0)
    parser.add_argument("--samples", type=int, default=512)
    parser.add_argument(
        "--chirps",
        type=int,
        default=1024,
        help="retained chirps, excluding dummy chirps",
    )
    parser.add_argument("--crt-us", type=float, default=15.96)
    parser.add_argument(
        "--center-frequency-ghz",
        type=float,
        default=76.78,
        help="RF reference for velocity conversion; default assumes a 76.58-76.98 GHz payload",
    )
    parser.add_argument("--doppler-hz", type=float, default=0.0)
    parser.add_argument("--rf-band", choices=("76-77", "77-81"), default="76-77")
    parser.add_argument("--level", choices=("typical", "maximum"), default="typical")
    parser.add_argument(
        "--sampling",
        choices=("real_phase_averaged", "complex"),
        default="real_phase_averaged",
    )
    parser.add_argument(
        "--correlation", choices=("stationary", "independent"), default="stationary"
    )
    parser.add_argument("--range-window", default="blackmanharris")
    parser.add_argument("--doppler-window", default="hann")
    parser.add_argument("--differential-delay-ns", type=float, default=0.0)
    parser.add_argument("--offset-min-hz", type=float, default=1.0)
    parser.add_argument("--offset-max-mhz", type=float, default=20.0)
    parser.add_argument("--integration-oversample", type=int, default=4)
    parser.add_argument("--max-integration-points", type=int, default=4_000_000)
    parser.add_argument(
        "--extrapolation", choices=("error", "constant", "slope"), default="constant"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "radarperf_phase_noise",
    )
    parser.add_argument("--no-show", action="store_true")
    args = parser.parse_args()

    source = ctrx8188f_phase_noise(
        rf_band=args.rf_band, level=args.level, extrapolation=args.extrapolation
    )
    model = SingleReturnPhaseNoise.from_range(
        args.range_m,
        shared=source,
        differential_delay_s=args.differential_delay_ns * 1e-9,
    )
    wf = FmcwWaveform.from_slope(
        center_frequency_hz=args.center_frequency_ghz * 1e9,
        chirp_slope_hz_per_s=args.slope_mhz_us * 1e12,
        sample_rate_hz=args.sample_rate_mhz * 1e6,
        n_samples=args.samples,
        n_chirps=args.chirps,
        chirp_repetition_time_s=args.crt_us * 1e-6,
    )
    band = (args.offset_min_hz, args.offset_max_mhz * 1e6)
    rd = phase_noise_fft(
        model,
        wf,
        offset_band_hz=band,
        doppler_hz=args.doppler_hz,
        range_window=args.range_window,
        doppler_window=args.doppler_window,
        sampling=args.sampling,
        chirp_correlation=args.correlation,
        integration_oversample=args.integration_oversample,
        max_integration_points=args.max_integration_points,
    )
    range_only = phase_noise_fft(
        model,
        wf,
        offset_band_hz=band,
        range_doppler=False,
        doppler_hz=args.doppler_hz,
        range_window=args.range_window,
        sampling=args.sampling,
        integration_oversample=args.integration_oversample,
        max_integration_points=args.max_integration_points,
    )

    offsets = np.geomspace(1e4, 1e7, 800)
    fig, axes = plt.subplots(2, 3, figsize=(17, 9), layout="constrained")
    plot_phase_noise_spectrum(model, offsets, ax=axes[0, 0])
    axes[0, 0].set_title(source.name)
    axes[0, 1].semilogx(offsets, linear_to_db(model.cancellation(offsets)))
    axes[0, 1].set_xlabel("offset from return [Hz]")
    axes[0, 1].set_ylabel("shared-source transfer [dB]")
    axes[0, 1].set_title(
        f"delay = {model.delay_s * 1e9:.2f} ns + {args.differential_delay_ns:g} ns"
    )
    axes[0, 1].grid(True, alpha=0.3)
    plot_phase_noise_cut(range_only, ax=axes[0, 2])
    axes[0, 2].set_title("single-chirp range FFT")
    # Use the predicted span to make small variations in an almost flat
    # pedestal visible, rather than stretching the scale up to the carrier.
    finite_noise = rd.phase_noise_dbc[np.isfinite(rd.phase_noise_dbc)]
    floor_dbc = float(np.floor(finite_noise.min())) if finite_noise.size else -140.0
    ceiling_dbc = (
        max(floor_dbc + 1, float(np.ceil(finite_noise.max())))
        if finite_noise.size
        else -40.0
    )
    # Tiny window sidelobes outside the modeled noise band should not set
    # the map's color span and hide structure in the main noise pedestal.
    floor_dbc = max(floor_dbc, ceiling_dbc - 20.0)
    plot_phase_noise_map(
        rd, ax=axes[1, 0], floor_dbc=floor_dbc, ceiling_dbc=ceiling_dbc
    )
    plot_phase_noise_cut(rd, ax=axes[1, 1])
    plot_phase_noise_cut(rd, axis="doppler", ax=axes[1, 2])
    for ax in (axes[0, 2], axes[1, 1], axes[1, 2]):
        ax.set_ylim(-150, 5)
    for label, ax in zip("ABCDEF", axes.flat):
        ax.set_title(f"({label}) {ax.get_title()}")
    fig.suptitle(
        f"Single return at {args.range_m:g} m | {args.sampling} | {args.correlation} chirp noise\n"
        f"{args.slope_mhz_us:g} MHz/µs; {args.sample_rate_mhz:g} MS/s; {args.samples} samples/chirp; {args.chirps} chirps; {args.crt_us:g} µs spacing\n"
        f"Ideal IF (hardware HPF omitted); TX CW spectrum assumed shared; {args.extrapolation} extrapolation"
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output_dir / "phase_noise.png", dpi=150)
    np.savez(
        args.output_dir / "phase_noise.npz",
        range_m=rd.range_m,
        doppler_hz=rd.doppler_hz,
        velocity_mps=rd.velocity_mps,
        phase_noise_dbc=rd.phase_noise_dbc,
        carrier_dbc=rd.carrier_dbc,
        total_dbc=rd.total_dbc,
        range_only_phase_noise_dbc=range_only.phase_noise_dbc,
        range_only_carrier_dbc=range_only.carrier_dbc,
        integration_step_hz=rd.integration_step_hz,
        offset_band_hz=band,
        settings=str(vars(args)),
        source=source.source,
    )
    print(f"{source.name}\n{source.source}")
    print(
        f"RF TX spectrum assumed entirely shared; extrapolation: {args.extrapolation}"
    )
    print(f"Sampling: {args.sampling}; chirp correlation: {args.correlation}")
    print(
        f"ADC duration: {wf.adc_duration_s * 1e6:.3f} us; "
        f"sampled bandwidth: {wf.bandwidth_hz / 1e6:.3f} MHz; "
        f"range-bin spacing: {wf.range_resolution_m:.4f} m"
    )
    print(
        f"PRF: {1 / wf.chirp_repetition_time_s:.3f} Hz; "
        f"CPI: {wf.cpi_duration_s * 1e3:.4f} ms; "
        f"Doppler-bin spacing: {1 / wf.cpi_duration_s:.3f} Hz"
    )
    print(
        f"Target beat: {(wf.effective_slope_hz_per_s * model.delay_s + args.doppler_hz) / 1e3:.3f} kHz; "
        f"velocity reference: {wf.center_frequency_hz / 1e9:g} GHz"
    )
    print(f"Ideal IF filter; modeled oscillator offsets: {band} Hz")
    print("The chamber's 300 kHz high-pass response is not included.")
    print(
        f"RD integration step: {rd.integration_step_hz:.3f} Hz (double oversampling to check convergence)"
    )
    print(f"Carrier peak loss: {float(linear_to_db(rd.carrier_peak_power)):.3f} dB")
    print(
        "Scale using measured_peak_level + phase_noise_dbc; no RCS or TX power needed."
    )
    print(f"Saved plots and arrays to {args.output_dir}")
    if not args.no_show and not is_non_interactive_backend():
        plt.show()
    plt.close(fig)


if __name__ == "__main__":
    main()
