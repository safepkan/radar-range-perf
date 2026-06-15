"""Basic usage: build a radar, evaluate one link budget, get a single-scan Pd.

Run with::

    python examples/basic_link_budget.py
"""

from __future__ import annotations

from radarperf import (
    FmcwWaveform,
    GaussianBeamAntenna,
    Geometry,
    MimoScheme,
    Radar,
    StandardProcessing,
    frontend,
    target,
)


def main() -> None:
    # A 77 GHz, 1 GHz-bandwidth fast-chirp waveform: 256 samples x 128 chirps.
    waveform = FmcwWaveform(
        center_frequency_hz=77e9,
        bandwidth_hz=1.0e9,
        sample_rate_hz=20.0e6,
        n_samples=256,
        n_chirps=128,
        chirp_repetition_time_s=50e-6,
    )
    print("Range resolution:    %.2f m" % waveform.range_resolution_m)
    print("Max unambig. range:  %.1f m" % waveform.max_unambiguous_range_m)
    print("Velocity resolution: %.2f m/s" % waveform.velocity_resolution_mps)
    print("Max unambig. vel.:   +/- %.1f m/s" % waveform.max_unambiguous_velocity_mps)
    print()

    # A 3TX/4RX MMIC (datasheet preset) in time-division MIMO, with a
    # wide-azimuth / narrow-elevation element pattern.
    element = GaussianBeamAntenna(
        boresight_gain_dbi=11.0,
        beamwidth_az_deg=80.0,
        beamwidth_el_deg=20.0,
    )
    radar = Radar(
        frontend=frontend.awr2243(),
        waveform=waveform,
        processing=StandardProcessing(mimo=MimoScheme.TDM),
        tx_antenna=element,
        rx_antenna=element,
        default_pfa=1e-6,
    )

    car = target.car()  # ~10 dBsm, Swerling 1 (illustrative)
    geometry = Geometry(range_m=120.0, azimuth_deg=0.0)

    budget = radar.link_budget(car, geometry)
    print(budget)
    print()

    pd = radar.probability_of_detection(car, geometry)
    print("Single-scan Pd at 120 m (Pfa 1e-6): %.3f" % pd)


if __name__ == "__main__":
    main()
