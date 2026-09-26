"""Compare a provisional CARKIT model with the updated TX1 walk fit.

Run from the repo root with the project venv. See NOTES.md for provenance and
unresolved assumptions. The printed report values evaluate a selected fixed-
slope fit, not raw observations. No extrapolated TX/RX gain is applied.
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

# Updated PDF pp. 13–14: fixed R^-4 reflector fit, before any RCS normalization
# or array-gain credits. Its 36.57 dB value at 100 m is a normalization of a fit
# to 33 selected observations in the 15–51 m interval, not a measurement at
# 100 m. Figure 10 says the observations were selected within 6 dB of a local
# R^-4-corrected peak.
REPORT_REFERENCE_RANGE_M = 100.0
REPORT_REFERENCE_SNR_DB = 36.57
REPORT_REFLECTOR_INTERCEPT_DB = REPORT_REFERENCE_SNR_DB + 40.0 * math.log10(
    REPORT_REFERENCE_RANGE_M
)
COMPARISON_RANGES_M = (15.0, 30.0, 51.0, REPORT_REFERENCE_RANGE_M)
REFLECTOR = ConstantRcsTarget.from_dbsm(
    10.0, swerling=0, name="Walking reflector: assumed 10 dBsm"
)


def carkit_walk() -> Radar:
    """Build TX1 / eight noncoherent RX using the report and explicit defaults.

    Boresight, preset TX power/NF and the toolbox complex-sample noise convention
    are provisional assumptions. The report does not state the field-processing
    windows or zero-padding factor. We provisionally use Blackman losses and
    assume enough zero-padding to neglect residual bin-straddling losses.
    """
    waveform = FmcwWaveform(
        center_frequency_hz=76.374237e9,
        bandwidth_hz=100.781248e6,
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
    print("Target: nominal 10 dBsm reflector; assumed Swerling 0 and boresight")
    print("TX power/NF and sample-noise bandwidth: unvalidated preset defaults")
    print("Assumed Blackman FFT windows and sufficient zero-padding")
    print("No residual straddling loss, CFAR loss or empirical correction applied")
    print(f"Active integration: {wf.dwell_time_s * 1e3:.5f} ms")
    print(f"CPI including dead time: {wf.cpi_duration_s * 1e3:.5f} ms")
    print()
    print("Model budget at 30 m:")
    print(radar.link_budget(REFLECTOR, Geometry(range_m=30.0)))
    print()
    print("Report column: selected fixed-slope fit, not individual measurements")
    print("Range [m]  Model SNR [dB]  Report fit [dB]  Report - model [dB]")
    empirical_offset_db = math.nan
    for range_m in COMPARISON_RANGES_M:
        budget = radar.link_budget(REFLECTOR, Geometry(range_m=range_m))
        report_snr_db = REPORT_REFLECTOR_INTERCEPT_DB - 40.0 * math.log10(range_m)
        empirical_offset_db = report_snr_db - budget.snr_db
        print(
            f"{range_m:9.1f}  {budget.snr_db:14.2f}  {report_snr_db:15.2f}"
            f"  {empirical_offset_db:19.2f}"
        )
    print()
    print(f"Provisional empirical SNR offset: {empirical_offset_db:+.2f} dB")
    print("(add to model SNR; it is not an attributable hardware-loss estimate)")
    print("Model SNR is per look; eight noncoherent looks affect Pd separately.")
    print("A normalized RX-power mean has the same S/N under equal-channel SNR.")
    print("Residual includes RCS, geometry, selection and processing uncertainty.")


if __name__ == "__main__":
    main()
