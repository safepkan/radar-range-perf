"""Field captures: the receiver's IF response for a signal against its background.

The receiver background rises towards low beat frequencies (NOTES, The receiver
background). If that is the IF gain's shape, a signal is shaped alike and the
SNR at a given range does not depend on the beat frequency. If it is receiver
noise, the SNR improves as the beat frequency rises.

The short ramp sweeps twice the medium ramp's bandwidth in the same payload at
the same sample rate. Its samples that cover the medium ramp's RF band
(field_common.matching_samples) therefore see the reflector in the same RF band
and range cell, through the same multipath, at twice the beat frequency. With
the reflector untouched between the two captures, the change of its
zero-Doppler power from medium to short sub-band, dS = G(2f) / G(f), is the
IF response's change over that octave. The background change dN = N(2f) / N(f)
comes from the capture with no TX enabled, so it holds only the receiver. Then

  T = dS - dN [dB]

is the change in SNR from f to 2f for equal processing: 0 if the background's
shape is gain shape, -dN if the background's excess is noise added before the
high-pass filter. Below about 1 MHz the high-pass filter shapes the signal;
there a positive T means part of the background is not shaped like a signal.

The backgrounds of the TX-off, empty-scene and sky captures (channel-independent
remote-Doppler floor, window_scene.analyze) show whether the TX changes them.
CPIs flagged as interfered are dropped. Writes generated/field/if/summary.json,
if_test.png and notx_background.npz for field_level.py.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

from carkit_common import SPEED_OF_LIGHT, FloatArray, db, write_summary
from field_common import (
    GENERATED_DIR,
    NOMINAL_RANGES_M,
    NOTX_CASE,
    data_argument,
    empty_case,
    kept_frames,
    load,
    matching_samples,
    placement_case,
    reflector_beat,
    zero_doppler_amplitudes,
)
from window_common import Capture
from window_scene import BACKGROUND_REFERENCE_HZ, analyze

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BACKGROUND_CASES = ("notx", "empty-medium", "empty-short", "sky-1tx", "sky-8tx")
# Pairs whose per-RX ratios spread by at most CLEAN_RX_SPREAD_DB are clean;
# up to USABLE_RX_SPREAD_DB usable; beyond that the scene changed between the
# two captures.
CLEAN_RX_SPREAD_DB = 0.5
USABLE_RX_SPREAD_DB = 1.0
# Neighbouring beat frequencies closer than this fraction are joined when the
# octave ratios are chained into one IF response.
CHAIN_TOLERANCE = 0.10
# Below this the high-pass filter shapes signal and background, so -dN is not
# the noise reading's prediction there.
HIGH_PASS_REGION_HZ = 1.0e6
# Pairs summed for the result over the walk's beat frequencies (medium beat).
WALK_BAND_HZ = (1.0e6, 4.0e6)


def compare(medium: Capture, short: Capture, data: Path | None) -> dict[str, Any]:
    sub = matching_samples(
        short.start_frequency_hz,
        short.sampled_bandwidth_hz,
        short.n_samples,
        medium.start_frequency_hz,
        medium.sampled_bandwidth_hz,
    )
    medium_beat = reflector_beat(medium, load(empty_case("medium"), data))
    short_beat = reflector_beat(short, load(empty_case("short"), data))
    medium_frames, medium_dropped = kept_frames(medium)
    short_frames, short_dropped = kept_frames(short)
    f_m, a_m = zero_doppler_amplitudes(medium, medium_frames, medium_beat)
    f_s, a_s = zero_doppler_amplitudes(short, short_frames, short_beat, sub)
    f_full, a_full = zero_doppler_amplitudes(short, short_frames, short_beat)
    p_m, p_s, p_full = (np.abs(a) ** 2 for a in (a_m, a_s, a_full))
    n = min(len(p_m), len(p_s))
    per_rx = db(p_s.mean(axis=0)) - db(p_m.mean(axis=0))
    per_cpi = db(p_s[:n].mean(axis=1)) - db(p_m[:n].mean(axis=1))
    return {
        "medium_case": medium.case,
        "short_case": short.case,
        "short_samples": [sub.start, sub.stop],
        "medium_range_m": float(f_m * SPEED_OF_LIGHT / (2 * medium.slope_hz_per_s)),
        "short_range_m": float(f_full * SPEED_OF_LIGHT / (2 * short.slope_hz_per_s)),
        "medium_beat_hz": f_m,
        "short_sub_beat_hz": f_s,
        "short_full_beat_hz": f_full,
        "cpis_used": [len(medium_frames), len(short_frames)],
        "cpis_dropped_interference": [medium_dropped, short_dropped],
        "signal_change_db": float(db(p_s.mean()) - db(p_m.mean())),
        "signal_change_full_short_band_db": float(db(p_full.mean()) - db(p_m.mean())),
        "per_rx_change_db": per_rx.tolist(),
        "rx_spread_db": float(per_rx.std()),
        "cpi_spread_db": float(per_cpi.std()),
        "medium_cpi_std_db": float(db(p_m.mean(axis=1)).std()),
    }


def chain_response(
    pairs: list[dict[str, Any]], reference_hz: float
) -> dict[str, float]:
    """IF response [dB] at the pairs' beat frequencies relative to ``reference_hz``.

    Each pair gives G(2f) - G(f). Pairs are joined where one's upper frequency
    and the next one's lower frequency differ by less than CHAIN_TOLERANCE,
    treating the response as equal there. Only the chain containing
    ``reference_hz`` is returned; unjoined pairs stay undefined.
    """
    usable = sorted(
        (p for p in pairs if p["rx_spread_db"] <= CLEAN_RX_SPREAD_DB),
        key=lambda p: p["medium_beat_hz"],
    )
    chains: list[list[dict[str, Any]]] = []
    for pair in usable:
        if chains:
            last = chains[-1][-1]["short_sub_beat_hz"]
            if abs(pair["medium_beat_hz"] / last - 1) < CHAIN_TOLERANCE:
                chains[-1].append(pair)
                continue
        chains.append([pair])
    for chain in chains:
        values: dict[float, float] = {}
        level = 0.0
        for pair in chain:
            values.setdefault(pair["medium_beat_hz"], level)
            level += pair["signal_change_db"]
            values[pair["short_sub_beat_hz"]] = level
        anchor = min(values, key=lambda f: abs(f / reference_hz - 1))
        if abs(anchor / reference_hz - 1) < CHAIN_TOLERANCE:
            offset = values[anchor]
            return {f"{f:.6g}": v - offset for f, v in sorted(values.items())}
    return {}


def plot(
    output: Path,
    backgrounds: dict[str, dict[str, FloatArray]],
    pairs: list[dict[str, Any]],
) -> None:
    figure, (left, right) = plt.subplots(1, 2, figsize=(13, 5), layout="constrained")
    for case, values in backgrounds.items():
        beat = values["beat_hz"]
        reference = (beat >= BACKGROUND_REFERENCE_HZ[0]) & (
            beat <= BACKGROUND_REFERENCE_HZ[1]
        )
        level = db(values["independent_floor"])
        left.plot(beat / 1e6, level - np.median(level[reference]), lw=0.8, label=case)
    left.set(
        xscale="log",
        xlim=(0.2, 25),
        ylim=(-4, 3),
        xlabel="Beat frequency [MHz]",
        ylabel="dB relative to 18–24 MHz",
        title="Channel-independent remote-Doppler background",
    )
    left.grid(alpha=0.3, which="both")
    left.legend(fontsize=8)
    for pair in pairs:
        f = pair["medium_beat_hz"] / 1e6
        clean = pair["rx_spread_db"] <= CLEAN_RX_SPREAD_DB
        error = pair["rx_spread_db"] / np.sqrt(len(pair["per_rx_change_db"]))
        right.errorbar(
            f,
            pair["snr_change_db"],
            yerr=error,
            fmt="o" if clean else "x",
            color="C0",
            capsize=3,
            label=None,
        )
        if pair["medium_beat_hz"] >= HIGH_PASS_REGION_HZ:
            right.plot(f, -pair["background_change_db"], "s", mfc="none", color="C1")
        right.annotate(
            pair["medium_case"].split("-")[1],
            (f, pair["snr_change_db"]),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=7,
        )
    right.axhline(0, color="k", lw=0.8)
    right.plot([], [], "o", color="C0", label="Measured T = dS − dN (x: scene changed)")
    right.plot(
        [],
        [],
        "s",
        mfc="none",
        color="C1",
        label="If the background excess is noise: −dN (above the high-pass filter)",
    )
    right.plot([], [], "k-", lw=0.8, label="If it is gain shape: 0")
    right.set(
        xscale="log",
        xlabel="Medium-ramp beat frequency f [MHz] (short sub-band at 2f)",
        ylabel="SNR change from f to 2f [dB]",
        title="Reflector at fixed positions, two slopes, same RF band",
    )
    right.grid(alpha=0.3, which="both")
    right.legend(fontsize=8)
    figure.savefig(output / "if_test.png", dpi=110)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_argument(parser)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "if")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    backgrounds: dict[str, dict[str, FloatArray]] = {}
    background_summary: dict[str, Any] = {}
    for case in BACKGROUND_CASES:
        capture = load(case, args.data, verify=True)
        summary, arrays = analyze(capture)
        backgrounds[case] = arrays
        background_summary[case] = {
            key: summary[key]
            for key in (
                "cpis",
                "tx_channels",
                "slope_mhz_per_us",
                "interference_cpis",
                "independent_background_db_counts2",
                "total_over_independent_1_10_mhz_db",
                "background_shape_db",
            )
        }
        reference = (arrays["beat_hz"] >= BACKGROUND_REFERENCE_HZ[0]) & (
            arrays["beat_hz"] <= BACKGROUND_REFERENCE_HZ[1]
        )
        background_summary[case]["total_db_counts2"] = float(
            np.median(db(arrays["total_floor"][reference]))
        )
    notx = backgrounds[NOTX_CASE]
    np.savez_compressed(
        args.output / "notx_background.npz",
        allow_pickle=False,
        beat_hz=notx["beat_hz"],
        independent_floor=notx["independent_floor"],
        total_floor=notx["total_floor"],
    )

    def background_db(beat_hz: float) -> float:
        return float(np.interp(beat_hz, notx["beat_hz"], db(notx["independent_floor"])))

    pairs = []
    for nominal in NOMINAL_RANGES_M:
        medium = load(placement_case("medium", nominal), args.data, verify=True)
        short = load(placement_case("short", nominal), args.data, verify=True)
        pair = compare(medium, short, args.data)
        pair["background_change_db"] = background_db(
            pair["short_sub_beat_hz"]
        ) - background_db(pair["medium_beat_hz"])
        pair["snr_change_db"] = pair["signal_change_db"] - pair["background_change_db"]
        pairs.append(pair)
        print(
            f"{nominal:3d} m: f {pair['medium_beat_hz'] / 1e6:5.2f} -> "
            f"{pair['short_sub_beat_hz'] / 1e6:5.2f} MHz, dS {pair['signal_change_db']:+.2f}, "
            f"dN {pair['background_change_db']:+.2f}, T {pair['snr_change_db']:+.2f} dB, "
            f"RX spread {pair['rx_spread_db']:.2f} dB"
        )

    reference_hz = next(
        p["short_sub_beat_hz"] for p in pairs if p["medium_case"] == "medium-20m"
    )
    walk_band = [
        p
        for p in pairs
        if WALK_BAND_HZ[0] <= p["medium_beat_hz"] < WALK_BAND_HZ[1]
        and p["rx_spread_db"] <= CLEAN_RX_SPREAD_DB
    ]
    above_high_pass = [
        p
        for p in pairs
        if p["medium_beat_hz"] >= HIGH_PASS_REGION_HZ
        and p["rx_spread_db"] <= USABLE_RX_SPREAD_DB
    ]
    plot(args.output, backgrounds, pairs)
    write_summary(
        args.output,
        {
            "backgrounds": background_summary,
            "pairs": pairs,
            "clean_rx_spread_db": CLEAN_RX_SPREAD_DB,
            "usable_rx_spread_db": USABLE_RX_SPREAD_DB,
            "above_high_pass": {
                "pairs": [p["medium_case"] for p in above_high_pass],
                "snr_change_sum_db": float(
                    sum(p["snr_change_db"] for p in above_high_pass)
                ),
                "noise_reading_sum_db": float(
                    sum(-p["background_change_db"] for p in above_high_pass)
                ),
            },
            "walk_band": {
                "medium_beat_band_mhz": [f / 1e6 for f in WALK_BAND_HZ],
                "pairs": [p["medium_case"] for p in walk_band],
                "snr_change_sum_db": float(sum(p["snr_change_db"] for p in walk_band)),
                "noise_reading_sum_db": float(
                    sum(-p["background_change_db"] for p in walk_band)
                ),
            },
            "if_response_db_relative_to_hz": reference_hz,
            "if_response_db": chain_response(pairs, reference_hz),
        },
    )


if __name__ == "__main__":
    main()
