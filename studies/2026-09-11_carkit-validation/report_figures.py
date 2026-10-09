"""The report's figures, from the pipeline's tracked summaries.

Needs no raw data: it reads the summary.json and per-frame CSV files that the
steps write and git tracks, and writes generated/report/levels.png and
generated/report/timing.png for README.md.

levels.png puts each set-up's measured SNR against the model without hardware
losses on one basis:

- The noise is referred to 5.3 MHz IF, where the receiver's noise is flat as
  the model assumes. The two-slope test (field_if.py) gives a fixed
  reflector's SNR change from 1.25 to 2.51 MHz and from 2.65 to 5.33 MHz;
  frequencies within 10 % are taken as equal. A level measured at 1.25 MHz
  gets both changes, one at 2.5-2.65 MHz the second. The walk, spread over
  1.1-3.3 MHz, gets the second plus the part of the first above its mean log
  beat frequency, taking the first as even over its octave.
- The home-made reflector is taken at the RCS chamber_tx1.py derives from the
  lab comparison with the finite-aperture correction, not at the 11.27 dBsm
  the steps use.
- The chamber rows are chamber_tx1.py's comparisons at 5.3 MHz (TX backoff
  nominal and as measured on the reflector) and chamber_level.py's for the
  first session (high-pass corner nominal and measured), with the
  finite-aperture correction.
- The walk's range spans walk_reference_snr.py's CPI-averaging conventions;
  the tripod's its 16 and 34 m placements with both waveforms.
- The carried runs of 2026-10-01 and the walk's way out are placed by their
  level differences in the 15-27, 27-38 and 38-52 m bands to the tripod and
  to the walk's way back (field_runs.py), which compare directly since the
  receiver noise at the ADC is the same in both sessions.
- The band is the data sheet's bound on the antenna's realized gain below its
  directivity over both passes (walk_model.py). The housing cover's loss is
  unknown.

timing.png shows the per-chirp frequency error of the 2026-10-06 chirp-timing
test against the time in fast-settling mode (flyback and wait), with the
settling fit for each pre-payload (window_timing.py), the CW phase-noise
table's typical prediction and the error measured with Infineon's timing.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
import numpy as np  # noqa: E402

from carkit_common import SPEED_OF_LIGHT, STUDY_DIR, write_summary  # noqa: E402

GENERATED = STUDY_DIR / "generated"
OUTPUT_DIR = GENERATED / "report"

# Chart colours: surface, text inks, two categorical slots and an ordinal
# blue ramp (steps 250, 400, 550, 700), from the reference palette.
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
BAND = "#f0efec"
REFERENCE_COLOUR = "#2a78d6"
HOME_MADE_COLOUR = "#eb6834"
PRE_PAYLOAD_COLOURS = ("#86b6ef", "#3987e5", "#1c5cab", "#0d366b")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def referral_db(pairs: list[dict[str, Any]], walk_beat_hz: float) -> dict[str, float]:
    """SNR change to 5.3 MHz from a level at 1.25 MHz, 2.5 MHz and the walk's."""
    by_case = {pair["medium_case"]: pair for pair in pairs}
    low, high = by_case["medium-20m"], by_case["medium-40m"]
    first, second = float(low["snr_change_db"]), float(high["snr_change_db"])
    share = math.log2(walk_beat_hz / low["medium_beat_hz"]) / math.log2(
        low["short_full_beat_hz"] / low["medium_beat_hz"]
    )
    return {
        "1.25 MHz": first + second,
        "2.5 MHz": second,
        "walk": second + first * (1.0 - share),
    }


def walk_mean_beat_hz(capture: dict[str, Any]) -> float:
    """Geometric mean beat frequency of the walk's inbound CPIs."""
    path = GENERATED / "walk" / "extract" / "per_frame.csv"
    with path.open() as handle:
        ranges = [
            float(row["range_m"])
            for row in csv.DictReader(handle)
            if row["leg"] == "inbound"
        ]
    beats = 2 * np.asarray(ranges) * capture["slope_hz_per_s"] / SPEED_OF_LIGHT
    return float(np.exp(np.mean(np.log(beats))))


