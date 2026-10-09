"""Lannik Psi range performance after the CARKIT validation.

Reuses the model of the concluded Lannik Psi antenna-concept study
(``studies/2026-09-02_lannik-psi/lannik_psi.py``) unchanged and applies the one
change decided since its conclusion on 2026-10-01: the receiver at the +3 dB RX
gain step, whose typical noise figure is 9.7 dB at 10 MHz IF instead of the
0 dB step's 10.2 dB (CTRX8188F target datasheet rev. 0.20, Table 30). Infineon
confirmed that the datasheet's noise modes are these gain steps, and the CARKIT
validation study (``studies/2026-09-11_carkit-validation``) measured the radar
within 1 dB of the model at +3 dB. Psi is optimized for range, so it runs at
+3 dB. Everything else is the antenna-concept study's baseline.

Writes ``generated/summary.json`` with every number in README.md, and the
figures ``generated/coverage_summary.png`` (single-scan Pd coverage of both RX
variants, from the concluded study's plotting function) and
``generated/steps.png`` (boresight Pd 50% range from the June study to now).
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

STUDY_DIR = Path(__file__).parent
sys.path.insert(0, str(STUDY_DIR.parent / "2026-09-02_lannik-psi"))

import lannik_psi as psi  # noqa: E402
from radarperf import Atmosphere, Rain  # noqa: E402

GENERATED_DIR = STUDY_DIR / "generated"
NOISE_FIGURE_DB = 9.7
RADOME_ONE_WAY_DB = (0.2, 0.5, 1.0)
DIRECTIONS_DEG = (
    ("Boresight", 0.0, 0.0),
    ("6° horizontally", 6.0, 0.0),
    ("6° vertically", 0.0, 6.0),
)

# The concluded study's breakdown rows, in order, with the labels used here.
CONCLUDED_STEPS = (
    "Same model, current toolbox",
    "Proposed TX aperture instead of the TX placeholder",
    "Large RX subarrays and 64 RX beams instead of the RX placeholder",
    "False alarms held per range–Doppler cell over all beams",
    "76.5 GHz instead of 77 GHz",
    "Atmosphere at 1000 m",
    "Antenna loss, 1.0 dB each side (RFQ target)",
    "Per-chirp frequency error, 3.5 kHz: 2026-10-01 baseline",
)
NEW_STEP = "Receiver at +3 dB gain, noise figure 9.7 dB"
SMALL_STEP = "Small RX instead, same assumptions"

# Chart colours from the reference palette: surface, text inks, a neutral for
# the end bars, and blue and red for range gained and lost.
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
NEUTRAL = "#8a8984"
GAIN = "#2a78d6"
LOSS = "#e34948"


def baseline(layout: psi.RxAntennaLayout, **overrides: Any) -> psi.Product:
    """The current baseline for one RX variant, with optional overrides."""
    settings: dict[str, Any] = {"noise_figure_db": NOISE_FIGURE_DB}
    settings.update(overrides)
    return psi.lannik_psi(layout, **settings)


def steps() -> list[dict[str, Any]]:
    """Boresight Pd ranges step by step from the published June figure."""
    concluded = psi.breakdown_products()
    if len(concluded) != len(CONCLUDED_STEPS) + 1:
        raise RuntimeError("the concluded study's breakdown has changed")
    rows: list[tuple[str, psi.Product]] = [
        (label, product) for label, (_, product) in zip(CONCLUDED_STEPS, concluded[:-1])
    ]
    rows.append((NEW_STEP, baseline(psi.RX_SUPPLIED_LAYOUT)))
    rows.append((SMALL_STEP, baseline(psi.RX_SQUARE_LAYOUT)))

    june = psi.JUNE_PUBLISHED_PD_RANGES_M
    out: list[dict[str, Any]] = [
        {"step": "June config 3, as published", "pd50_m": june[0], "pd90_m": june[1]}
    ]
    previous = june[0]
    for label, product in rows:
        ranges = psi.pd_ranges(product)
        # The small variant is compared with the large baseline, not chained.
        reference = out[-1]["pd50_m"] if label == SMALL_STEP else previous
        out.append(
            {
                "step": label,
                "pd50_m": ranges[0.5],
                "pd90_m": ranges[0.9],
                "change_percent": 100.0 * (ranges[0.5] / reference - 1.0),
                "equivalent_db": psi.equivalent_db(ranges[0.5], reference),
            }
        )
        if label != SMALL_STEP:
            previous = ranges[0.5]
    return out


def radome_per_0_1_db_percent() -> float:
    """Change of the large variant's Pd 50% range per 0.1 dB of radome loss."""
    layout = psi.RX_SUPPLIED_LAYOUT
    reference = psi.pd_ranges(baseline(layout))[0.5]
    with_radome = psi.pd_ranges(
        baseline(layout, losses=replace(psi.LOSSES, radome_one_way_loss_db=0.1))
    )[0.5]
    return 100.0 * (with_radome / reference - 1.0)


def directions() -> dict[str, dict[str, dict[str, float]]]:
    """Pd 50% and 90% ranges of both variants along the reported directions."""
    out: dict[str, dict[str, dict[str, float]]] = {}
    for name, layout in (
        ("large", psi.RX_SUPPLIED_LAYOUT),
        ("small", psi.RX_SQUARE_LAYOUT),
    ):
        product = baseline(layout)
        out[name] = {}
        for label, azimuth, elevation in DIRECTIONS_DEG:
            ranges = psi.pd_ranges(product, azimuth, elevation)
            out[name][label] = {"pd50_m": ranges[0.5], "pd90_m": ranges[0.9]}
    return out


