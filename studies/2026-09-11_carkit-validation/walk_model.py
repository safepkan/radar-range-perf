"""Radar-equation model of the CARKIT TX1 walk and its measured comparison.

TX1 only, eight RX compared per channel (no coherent RX combination), CTRX8188F
datasheet TX power and noise figure, the boresight gains of CARKIT's antenna
(the FARAD-IV preset), the walk waveform and Blackman windows with fourfold
padding (no residual straddle, no CFAR loss).
The reflector is modeled as a nonfluctuating 10 dBsm target at boresight.

That reference model has no hardware losses. The CARKIT terms (see the notes,
"Loss terms") change it: the noise figure at the RX gain the walk used, the
residual straddle of the padded FFTs, the antenna's loss from directivity to
realized gain up to its datasheet bound, and, at the walk's own ranges, the
atmosphere and the per-chirp frequency error. The loss of CARKIT's housing
cover is not known and is left out.

Prints the link budgets and, if walk_reference_snr.py has been run, the measured
reference scaled to 100 m and 10 dBsm; writes generated/walk/model/summary.json.
"""

from __future__ import annotations

import json
import math
from typing import Any

from carkit_common import write_summary
from walk_common import (
    GENERATED_DIR,
    REFERENCE_RANGE_M,
    REFERENCE_RCS_DBSM,
    WALKING_RCS_DBSM,
)
from radarperf import (
    WINDOW_LOSS_BLACKMAN_DB,
    Atmosphere,
    BeamCombination,
    ConstantRcsTarget,
    FmcwWaveform,
    Geometry,
    Radar,
    StandardProcessing,
    SystemLosses,
    antenna,
    frontend,
)

# CTRX8188F target datasheet rev. 0.20, Table 30: typical total RX SSB noise
# figure at RX gain step +3 dB (the "ultra low noise operation mode" rows) at
# 1 and 10 MHz IF. The walk used RX gain code 0, +3 dB (user manual Table 120),
# and its 15-51 m lie at 1.0-3.3 MHz IF, between the two rows.
NOISE_FIGURE_GAIN_PLUS3_DB = (9.9, 9.7)
# SENCITY FARAD-IV data sheet: radiation efficiency >= 90 % and reflection
# coefficient <= -10 dB, so realized gain is at most this far below directivity.
ANTENNA_LOSS_BOUND_DB = -10.0 * math.log10(0.9) - 10.0 * math.log10(1.0 - 0.1)
# These notes: per-chirp frequency error of the static return at 39 m after the
# walk (Infineon's firmware).
WALK_CHIRP_FREQUENCY_ERROR_HZ = 19.0e3
# Nearest and farthest target ranges of the analysed legs.
WALK_RANGES_M = (15.0, 51.0)


def walk_waveform() -> FmcwWaveform:
    """The walk's sampled ramp and CPI."""
    return FmcwWaveform(
        center_frequency_hz=76.374237e9,
        bandwidth_hz=100.781248e6,  # sampled sweep
        sample_rate_hz=512 / 10.24e-6,
        n_samples=512,
        n_chirps=1024,
        chirp_repetition_time_s=15.96e-6,
    )


def carkit_walk(
    noise_figure_db: float | None = None,
    antenna_loss_db: float = 0.0,
    computed_straddle: bool = False,
) -> Radar:
    """TX1 with eight noncoherently compared RX channels, as in the walk.

    The defaults give the reference model: the datasheet's headline noise
    figure, no system losses and no straddle loss. ``antenna_loss_db`` applies
    on transmit and receive; ``computed_straddle`` uses the toolbox's mean
    straddle loss for the fourfold padding instead of zero.
    """
    waveform = walk_waveform()
    if noise_figure_db is None:
        ctrx = frontend.ctrx8188f(n_tx=1)
    else:
        ctrx = frontend.ctrx8188f(n_tx=1, noise_figure_db=noise_figure_db)
    straddle_db = None if computed_straddle else 0.0
    return Radar(
        frontend=ctrx,
        antenna=antenna.sencity_farad_iv(),
        waveform=waveform,
        processing=StandardProcessing(
            rx_combination=BeamCombination.NONCOHERENT,
            range_window="blackman",
            doppler_window="blackman",
            range_fft_size=4 * waveform.n_samples,
            doppler_fft_size=4 * waveform.n_chirps,
            range_window_loss_db=WINDOW_LOSS_BLACKMAN_DB,
            doppler_window_loss_db=WINDOW_LOSS_BLACKMAN_DB,
            range_straddle_loss_db=straddle_db,
            doppler_straddle_loss_db=straddle_db,
            cfar_loss_db=0.0,
        ),
        losses=SystemLosses(
            tx_antenna_loss_db=antenna_loss_db, rx_antenna_loss_db=antenna_loss_db
        ),
    )


def model_snr_db(
    range_m: float = REFERENCE_RANGE_M, rcs_dbsm: float = REFERENCE_RCS_DBSM
) -> float:
    """Per-RX matched-filter SNR of a nonfluctuating target at boresight."""
    target = ConstantRcsTarget.from_dbsm(rcs_dbsm, swerling=0)
    return carkit_walk().link_budget(target, Geometry(range_m=range_m)).snr_db