def level_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Measured minus model [dB] per set-up, and the inputs behind them."""
    tx1 = read_json(GENERATED / "chamber" / "2026-10-09" / "tx1" / "summary.json")
    first = read_json(GENERATED / "chamber" / "level" / "summary.json")
    walk_model = read_json(GENERATED / "walk" / "model" / "summary.json")
    walk_snr = read_json(GENERATED / "walk" / "reference_snr" / "summary.json")
    capture = read_json(GENERATED / "walk" / "extract" / "summary.json")["capture"]
    field_if = read_json(GENERATED / "field" / "if" / "summary.json")
    field_level = read_json(GENERATED / "field" / "level" / "summary.json")
    runs = read_json(GENERATED / "field" / "runs" / "summary.json")

    walk_beat = walk_mean_beat_hz(capture)
    referral = referral_db(field_if["pairs"], walk_beat)
    rcs_dbsm = tx1["home_made_reflector_rcs"]["rcs_dbsm"]
    rcs_shift = -(rcs_dbsm - field_level["reflector_rcs_dbsm_in_model"])

    chamber = [
        value["measured_minus_model_db"]
        for key, value in tx1["level"].items()
        if key.startswith("steep chirp") and key.endswith("noise 5.3 MHz")
    ]
    chamber_first = [
        value["measured_minus_model_db"]
        for key, value in first["comparisons"].items()
        if key.endswith("noise at 5.3 MHz")
    ]

    # The walk at its own beat frequencies, by averaging convention.
    model = walk_snr["model_db"]
    conventions = walk_snr["target_free"]["inbound"]
    headline = conventions["linear_rx_mean_then_db_mean_over_cpis"] - model
    walk_shift = referral["walk"] + rcs_shift
    walk = [
        conventions[key] - model + walk_shift
        for key in (
            "linear_rx_mean_then_db_mean_over_cpis",
            "linear_rx_mean_then_median_over_cpis",
            "linear_mean_over_rx_and_cpis",
            "db_mean_over_rx_and_cpis",
        )
    ]

    beat_referral = {
        "medium-20m": referral["1.25 MHz"],
        "short-20m": referral["2.5 MHz"],
        "medium-40m": referral["2.5 MHz"],
        "short-40m": 0.0,
    }
    tripod = [
        placement["residual_local_db"] + beat_referral[placement["case"]] + rcs_shift
        for placement in field_level["placements"]
        if placement["case"] in beat_referral
    ]
    tripod_mean = float(np.mean(tripod))
    carried_field = [
        tripod_mean + change for change in runs["tx1_runs_minus_tripod_db"].values()
    ]
    walk_legs = runs["walk_bands"]
    walk_out = [
        walk[0] + walk_legs["outbound"][band]["mean_db"] - inbound["mean_db"]
        for band, inbound in walk_legs["inbound"].items()
    ]

    rows = [
        {
            "label": "Chamber, 2026-10-09: TX1 at 10 dB backoff",
            "group": "reference",
            "values": chamber,
        },
        {
            "label": "Chamber, 2026-09-29: backoff outside the chip's range",
            "group": "reference",
            "values": chamber_first,
        },
        {
            "label": "Carried towards the radar, 2026-09-11",
            "group": "home-made",
            "values": walk,
        },
        {
            "label": "On a tripod, 2026-10-01",
            "group": "home-made",
            "values": tripod,
        },
        {
            "label": "Carried towards the radar, 2026-10-01",
            "group": "home-made",
            "values": carried_field,
        },
        {
            "label": "Carried away from the radar, 2026-09-11",
            "group": "home-made",
            "values": walk_out,
        },
    ]
    inputs = {
        "walk_mean_beat_hz": walk_beat,
        "referral_to_5_3_mhz_db": referral,
        "home_made_rcs_dbsm": rcs_dbsm,
        "rcs_shift_db": rcs_shift,
        "walk_headline_at_own_if_db": headline,
        "antenna_loss_bound_both_passes_db": 2
        * walk_model["inputs"]["antenna_loss_bound_db_per_pass"],
    }
    return rows, inputs


def style_axes(ax: Any) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(TEXT_SECONDARY)
    ax.tick_params(colors=TEXT_SECONDARY, labelcolor=TEXT)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def signed(value: float) -> str:
    """A signed number with a typographic minus."""
    return f"{value:+.1f}".replace("-", "\u2212")


def plot_levels(output: Path, rows: list[dict[str, Any]], band_db: float) -> None:
    colours = {"reference": REFERENCE_COLOUR, "home-made": HOME_MADE_COLOUR}
    fig, ax = plt.subplots(figsize=(8.5, 3.9), facecolor=SURFACE)
    style_axes(ax)
    ax.grid(axis="y", visible=False)
    top = len(rows) - 0.2
    ax.axvspan(-band_db, 0.0, color=BAND, zorder=0)
    ax.text(
        -band_db / 2,
        top - 0.05,
        "antenna loss allowed\nby the data sheet",
        ha="center",
        va="top",
        fontsize=7,
        color=TEXT_SECONDARY,
    )
    ax.axvline(0.0, color=TEXT_SECONDARY, linewidth=1.0, zorder=1)
    for index, row in enumerate(rows):
        y = len(rows) - 1 - index
        values = np.asarray(row["values"], dtype=float)
        colour = colours[row["group"]]
        low, high = float(values.min()), float(values.max())
        ax.plot(
            [low, high],
            [y, y],
            color=colour,
            linewidth=3,
            solid_capstyle="round",
            zorder=2,
        )
        ax.scatter(
            values,
            np.full(values.size, y),
            s=42,
            color=colour,
            edgecolors=SURFACE,
            linewidths=1.5,
            zorder=3,
        )
        text = (
            f"{signed(high)} dB"
            if abs(high - low) < 0.05
            else f"{signed(low)} to {signed(high)} dB"
        )
        ax.text(
            1.02,
            y,
            text,
            transform=ax.get_yaxis_transform(),
            va="center",
            ha="left",
            fontsize=8,
            color=TEXT_SECONDARY,
        )
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([row["label"] for row in reversed(rows)], fontsize=8.5)
    ax.set_xlim(-15.0, 2.0)
    ax.set_ylim(-0.6, top + 0.5)
    ax.set_xlabel("Measured SNR minus model [dB]", color=TEXT)
    handles = [
        Line2D([], [], color=REFERENCE_COLOUR, marker="o", linewidth=3, markersize=6),
        Line2D([], [], color=HOME_MADE_COLOUR, marker="o", linewidth=3, markersize=6),
    ]
    ax.set_xticks(range(-15, 1, 5))
    fig.legend(
        handles,
        [
            "10 dBsm reference reflector, fixed mount",
            "Home-made reflector, aim not controlled",
        ],
        loc="upper left",
        bbox_to_anchor=(0.01, 0.99),
        ncol=2,
        fontsize=8,
        frameon=False,
        labelcolor=TEXT,
    )
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.93))
    fig.savefig(output, dpi=200, facecolor=SURFACE)
    plt.close(fig)


def plot_timing(output: Path, timing: dict[str, Any]) -> dict[str, Any]:
    fit = timing["fit"]
    floor, excess = fit["floor_hz"], fit["excess_at_zero_hz2"]
    tau_fast, tau_pre = fit["tau_fast_us"], fit["tau_pre_us"]

    def model_hz(pre_us: float, fast_us: Any) -> Any:
        fast = np.asarray(fast_us, dtype=float)
        return np.sqrt(floor**2 + excess * np.exp(-fast / tau_fast - pre_us / tau_pre))

    cases = timing["cases"]
    pres = sorted({case["pre_payload_us"] for case in cases.values()})
    cw = [
        value
        for case in cases.values()
        for key, value in case["cw_prediction_rms_hz"].items()
        if key.endswith("typical_hz")
    ]
    fig, ax = plt.subplots(figsize=(7.0, 4.2), facecolor=SURFACE)
    style_axes(ax)
    ax.axhspan(min(cw) / 1e3, max(cw) / 1e3, color=BAND, zorder=0)
    ax.text(
        95,
        min(cw) / 1e3 * 1.03,
        "CW phase-noise table, typical",
        ha="right",
        va="bottom",
        fontsize=7.5,
        color=TEXT_SECONDARY,
    )
    measured_fast = [case["fast_settling_us"] for case in cases.values()]
    for pre, colour in zip(pres, PRE_PAYLOAD_COLOURS):
        grid = np.geomspace(min(measured_fast) * 0.8, 100.0, 200)
        ax.plot(grid, model_hz(pre, grid) / 1e3, color=colour, linewidth=2)
        chosen = [case for case in cases.values() if case["pre_payload_us"] == pre]
        fast = np.array([case["fast_settling_us"] for case in chosen])
        df = np.array([case["df_rms_hz"] for case in chosen]) / 1e3
        spread = np.array([case["df_rms_p5_p95_hz"] for case in chosen]).T / 1e3
        ax.errorbar(
            fast,
            df,
            yerr=[df - spread[0], spread[1] - df],
            fmt="o",
            color=colour,
            markersize=6,
            markeredgecolor=SURFACE,
            markeredgewidth=1.2,
            elinewidth=1.2,
            label=f"pre-payload {pre:g} µs",
        )
    # Infineon's timing: from the lowest lower end to the highest measured value.
    measured = [entry["measured_df_rms_hz"] for entry in timing["infineon_timing"]]
    lower = [
        (entry.get("measured_range_hz") or entry["measured_p5_p95_hz"])[0]
        for entry in timing["infineon_timing"]
    ]
    ax.text(
        7.3,
        2.1,
        "Infineon's timing, 0.12 µs of\nflyback and wait: "
        f"{min(lower) / 1e3:.0f}–{max(measured) / 1e3:.0f} kHz measured",
        ha="left",
        va="bottom",
        fontsize=8,
        color=TEXT_SECONDARY,
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(7.0, 100.0)
    ax.set_ylim(2.0, 12.0)
    ticks = [2, 3, 4, 5, 6, 8, 10, 12]
    ax.set_yticks(ticks)
    ax.set_yticklabels([str(t) for t in ticks])
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    xticks = [7, 10, 15, 20, 30, 50, 100]
    ax.set_xticks(xticks)
    ax.set_xticklabels([str(t) for t in xticks])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlabel("Flyback and wait between chirps [µs]", color=TEXT)
    ax.set_ylabel("Per-chirp frequency error, rms [kHz]", color=TEXT)
    ax.legend(loc="upper right", fontsize=8, frameon=False, labelcolor=TEXT)
    fig.tight_layout()
    fig.savefig(output, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return {
        "cw_typical_hz": [min(cw), max(cw)],
        "infineon_measured_hz": [min(lower), max(measured)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    rows, inputs = level_rows()
    plot_levels(
        args.output / "levels.png", rows, inputs["antenna_loss_bound_both_passes_db"]
    )
    timing = read_json(GENERATED / "window" / "2026-10-06" / "timing" / "summary.json")
    timing_inputs = plot_timing(args.output / "timing.png", timing)
    write_summary(
        args.output,
        {
            "levels": {
                "basis": "measured SNR minus model without hardware losses, noise "
                "referred to 5.3 MHz IF, home-made reflector at its corrected RCS",
                "inputs": inputs,
                "rows": [
                    {
                        "label": row["label"],
                        "group": row["group"],
                        "values_db": row["values"],
                        "range_db": [min(row["values"]), max(row["values"])],
                    }
                    for row in rows
                ],
            },
            "timing": timing_inputs,
        },
    )


if __name__ == "__main__":
    main()
