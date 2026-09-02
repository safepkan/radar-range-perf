"""Range-performance baseline for Lannik Psi.

This study carries config 3 from the 2026-06-22 configuration comparison into
its own workspace, unchanged. It pins the starting front-end, antenna, waveform,
processing and evaluation assumptions so later modelling refinements can be
compared against a reproducible baseline. Run it from the repo root with::

    venv/bin/python studies/2026-09-02_lannik-psi/lannik_psi.py

It writes a "Pd + Pacq vs range" plot to the study-local ``generated/``
directory, prints diagnostics and, under an interactive Matplotlib backend,
opens the figure.

Scenario
--------
* Target: 1 m^2 RCS, Swerling 1, at boresight.
* Acquisition: closing at 15 m/s, 20 Hz frame rate, 2-of-3 confirmation.
* Pfa = 1e-6.

The initial range is far enough that single-scan Pd is solidly zero at the start
of the run. The plot is zoomed to the product's detection range.

Baseline modelling notes
------------------------
* "Coherent TX, coherent RX" is modelled as a transmit phased array
  (``transmit_coherent=True``: all TX radiating in phase, +20 log10(n_tx) on
  boresight) plus coherent RX beamforming -- not orthogonal MIMO.
* Boresight SNR is independent of the chirp slope; the slope only sets the
  maximum unambiguous range. The 2 MHz/us slope was not specified in the source
  study and is assumed so the unambiguous range clears the detection range.
* Phase noise, clutter and antenna sidelobes are not modelled, so the deep
  (long-range, high-SNR) tails are optimistic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt

from radarperf import (
    AntennaPair,
    BeamCombination,
    ConstantGainAntenna,
    ConstantRcsTarget,
    FmcwWaveform,
    Radar,
    RadialApproach,
    StandardProcessing,
    frontend,
    sweeps,
)
from radarperf.plotting import is_non_interactive_backend
from radarperf.sweeps import AcquisitionSweep

# --- Scenario (unchanged from the 2026-06-22 comparison) --------------------

CENTER_FREQUENCY_HZ = 77.0e9
TARGET = ConstantRcsTarget(rcs=1.0, swerling=1, name="1 m^2 Swerling-1")
CLOSING_SPEED_MPS = 15.0
FRAME_TIME_S = 1.0 / 20.0  # 20 Hz frame rate
CONFIRM = (2, 3)  # 2-of-3 sliding confirmation
PFA = 1.0e-6
INITIAL_RANGE_M = 3000.0
DETECTION_LEVELS = (0.5, 0.9)

SCENARIO_TEXT = (
    "1 m^2 RCS, Swerling 1, boresight  |  closing 15 m/s, 20 Hz frame, "
    "2-of-3 confirm  |  Pfa 1e-6"
)


@dataclass(frozen=True)
class Product:
    """The Lannik Psi baseline plus short notes for reports."""

    name: str
    radar: Radar
    waveform: FmcwWaveform
    front_end_note: str
    waveform_note: str
    processing_note: str


def lannik_psi() -> Product:
    """Build Lannik Psi from config 3 without model changes."""
    waveform = FmcwWaveform.from_slope(
        center_frequency_hz=CENTER_FREQUENCY_HZ,
        chirp_slope_hz_per_s=2.0e12,  # assumed; sets unambiguous range only
        sample_rate_hz=50.0e6,
        n_samples=1024,
        n_chirps=512,
    )
    radar = Radar(
        frontend=frontend.ctrx8188f(),
        waveform=waveform,
        processing=StandardProcessing(
            transmit_coherent=True,
            rx_combination=BeamCombination.COHERENT,
        ),
        antenna=AntennaPair.from_element(ConstantGainAntenna(17.0)),
        default_pfa=PFA,
    )
    return Product(
        name="Lannik Psi",
        radar=radar,
        waveform=waveform,
        front_end_note="CTRX8188F 8Tx/8Rx + 17 dBi antenna",
        waveform_note="1024 x 512 @ 50 MHz",
        processing_note="coherent TX (phased array) & coherent RX",
    )


def evaluate(product: Product) -> AcquisitionSweep:
    """Run the baseline closing-target acquisition sweep."""
    approach = RadialApproach(
        initial_range_m=INITIAL_RANGE_M, closing_speed_mps=CLOSING_SPEED_MPS
    )
    return sweeps.acquisition_sweep(
        product.radar,
        TARGET,
        approach,
        frame_time_s=FRAME_TIME_S,
        confirm=CONFIRM,
    )


def outermost_range_at(
    range_m: npt.NDArray[np.float64],
    values: npt.NDArray[np.float64],
    level: float,
) -> float:
    """Largest range whose curve value reaches ``level`` (NaN if never)."""
    mask = values >= level
    if not bool(mask.any()):
        return float("nan")
    return float(range_m[mask].max())


def ranges_at_levels(
    range_m: npt.NDArray[np.float64],
    values: npt.NDArray[np.float64],
) -> dict[float, float]:
    """Outermost ranges at the configured detection-probability levels."""
    return {
        level: outermost_range_at(range_m, values, level) for level in DETECTION_LEVELS
    }


def format_range_m(range_m: float) -> str:
    """Format a range for reports, preserving unavailable values cleanly."""
    if not np.isfinite(range_m):
        return "n/a"
    return f"{range_m:.0f} m"


def format_level_ranges(level_ranges: dict[float, float]) -> str:
    """Format ``50% @ ...`` / ``90% @ ...`` legend text."""
    return ", ".join(
        f"{level:.0%} @ {format_range_m(level_ranges[level])}"
        for level in DETECTION_LEVELS
    )


def nice_ceiling(value: float) -> float:
    """Round a positive range up to a tidy axis limit."""
    if not np.isfinite(value) or value <= 0.0:
        return 50.0
    step = 50.0 if value <= 500.0 else 100.0 if value <= 2000.0 else 250.0
    return float(np.ceil(value / step) * step)


def print_diagnostics(product: Product, acq: AcquisitionSweep) -> None:
    """Print the baseline link/processing budget and detection ranges."""
    assert acq.confirmation_pd is not None
    waveform = product.waveform
    budget = product.radar.processing.budget(
        waveform, product.radar.frontend.n_tx, product.radar.frontend.n_rx
    )
    unambiguous_range_m = waveform.max_unambiguous_range_m

    print(product.name)
    print(f"  front-end / antenna : {product.front_end_note}")
    print(f"  waveform            : {product.waveform_note}")
    print(f"  processing          : {product.processing_note}")
    print(f"  coherent gain       : {budget.coherent_gain_db:6.1f} dB")
    print(
        f"  detector looks      : {budget.n_noncoherent} signal "
        f"+ {budget.n_collapsing} collapsing"
    )
    pd_ranges = ranges_at_levels(acq.range_m, acq.pd)
    pacq_ranges = ranges_at_levels(acq.range_m, acq.confirmation_pd)
    pd09 = pd_ranges[0.9]
    print(f"  range resolution    : {waveform.range_resolution_m:6.2f} m")
    print(f"  max unambig. range  : {unambiguous_range_m:6.0f} m")
    for level in DETECTION_LEVELS:
        print(
            f"  Pd {level:.0%} single scan : " f"{format_range_m(pd_ranges[level]):>7}"
        )
    for level in DETECTION_LEVELS:
        print(
            f"  Pacq {level:.0%} (2-of-3)  : "
            f"{format_range_m(pacq_ranges[level]):>7}"
        )
    if np.isfinite(pd09) and unambiguous_range_m < pd09:
        print(
            "  ** WARNING: unambiguous range is below the Pd=0.9 range; "
            "pick a gentler chirp slope."
        )


def plot_product(product: Product, acq: AcquisitionSweep, path: Path) -> None:
    """Plot single-scan Pd and 2-of-3 Pacq vs range and save to ``path``."""
    assert acq.confirmation_pd is not None
    pd_ranges = ranges_at_levels(acq.range_m, acq.pd)
    pacq_ranges = ranges_at_levels(acq.range_m, acq.confirmation_pd)

    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    ax.plot(
        acq.range_m,
        acq.pd,
        label=f"Pd single scan ({format_level_ranges(pd_ranges)})",
    )
    ax.plot(
        acq.range_m,
        acq.confirmation_pd,
        label=f"Pacq 2-of-3 ({format_level_ranges(pacq_ranges)})",
    )
    for level in DETECTION_LEVELS:
        ax.axhline(level, color="0.6", lw=0.8, ls=":")

    edge = outermost_range_at(acq.range_m, acq.pd, 0.02)
    xmax = nice_ceiling(edge * 1.1)
    ax.set_xlim(0.0, xmax)
    ax.set_ylim(0.0, 1.0)

    unambiguous_range_m = product.waveform.max_unambiguous_range_m
    if unambiguous_range_m <= xmax:
        ax.axvline(unambiguous_range_m, color="C3", lw=0.8, ls="--")
        ax.text(
            unambiguous_range_m,
            0.05,
            "max unambiguous range ",
            rotation=90,
            va="bottom",
            ha="right",
            fontsize=7,
            color="C3",
        )

    ax.set_xlabel("range [m]")
    ax.set_ylabel("probability")
    ax.set_title(
        f"{product.name}\n"
        f"{product.front_end_note}\n"
        f"{product.waveform_note}  |  {product.processing_note}",
        fontsize=9,
    )
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower left")
    fig.text(0.5, 0.005, SCENARIO_TEXT, ha="center", fontsize=8, color="0.3")
    fig.tight_layout(rect=(0.0, 0.03, 1.0, 1.0))
    fig.savefig(path, dpi=130)


def main() -> None:
    product = lannik_psi()
    generated_dir = Path(__file__).parent / "generated"
    generated_dir.mkdir(exist_ok=True)

    print(f"Scenario: {SCENARIO_TEXT}")
    print(f"Initial range: {INITIAL_RANGE_M:.0f} m\n")

    acquisition = evaluate(product)
    print_diagnostics(product, acquisition)
    path = generated_dir / "pd_pacq_vs_range.png"
    plot_product(product, acquisition, path)
    print(f"\n  saved {path}")

    if not is_non_interactive_backend():
        plt.show()


if __name__ == "__main__":
    main()
