"""Comparing channel-combination strategies for a DDMA AWR2E44P (4 TX / 4 RX).

Reproduces the three paths discussed for the TI DDMA SDK plus the in-phase
transmit alternative, at a fixed geometry, so the SNR / detection trade-offs are
visible side by side.

Run with::

    python examples/ddma_combinations.py
"""

from __future__ import annotations

from radarperf import (
    AntennaPair,
    BeamCombination,
    FmcwWaveform,
    GaussianBeamAntenna,
    Geometry,
    MimoScheme,
    Radar,
    StandardProcessing,
    frontend,
    target,
)

N_SUBBANDS = 6  # 4 active (one per TX) + 2 empty guard bands

# A small, configurable angular straddle / beamforming loss for the coherent
# paths (set to 0 if you refine the beam onto the DOA, larger for a coarse grid).
BEAMFORMING_LOSS_DB = 1.0


def radar(processing: StandardProcessing) -> Radar:
    waveform = FmcwWaveform(
        center_frequency_hz=77e9,
        bandwidth_hz=1.0e9,
        sample_rate_hz=20e6,
        n_samples=256,
        n_chirps=128,
        chirp_repetition_time_s=50e-6,
    )
    element = GaussianBeamAntenna(11.0, 80.0, 20.0)
    return Radar(
        frontend=frontend.awr2e44p(),  # 4 TX / 4 RX (datasheet)
        waveform=waveform,
        processing=processing,
        antenna=AntennaPair.from_element(element),
        default_pfa=1e-6,
    )


CONFIGS = {
    "non-coh RX+subband (DDMA detect)": StandardProcessing(
        mimo=MimoScheme.DDM,
        rx_combination=BeamCombination.NONCOHERENT,
        tx_combination=BeamCombination.NONCOHERENT,
        n_doppler_subbands=N_SUBBANDS,
    ),
    "coherent RX, non-coh subband": StandardProcessing(
        mimo=MimoScheme.DDM,
        rx_combination=BeamCombination.COHERENT,
        tx_combination=BeamCombination.NONCOHERENT,
        n_doppler_subbands=N_SUBBANDS,
        beamforming_loss_db=BEAMFORMING_LOSS_DB,
    ),
    "coherent RX + TX (virtual array)": StandardProcessing(
        mimo=MimoScheme.DDM,
        rx_combination=BeamCombination.COHERENT,
        tx_combination=BeamCombination.COHERENT,
        beamforming_loss_db=BEAMFORMING_LOSS_DB,
    ),
    "in-phase TX + coherent RX": StandardProcessing(
        transmit_coherent=True,
        rx_combination=BeamCombination.COHERENT,
        beamforming_loss_db=BEAMFORMING_LOSS_DB,
    ),
}


def main() -> None:
    pedestrian = target.pedestrian()  # ~-3 dBsm, Swerling 1 (illustrative)
    geometry = Geometry(range_m=90.0)

    header = (
        f"{'configuration':36}  {'coh.gain':>8}  {'looks':>6}  "
        f"{'empty':>6}  {'per-look SNR':>12}  {'Pd':>6}"
    )
    print(f"AWR2E44P DDMA, pedestrian at {geometry.range_m:.0f} m, Pfa 1e-6\n")
    print(header)
    print("-" * len(header))
    for name, processing in CONFIGS.items():
        r = radar(processing)
        budget = r.link_budget(pedestrian, geometry)
        pd = r.probability_of_detection(pedestrian, geometry)
        print(
            f"{name:36}  {budget.coherent_gain_db:8.1f}  "
            f"{budget.n_noncoherent:6d}  {budget.n_collapsing:6d}  "
            f"{budget.snr_db:12.1f}  {pd:6.3f}"
        )


if __name__ == "__main__":
    main()
