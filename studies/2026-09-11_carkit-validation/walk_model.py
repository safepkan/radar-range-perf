"""Radar-equation model of the CARKIT TX1 walk and its measured comparison.

TX1 only, eight RX compared per channel (no coherent RX combination), CTRX8188F
datasheet TX power and noise figure, FARAD-IV boresight gains, the walk waveform
and Blackman windows with fourfold padding (no residual straddle, no CFAR loss).
The reflector is modeled as a nonfluctuating 10 dBsm target at boresight.

Prints the link budget and, if walk_reference_snr.py has been run, the measured
reference scaled to 100 m and 10 dBsm.
"""

from __future__ import annotations

import json

from walk_common import (
    GENERATED_DIR,
    REFERENCE_RANGE_M,
    REFERENCE_RCS_DBSM,
    WALKING_RCS_DBSM,
)
from radarperf import (
    WINDOW_LOSS_BLACKMAN_DB,
    BeamCombination,
    ConstantRcsTarget,
    FmcwWaveform,
    Geometry,
    Radar,
    StandardProcessing,
    antenna,
    frontend,
)


def carkit_walk() -> Radar:
    """TX1 with eight noncoherently compared RX channels, as in the walk."""
    waveform = FmcwWaveform(
        center_frequency_hz=76.374237e9,
        bandwidth_hz=100.781248e6,  # sampled sweep
        sample_rate_hz=512 / 10.24e-6,
        n_samples=512,
        n_chirps=1024,
        chirp_repetition_time_s=15.96e-6,
    )
    return Radar(
        frontend=frontend.ctrx8188f(n_tx=1),
        antenna=antenna.sencity_farad_iv(),
        waveform=waveform,
        processing=StandardProcessing(
            rx_combination=BeamCombination.NONCOHERENT,
            range_window_loss_db=WINDOW_LOSS_BLACKMAN_DB,
            doppler_window_loss_db=WINDOW_LOSS_BLACKMAN_DB,
            range_straddle_loss_db=0.0,
            doppler_straddle_loss_db=0.0,
            cfar_loss_db=0.0,
        ),
    )


def model_snr_db(
    range_m: float = REFERENCE_RANGE_M, rcs_dbsm: float = REFERENCE_RCS_DBSM
) -> float:
    """Per-RX matched-filter SNR of a nonfluctuating target at boresight."""
    target = ConstantRcsTarget.from_dbsm(rcs_dbsm, swerling=0)
    return carkit_walk().link_budget(target, Geometry(range_m=range_m)).snr_db


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

    summary_path = GENERATED_DIR / "reference_snr" / "summary.json"
    if not summary_path.is_file():
        print("Run walk_reference_snr.py for the measured comparison.")
        return
    comparison = json.loads(summary_path.read_text())["comparison"]
    print()
    print("Measured, scaled to 100 m and 10 dBsm (see walk_reference_snr.py):")
    for name, values in comparison.items():
        print(
            f"  {name:34s} {values['measured_db']:6.2f} dB  "
            f"residual {values['residual_db']:+.2f} dB"
        )


if __name__ == "__main__":
    main()