def sensitivities() -> list[dict[str, Any]]:
    """Changes to the large variant's baseline, one term at a time."""
    layout = psi.RX_SUPPLIED_LAYOUT
    losses = psi.LOSSES
    light_rain = Atmosphere(
        psi.ENVIRONMENT.specific_attenuation_db_per_km
        + Rain(rain_rate_mm_per_hr=1.0).specific_attenuation_db_per_km(
            psi.CENTER_FREQUENCY_HZ
        )
    )
    rows: list[tuple[str, psi.Product]] = [
        ("Baseline", baseline(layout)),
        (
            "Noise figure at the datasheet maximum, 12.7 dB",
            baseline(layout, noise_figure_db=12.7),
        ),
        (
            "Receiver left at the chip's default 0 dB gain, noise figure 10.2 dB",
            baseline(layout, noise_figure_db=10.2),
        ),
        (
            "TX power 1 dB lower (temperature)",
            baseline(layout, losses=replace(losses, tx_power_derating_db=1.0)),
        ),
        (
            "Light rain, 1 mm/h (attenuation only)",
            baseline(layout, environment=light_rain),
        ),
        (
            "Per-chirp frequency error of 21 kHz (too little time between chirps)",
            baseline(
                layout, losses=replace(losses, chirp_frequency_error_rms_hz=21.0e3)
            ),
        ),
        (
            "Sea-level instead of 1000 m atmosphere",
            baseline(layout, environment=Atmosphere()),
        ),
    ]
    # The radome is not defined, so no value is typical: a few losses, and the
    # cost per 0.1 dB in the summary (radome_per_0_1_db_percent).
    for one_way_db in RADOME_ONE_WAY_DB:
        rows.append(
            (
                f"Radome, {one_way_db:.1f} dB one way",
                baseline(
                    layout,
                    losses=replace(losses, radome_one_way_loss_db=one_way_db),
                ),
            )
        )

    out: list[dict[str, Any]] = []
    reference: dict[float, float] = {}
    for label, product in rows:
        ranges = psi.pd_ranges(product)
        if not reference:
            reference = ranges
        out.append(
            {
                "change": label,
                "pd50_m": ranges[0.5],
                "pd90_m": ranges[0.9],
                "pd50_change_percent": 100.0 * (ranges[0.5] / reference[0.5] - 1.0),
                "pd90_change_percent": 100.0 * (ranges[0.9] / reference[0.9] - 1.0),
                "equivalent_db": psi.equivalent_db(ranges[0.5], reference[0.5]),
            }
        )
    return out


def plot_steps(path: Path, rows: list[dict[str, Any]]) -> None:
    """Waterfall of the boresight Pd 50% range from June to now.

    Each change is a bar from the previous range to the new one; the published
    June figure and the current estimate are markers, since the axis does not
    start at zero.
    """
    chained = [row for row in rows if row["step"] != SMALL_STEP]
    labels = [row["step"] for row in chained] + ["Current estimate, large RX"]
    ranges = [row["pd50_m"] for row in chained]
    totals = {0: ranges[0], len(labels) - 1: ranges[-1]}
    fig, ax = plt.subplots(figsize=(8.5, 4.9), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    y = np.arange(len(labels))[::-1]
    for index in range(len(labels)):
        if index in totals:
            value = totals[index]
            ax.scatter(
                [value],
                [y[index]],
                s=70,
                color=NEUTRAL,
                zorder=3,
                edgecolors=SURFACE,
                linewidths=1.5,
            )
            ax.text(
                value + 12,
                y[index],
                f"{value:.0f} m",
                va="center",
                fontsize=8.5,
                color=TEXT,
            )
            continue
        start_m, value = ranges[index - 1], ranges[index]
        ax.barh(
            y[index],
            abs(value - start_m),
            left=min(start_m, value),
            height=0.62,
            color=GAIN if value > start_m else LOSS,
        )
        ax.text(
            max(start_m, value) + 8,
            y[index],
            f"{value - start_m:+.0f} m".replace("-", "\u2212"),
            va="center",
            fontsize=8,
            color=TEXT_SECONDARY,
        )
    for index in range(1, len(labels)):
        ax.plot(
            [ranges[index - 1]] * 2,
            [y[index - 1] - 0.31, y[index] + 0.31],
            color=TEXT_SECONDARY,
            linewidth=0.6,
        )
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.5, color=TEXT)
    ax.set_xlim(800, 1200)
    ax.set_xlabel(
        "Boresight single-scan Pd 50% range, large RX variant [m]", color=TEXT
    )
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(TEXT_SECONDARY)
    ax.tick_params(colors=TEXT_SECONDARY, labelcolor=TEXT)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)


def write_summary(summary: dict[str, Any]) -> None:
    text = json.dumps(summary, indent=2) + "\n"
    (GENERATED_DIR / "summary.json").write_text(text)
    print(text, end="")


def main() -> None:
    GENERATED_DIR.mkdir(exist_ok=True)
    step_rows = steps()
    summary = {
        "noise_figure_db": NOISE_FIGURE_DB,
        "steps": step_rows,
        "directions": directions(),
        "sensitivities_large": sensitivities(),
        "radome_per_0_1_db_percent": radome_per_0_1_db_percent(),
    }
    plot_steps(GENERATED_DIR / "steps.png", step_rows)
    psi.plot_coverage_summary(
        (baseline(psi.RX_SUPPLIED_LAYOUT), baseline(psi.RX_SQUARE_LAYOUT)),
        ("Large RX (baseline)", "Small RX (first prototype)"),
        GENERATED_DIR / "coverage_summary.png",
    )
    write_summary(summary)


if __name__ == "__main__":
    main()
