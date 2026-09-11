"""Compare a provisional CARKIT model with the reported TX1 walk fit.

Run from the repo root with the project venv. See NOTES.md for provenance and
unresolved assumptions. The three printed report values evaluate an upper-
envelope fit, not raw observations. No extrapolated TX/RX gain is applied.
"""

from __future__ import annotations

import math

from radarperf import (
    BeamCombination,
    ConstantRcsTarget,
    FmcwWaveform,
    Geometry,
    Radar,
    StandardProcessing,
    WINDOW_LOSS_BLACKMAN_DB,
    antenna,
    frontend,
)

# PDF p. 3: reflector-curve intercept, before any RCS normalization or array
# gain credits. Evaluate only inside the reported fit interval, 15–51 m.
REPORT_REFLECTOR_INTERCEPT_DB = 115.746526
COMPARISON_RANGES_M = (15.0, 30.0, 51.0)
REFLECTOR = ConstantRcsTarget.from_dbsm(
    10.0, swerling=0, name="Walking reflector: assumed 10 dBsm"
)


def carkit_walk() -> Radar:
    """Build TX1 / eight noncoherent RX using the report and explicit defaults.

    Boresight, 77 GHz, preset TX power/NF and complex-sample noise bandwidth
    are provisional assumptions. Blackman losses represent centered FFT bins;
    measured bin offsets and the RX noise convention still need matching.
    """
    waveform = FmcwWaveform(
        center_frequency_hz=77.0e9,  # assumed; exact capture frequency needed
        bandwidth_hz=100.781e6,
        sample_rate_hz=512 / 10.24e-6,  # inferred from sampled payload
        n_samples=512,
        n_chirps=1024,
        chirp_repetition_time_s=15.96e-6,
    )
    return Radar(
        frontend=frontend.ctrx8188f(n_tx=1),  # preset power/NF; eight RX
        antenna=antenna.sencity_farad_iv(),
        waveform=waveform,
        processing=StandardProcessing(
            rx_combination=BeamCombination.NONCOHERENT,
            range_window_loss_db=WINDOW_LOSS_BLACKMAN_DB,
            doppler_window_loss_db=WINDOW_LOSS_BLACKMAN_DB,
            range_straddle_loss_db=0.0,
            doppler_straddle_loss_db=0.0,
            cfar_loss_db=0.0,  # raw spectral SNR comparison
        ),
    )


def main() -> None:
    radar = carkit_walk()
    wf = radar.waveform
    print("CARKIT TX1 / eight noncoherent RX: provisional walk comparison")
    print("Target: assumed 10 dBsm reflector; assumed boresight and 77 GHz")
    print("TX power/NF and sample-noise bandwidth: unvalidated preset defaults")
    print("Blackman FFT windows; centered bins; no CFAR or fitted loss")
    print(f"Active integration: {wf.dwell_time_s * 1e3:.5f} ms")
    print(f"CPI including dead time: {wf.cpi_duration_s * 1e3:.5f} ms")
    print()
    print("Model budget at 30 m:")
    print(radar.link_budget(REFLECTOR, Geometry(range_m=30.0)))
    print()
    print("Report column: fitted upper envelope, not individual measurements")
    print("Range [m]  Model SNR [dB]  Report fit [dB]  Report - model [dB]")
    for range_m in COMPARISON_RANGES_M:
        budget = radar.link_budget(REFLECTOR, Geometry(range_m=range_m))
        report_snr_db = REPORT_REFLECTOR_INTERCEPT_DB - 40.0 * math.log10(range_m)
        print(
            f"{range_m:9.1f}  {budget.snr_db:14.2f}  {report_snr_db:15.2f}"
            f"  {report_snr_db - budget.snr_db:19.2f}"
        )
    print()
    print("Model SNR is per look; eight noncoherent looks affect Pd separately.")
    print("Residual includes unverified RCS, geometry and processing assumptions.")
    print("This comparison does not calibrate hardware loss or predict 1 km Pd.")


if __name__ == "__main__":
    main()
