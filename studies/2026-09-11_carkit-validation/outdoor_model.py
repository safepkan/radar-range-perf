"""Compare the measured per-chirp frequency error with the CW datasheet spectrum.

Reads the outputs of outdoor_scene.py and outdoor_phase.py; the raw data are
not needed. Two predictions use the toolbox's CTRX8188F CW table (upper band,
since the captures are centred near 78 GHz), treated as noise shared by TX and
RX and delay-filtered by 4 sin²(pi f tau):

1. The same quantity as measured. A return's per-chirp phase is the
   Blackman-Harris-weighted mean of its phase difference over the sampled
   payload, sampled once per chirp. Its slow-time PSD is therefore

       S(f_D) = sum_k P(f_D + k PRF) |H(f_D + k PRF)|²,

   with P the delay-filtered phase PSD and H the normalized weighting's
   frequency response. Divided by (2 pi tau)², this is the equivalent
   frequency-error PSD that outdoor_phase.py measures.
2. The full range-Doppler prediction (``phase_noise_fft``), averaged over
   |Doppler| > 5 kHz, at every range bin. Away from the return this is the
   broad skirt from high offsets, which the per-chirp quantity does not see.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Literal

import matplotlib
import numpy as np

from carkit_common import (
    FloatArray,
    db,
    display_groups,
    enbw_bins,
    write_summary,
)
from outdoor_common import (
    CASES,
    FAR_DOPPLER_HZ,
    GENERATED_DIR,
    doppler_window,
    range_window,
    read_summary,
)
from radarperf import FmcwWaveform
from radarperf.phase_noise import (
    SingleReturnPhaseNoise,
    ctrx8188f_phase_noise,
    phase_noise_fft,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RF_BAND: Literal["77-81"] = "77-81"
LEVELS: tuple[Literal["typical", "maximum"], ...] = ("typical", "maximum")
OFFSET_BAND_HZ = (1.0, 20e6)
# Resolution of |H(f)|² relative to the sample rate (2^20-point FFT).
RESPONSE_FFT_SIZE = 2**20


def model(
    range_m: float, level: Literal["typical", "maximum"]
) -> SingleReturnPhaseNoise:
    return SingleReturnPhaseNoise.from_range(
        range_m,
        shared=ctrx8188f_phase_noise(
            rf_band=RF_BAND, level=level, extrapolation="constant"
        ),
    )


def per_chirp_frequency_psd(
    phase_noise: SingleReturnPhaseNoise,
    doppler_hz: FloatArray,
    chirp_period_s: float,
    sample_rate_hz: float,
    n_samples: int,
) -> FloatArray:
    """Two-sided PSD [Hz²/Hz] of the per-chirp equivalent frequency error."""
    weights = range_window(n_samples)
    response = np.abs(np.fft.rfft(weights, RESPONSE_FFT_SIZE) / weights.sum()) ** 2
    response_hz = np.fft.rfftfreq(RESPONSE_FFT_SIZE, 1 / sample_rate_hz)
    prf = 1 / chirp_period_s
    folds = np.arange(
        -int(OFFSET_BAND_HZ[1] / prf) - 1, int(OFFSET_BAND_HZ[1] / prf) + 2
    )
    offsets = doppler_hz[:, None] + folds[None, :] * prf
    inside = (np.abs(offsets) >= OFFSET_BAND_HZ[0]) & (
        np.abs(offsets) <= OFFSET_BAND_HZ[1]
    )
    density = np.zeros(offsets.shape)
    density[inside] = phase_noise.residual_psd_per_hz(offsets[inside]) * np.interp(
        np.abs(offsets[inside]), response_hz, response
    )
    return np.asarray(density.sum(axis=1) / (2 * np.pi * phase_noise.delay_s) ** 2)


def far_doppler_prediction(
    scene: dict[str, Any], phase_noise: SingleReturnPhaseNoise
) -> tuple[FloatArray, FloatArray]:
    """Model power over |Doppler| > 5 kHz per range bin, dBc to the peak bin."""
    nc, ns, _ = scene["shape_chirp_sample_rx"]
    fs = float(scene["sample_rate_hz"])
    # The metadata period, 15.9600003826 us, is 798 ticks of 20 ns; use the
    # exact grid to avoid an artificial fractional-clock integration.
    period = round(float(scene["chirp_period_s"]) * fs) / fs
    waveform = FmcwWaveform.from_slope(
        float(scene["center_frequency_hz"]),
        float(scene["slope_hz_per_s"]),
        fs,
        ns,
        nc,
        period,
    )
    result = phase_noise_fft(
        phase_noise,
        waveform,
        offset_band_hz=OFFSET_BAND_HZ,
        range_window="blackmanharris",
        doppler_window="hann",
        sampling="real_phase_averaged",
    )
    far = np.abs(result.doppler_hz) > FAR_DOPPLER_HZ
    power = np.mean(10 ** (result.phase_noise_dbc[far] / 10), axis=0)
    return np.asarray(result.range_m), np.asarray(db(power))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "model")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    scene = read_summary("scene")
    background_range = scene["background_range_m"]

    figure, axes = plt.subplots(1, 3, figsize=(17, 5), layout="constrained")
    summaries: dict[str, Any] = {}
    cut_axes = {"400MHz-5m": axes[1], "800MHz-5m": axes[2]}
    for index, case in enumerate(CASES):
        case_scene = scene["cases"][case]
        phase = np.load(GENERATED_DIR / "phase" / f"{case}.npz")
        measured = np.load(GENERATED_DIR / "scene" / f"{case}.npz")
        doppler = phase["doppler_hz"]
        period = float(phase["chirp_period_s"])
        nc, ns, _ = case_scene["shape_chirp_sample_rx"]
        band = np.abs(doppler) > FAR_DOPPLER_HZ
        enbw = enbw_bins(doppler_window(nc))
        bin_hz = 1 / (nc * period)
        measured_psd = phase["common_df_per_bin"][:, 0] / (enbw * bin_hz)
        measured_rms = float(np.sqrt(np.sum(measured_psd[band]) * bin_hz))
        reflector_m = float(case_scene["reflector_range_m"])

        summary: dict[str, Any] = {
            "reflector_range_m": reflector_m,
            "measured_df_rms_hz": measured_rms,
        }
        predictions = {}
        for level in LEVELS:
            psd = per_chirp_frequency_psd(
                model(reflector_m, level),
                doppler,
                period,
                case_scene["sample_rate_hz"],
                ns,
            )
            predictions[level] = psd
            rms = float(np.sqrt(np.sum(psd[band]) * bin_hz))
            summary[f"cw_{level}_df_rms_hz"] = rms
            summary[f"excess_over_cw_{level}_db"] = float(
                20 * np.log10(measured_rms / rms)
            )

        frequency, level_psd = display_groups(doppler, measured_psd)
        axes[0].plot(
            frequency / 1e3, db(level_psd), color=f"C{index}", label=f"{case}, measured"
        )
        if index == 0:
            for level, style in zip(LEVELS, ("--", ":")):
                frequency, level_psd = display_groups(doppler, predictions[level])
                axes[0].plot(
                    frequency / 1e3,
                    db(level_psd),
                    color="black",
                    linestyle=style,
                    label=f"CW datasheet, {level}",
                )

        model_range, model_far_db = far_doppler_prediction(
            case_scene, model(reflector_m, "typical")
        )
        ranges = measured["range_m"]
        peak = 10 ** (case_scene["reflector_peak_db_counts2"] / 10)
        broad = (
            (model_range >= background_range[0])
            & (model_range <= background_range[1])
            & (np.abs(model_range - reflector_m) > scene["background_exclusion_m"])
        )
        raise_db = summary["excess_over_cw_typical_db"]
        summary.update(
            {
                "cw_typical_far_doppler_at_reflector_dbc": float(
                    model_far_db[np.argmin(np.abs(model_range - reflector_m))]
                ),
                "cw_typical_far_doppler_broad_dbc": float(
                    np.median(model_far_db[broad])
                ),
                "measured_background_dbc": case_scene["far_doppler_background_dbc"],
            }
        )
        summary["raised_broad_minus_measured_background_db"] = (
            summary["cw_typical_far_doppler_broad_dbc"]
            + raise_db
            - summary["measured_background_dbc"]
        )
        summaries[case] = summary
        if case in cut_axes:
            axis = cut_axes[case]
            axis.plot(
                ranges, db(measured["far_doppler_power"] / peak), label="Measured"
            )
            axis.plot(model_range, model_far_db, label="CW typical")
            axis.plot(
                model_range,
                model_far_db + raise_db,
                label=f"CW typical + {raise_db:.1f} dB",
            )
            axis.axvline(reflector_m, color="gray", linestyle=":", linewidth=1)
            axis.set(
                xlim=(0, 16),
                ylim=(-95, -60),
                xlabel="Apparent range [m]",
                ylabel="dBc per bin",
                title=f"{case}: mean over |Doppler| > 5 kHz, RX{scene['rx']}",
            )

    axes[0].set(
        xlim=(0, 31.4),
        ylim=(0, 45),
        xlabel="|Doppler| [kHz]",
        ylabel="dB Hz²/Hz",
        title="Per-chirp frequency error at the reflector",
    )
    for axis in axes:
        axis.grid(alpha=0.3)
        axis.legend(fontsize=8)
    figure.suptitle(
        f"CTRX8188F CW table, {RF_BAND} GHz, shared by TX and RX, "
        f"integrated over {OFFSET_BAND_HZ[0]:g} Hz–{OFFSET_BAND_HZ[1] / 1e6:g} MHz"
    )
    figure.savefig(args.output / "model.png", dpi=130)
    plt.close(figure)
    write_summary(
        args.output,
        {
            "rf_band": RF_BAND,
            "offset_band_hz": list(OFFSET_BAND_HZ),
            "cases": summaries,
        },
    )


if __name__ == "__main__":
    main()
