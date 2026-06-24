"""Pd (single scan) and 2-of-3 acquisition probability vs range for the current
Lannik Omega, a modified Lannik Omega and a separate future product.

Reference / traceability script: it pins the exact front-end, antenna, waveform
and processing assumptions behind the presentation figures so the numbers can be
reproduced and audited later.  Run it from the repo root with the project venv::

    venv/bin/python studies/2026-06-22_config-comparison/config_comparison.py

It writes one "Pd + Pacq vs range" PNG per configuration into the study-local
``generated/`` directory; generated PNGs are git-ignored. It also prints a
diagnostics table and, under an interactive Matplotlib backend, opens the figures.

Scenario (common to all three configurations)
---------------------------------------------
* Target: 1 m^2 RCS, Swerling 1, at boresight.
* Acquisition: closing at 15 m/s, 20 Hz frame rate, 2-of-3 confirmation.
* Pfa = 1e-6.

A single large ``initial_range_m`` is used for every configuration (so the
single-scan Pd is solidly zero at the start of the run) and each plot is then
zoomed to that configuration's own detection range.

Modelling notes
---------------
* "Coherent TX, coherent RX" is modelled as a transmit phased array
  (``transmit_coherent=True``: all TX radiating in phase, +20 log10(n_tx) on
  boresight) plus coherent RX beamforming -- not orthogonal MIMO.
* Boresight SNR is independent of the chirp slope; the slope only sets the
  maximum unambiguous range.  Config 1 therefore uses the long-range mode
  (4.5 MHz/us, the only one of the three modes whose unambiguous range clears
  the detection range).  The slopes for configs 2 and 3 were not specified and
  are *assumed* here, chosen so the unambiguous range clears the detection range
  -- see the printed diagnostics and adjust if a mode is pinned.
* Phase noise, clutter and antenna sidelobes are not modelled, so the deep
  (long-range, high-SNR) tails are optimistic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt

from radarperf import (
    AntennaPair,
    BeamCombination,
    ConstantGainAntenna,
    ConstantRcsTarget,
    FmcwWaveform,
    MimoScheme,
    Radar,
    RadialApproach,
    StandardProcessing,
    antenna,
    frontend,
    sweeps,
)
from radarperf.plotting import is_non_interactive_backend
from radarperf.sweeps import AcquisitionSweep

# --- Scenario ---------------------------------------------------------------

CENTER_FREQUENCY_HZ = 77.0e9
TARGET = ConstantRcsTarget(rcs=1.0, swerling=1, name="1 m^2 Swerling-1")
CLOSING_SPEED_MPS = 15.0
FRAME_TIME_S = 1.0 / 20.0  # 20 Hz frame rate
CONFIRM = (2, 3)  # 2-of-3 sliding confirmation
PFA = 1.0e-6
# One range, far enough that Pd is ~0 for every configuration at the start.
INITIAL_RANGE_M = 3000.0
DETECTION_LEVELS = (0.5, 0.9)

SCENARIO_TEXT = (
    "1 m^2 RCS, Swerling 1, boresight  |  closing 15 m/s, 20 Hz frame, "
    "2-of-3 confirm  |  Pfa 1e-6"
)


@dataclass(frozen=True)
class Config:
    """A named radar configuration plus short notes for the figures."""

    name: str
    radar: Radar
    waveform: FmcwWaveform
    front_end_note: str
    waveform_note: str
    processing_note: str


def config_1() -> Config:
    """Lannik Omega as-is: AWR2E44P + SENCITY THIS-II, DDM-MIMO."""
    waveform = FmcwWaveform.from_slope(
        center_frequency_hz=CENTER_FREQUENCY_HZ,
        chirp_slope_hz_per_s=4.5e12,  # long-range mode (medium 9, short 18 MHz/us)
        sample_rate_hz=30.0e6,
        n_samples=384,
        n_chirps=6 * 128,
    )
    radar = Radar(
        frontend=frontend.awr2e44p(),
        waveform=waveform,
        processing=StandardProcessing(
            mimo=MimoScheme.DDM,
            rx_combination=BeamCombination.NONCOHERENT,
            tx_combination=BeamCombination.NONCOHERENT,
            n_doppler_subbands=6,
        ),
        antenna=antenna.sencity_this_ii(),
        default_pfa=PFA,
    )
    return Config(
        name="Lannik Omega (as-is)",
        radar=radar,
        waveform=waveform,
        front_end_note="AWR2E44P 4Tx/4Rx + SENCITY THIS-II (~16 dBi)",
        waveform_note="384 x 768 @ 30 MHz, 4.5 MHz/us",
        processing_note="DDM-MIMO 6 subbands, non-coherent TX & RX",
    )


def config_2() -> Config:
    """Modified Lannik Omega: AWR2E44P + 21 dBi antenna, fully coherent."""
    waveform = FmcwWaveform.from_slope(
        center_frequency_hz=CENTER_FREQUENCY_HZ,
        chirp_slope_hz_per_s=1.5e12,  # assumed; sets unambiguous range only
        sample_rate_hz=30.0e6,
        n_samples=512,
        n_chirps=512,
    )
    radar = Radar(
        frontend=frontend.awr2e44p(),
        waveform=waveform,
        processing=StandardProcessing(
            transmit_coherent=True,
            rx_combination=BeamCombination.COHERENT,
        ),
        antenna=AntennaPair.from_element(ConstantGainAntenna(21.0)),
        default_pfa=PFA,
    )
    return Config(
        name="Modified Lannik Omega",
        radar=radar,
        waveform=waveform,
        front_end_note="AWR2E44P 4Tx/4Rx + 21 dBi antenna",
        waveform_note="512 x 512 @ 30 MHz",
        processing_note="coherent TX (phased array) & coherent RX",
    )


def config_3() -> Config:
    """New product: CTRX8188F + 17 dBi antenna, fully coherent."""
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
    return Config(
        name="New product (CTRX8188F)",
        radar=radar,
        waveform=waveform,
        front_end_note="CTRX8188F 8Tx/8Rx + 17 dBi antenna",
        waveform_note="1024 x 512 @ 50 MHz",
        processing_note="coherent TX (phased array) & coherent RX",
    )


def evaluate(cfg: Config) -> AcquisitionSweep:
    """Run the closing-target acquisition sweep for one configuration."""
    approach = RadialApproach(
        initial_range_m=INITIAL_RANGE_M, closing_speed_mps=CLOSING_SPEED_MPS
    )
    return sweeps.acquisition_sweep(
        cfg.radar,
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


def print_diagnostics(index: int, cfg: Config, acq: AcquisitionSweep) -> None:
    """Print the link/processing budget and detection ranges for a config."""
    assert acq.confirmation_pd is not None
    wf = cfg.waveform
    budget = cfg.radar.processing.budget(
        wf, cfg.radar.frontend.n_tx, cfg.radar.frontend.n_rx
    )
    r_unamb = wf.max_unambiguous_range_m

    print(f"Config {index}: {cfg.name}")
    print(f"  front-end / antenna : {cfg.front_end_note}")
    print(f"  waveform            : {cfg.waveform_note}")
    print(f"  processing          : {cfg.processing_note}")
    print(f"  coherent gain       : {budget.coherent_gain_db:6.1f} dB")
    print(
        f"  detector looks      : {budget.n_noncoherent} signal "
        f"+ {budget.n_collapsing} collapsing"
    )
    pd_ranges = ranges_at_levels(acq.range_m, acq.pd)
    pacq_ranges = ranges_at_levels(acq.range_m, acq.confirmation_pd)
    pd09 = pd_ranges[0.9]
    print(f"  range resolution    : {wf.range_resolution_m:6.2f} m")
    print(f"  max unambig. range  : {r_unamb:6.0f} m")
    for level in DETECTION_LEVELS:
        print(
            f"  Pd {level:.0%} single scan : " f"{format_range_m(pd_ranges[level]):>7}"
        )
    for level in DETECTION_LEVELS:
        print(
            f"  Pacq {level:.0%} (2-of-3)  : "
            f"{format_range_m(pacq_ranges[level]):>7}"
        )
    if np.isfinite(pd09) and r_unamb < pd09:
        print(
            "  ** WARNING: unambiguous range is below the Pd=0.9 range; "
            "pick a gentler chirp slope."
        )
    print()


def plot_config(index: int, cfg: Config, acq: AcquisitionSweep, path: str) -> None:
    """Plot Pd single-scan and 2-of-3 Pacq vs range and save to ``path``."""
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

    r_unamb = cfg.waveform.max_unambiguous_range_m
    if r_unamb <= xmax:
        ax.axvline(r_unamb, color="C3", lw=0.8, ls="--")
        ax.text(
            r_unamb,
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
        f"Config {index}: {cfg.name}\n"
        f"{cfg.front_end_note}\n"
        f"{cfg.waveform_note}  |  {cfg.processing_note}",
        fontsize=9,
    )
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower left")
    fig.text(0.5, 0.005, SCENARIO_TEXT, ha="center", fontsize=8, color="0.3")
    fig.tight_layout(rect=(0.0, 0.03, 1.0, 1.0))
    fig.savefig(path, dpi=130)


def main() -> None:
    configs = [config_1(), config_2(), config_3()]
    generated_dir = os.path.join(os.path.dirname(__file__), "generated")
    os.makedirs(generated_dir, exist_ok=True)

    print(f"Scenario: {SCENARIO_TEXT}")
    print(f"Common initial range: {INITIAL_RANGE_M:.0f} m\n")

    summary: list[tuple[str, float, float, float, float, float]] = []
    for index, cfg in enumerate(configs, start=1):
        acq = evaluate(cfg)
        assert acq.confirmation_pd is not None
        print_diagnostics(index, cfg, acq)
        pd_ranges = ranges_at_levels(acq.range_m, acq.pd)
        pacq_ranges = ranges_at_levels(acq.range_m, acq.confirmation_pd)
        path = os.path.join(generated_dir, f"config{index}_pd_pacq_vs_range.png")
        plot_config(index, cfg, acq, path)
        print(f"  saved {path}\n")
        summary.append(
            (
                f"Config {index}",
                pd_ranges[0.5],
                pd_ranges[0.9],
                pacq_ranges[0.5],
                pacq_ranges[0.9],
                cfg.waveform.max_unambiguous_range_m,
            )
        )

    print("Summary (outermost range at which each criterion is met):")
    print(
        f"  {'':9}  {'Pd 50%':>8}  {'Pd 90%':>8}  "
        f"{'Pacq 50%':>9}  {'Pacq 90%':>9}  {'R_unamb':>8}"
    )
    for label, pd05, pd09, pacq05, pacq09, r_unamb in summary:
        print(
            f"  {label:9}  {format_range_m(pd05):>8}  "
            f"{format_range_m(pd09):>8}  {format_range_m(pacq05):>9}  "
            f"{format_range_m(pacq09):>9}  {format_range_m(r_unamb):>8}"
        )

    if not is_non_interactive_backend():
        plt.show()


if __name__ == "__main__":
    main()