def _snr_db(radar: Radar) -> float:
    target = ConstantRcsTarget.from_dbsm(REFERENCE_RCS_DBSM, swerling=0)
    return radar.link_budget(target, Geometry(range_m=REFERENCE_RANGE_M)).snr_db


def carkit_terms() -> dict[str, Any]:
    """Each CARKIT term's effect on the model, and the model with all of them.

    The measurement is scaled to 100 m by R^-4 alone, so it compares with a
    free-space model at 100 m; the range-dependent terms are given at the
    walk's own ranges and are too small to enter the bracket.
    """
    reference = _snr_db(carkit_walk())
    nf_worse, nf_better = NOISE_FIGURE_GAIN_PLUS3_DB
    straddle = carkit_walk(computed_straddle=True)
    waveform = straddle.waveform
    atmosphere = Atmosphere.itu_p676(waveform.center_frequency_hz)
    coherence = SystemLosses(chirp_frequency_error_rms_hz=WALK_CHIRP_FREQUENCY_ERROR_HZ)
    near, far = (Geometry(range_m=r) for r in WALK_RANGES_M)
    effects = {
        "noise_figure_at_rx_gain_plus3": [
            _snr_db(carkit_walk(noise_figure_db=nf)) - reference
            for nf in (nf_worse, nf_better)
        ],
        "straddle_fourfold_padding": _snr_db(straddle) - reference,
        "antenna_directivity_to_realized_gain": [
            0.0,
            _snr_db(carkit_walk(antenna_loss_db=ANTENNA_LOSS_BOUND_DB)) - reference,
        ],
        "atmosphere_at_walk_ranges": [
            -float(atmosphere.two_way_loss_db(g, waveform)) for g in (near, far)
        ],
        "chirp_coherence_at_walk_ranges": [
            -float(coherence.coherence_loss_db(g.range_m)) for g in (near, far)
        ],
    }
    low = _snr_db(carkit_walk(nf_worse, ANTENNA_LOSS_BOUND_DB, computed_straddle=True))
    high = _snr_db(carkit_walk(nf_better, computed_straddle=True))
    return {
        "reference_model_db": reference,
        "inputs": {
            "noise_figure_gain_plus3_db": list(NOISE_FIGURE_GAIN_PLUS3_DB),
            "antenna_loss_bound_db_per_pass": ANTENNA_LOSS_BOUND_DB,
            "atmosphere_db_per_km": atmosphere.specific_attenuation_db_per_km,
            "chirp_frequency_error_rms_hz": WALK_CHIRP_FREQUENCY_ERROR_HZ,
            "walk_ranges_m": list(WALK_RANGES_M),
        },
        "effects_db": effects,
        "model_with_terms_db": [low, high],
    }


def _span(values: float | list[float]) -> str:
    if isinstance(values, float):
        return f"{values:+.2f} dB"
    return f"{values[0]:+.2f} to {values[1]:+.2f} dB"


def main() -> None:
    radar = carkit_walk()
    target = ConstantRcsTarget.from_dbsm(REFERENCE_RCS_DBSM, swerling=0)
    print("CARKIT TX1 walk model, per RX channel, 10 dBsm nonfluctuating reflector")
    print(f"Active integration: {radar.waveform.dwell_time_s * 1e3:.5f} ms")
    print(f"CPI including dead time: {radar.waveform.cpi_duration_s * 1e3:.5f} ms")
    print()
    print(radar.link_budget(target, Geometry(range_m=REFERENCE_RANGE_M)))
    print()
    print(
        f"Model at {REFERENCE_RANGE_M:g} m: {model_snr_db():.2f} dB for 10 dBsm, "
        f"{model_snr_db(rcs_dbsm=WALKING_RCS_DBSM):.2f} dB for "
        f"{WALKING_RCS_DBSM:g} dBsm"
    )

    terms = carkit_terms()
    print()
    print("CARKIT terms, effect on the model (cover loss not known, left out):")
    for name, values in terms["effects_db"].items():
        print(f"  {name:38s} {_span(values)}")
    low, high = terms["model_with_terms_db"]
    print(f"Model with the terms: {low:.2f} to {high:.2f} dB")

    summary_path = GENERATED_DIR / "reference_snr" / "summary.json"
    if not summary_path.is_file():
        print("Run walk_reference_snr.py for the measured comparison.")
        write_summary(GENERATED_DIR / "model", terms)
        return
    comparison = json.loads(summary_path.read_text())["comparison"]
    print()
    print("Measured, scaled to 100 m and 10 dBsm (see walk_reference_snr.py):")
    measured: dict[str, Any] = {}
    for name, values in comparison.items():
        value = values["measured_db"]
        print(
            f"  {name:34s} {value:6.2f} dB  residual {values['residual_db']:+.2f} dB, "
            f"with the terms {value - high:+.2f} to {value - low:+.2f} dB"
        )
        measured[name] = {
            "measured_db": value,
            "residual_db": values["residual_db"],
            "residual_with_terms_db": [value - high, value - low],
        }
    print()
    write_summary(GENERATED_DIR / "model", terms | {"measured": measured})


if __name__ == "__main__":
    main()
