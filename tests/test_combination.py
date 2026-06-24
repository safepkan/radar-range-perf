"""Tests for mixed coherent/non-coherent combination, collapsing and in-phase TX."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.special import gammainc, gammaincc

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
from radarperf.detection import detection_threshold, probability_of_detection


def _waveform() -> FmcwWaveform:
    return FmcwWaveform(
        center_frequency_hz=77e9,
        bandwidth_hz=1.0e9,
        sample_rate_hz=20e6,
        n_samples=256,
        n_chirps=128,
        chirp_repetition_time_s=50e-6,
    )


def _sw1_correlated_closed_form(
    snr_db: float, pfa: float, n_signal: int, n_collapsing: int
) -> float:
    """Closed-form Swerling-1 Pd for a shared fluctuation and empty cells."""
    snr = 10.0 ** (snr_db / 10.0)
    n_total = n_signal + n_collapsing
    thr = detection_threshold(n_total, pfa)
    if n_total == 1:
        return float(np.exp(-thr / (1.0 + snr)))
    a = 1.0 + 1.0 / (n_signal * snr)
    k = n_total - 1
    return float(
        gammaincc(k, thr)
        + a**k * gammainc(k, thr / a) * np.exp(-thr / (1.0 + n_signal * snr))
    )


def test_sw1_collapsing_matches_closed_form() -> None:
    # Shared Swerling-1 amplitude diagonalises to one signal mode plus
    # n_total - 1 noise modes, so no Gauss-Laguerre quadrature is needed.
    pfa = 1e-4
    for snr_db in (6.0, 12.0):
        for n_signal, n_collapsing in ((4, 0), (4, 2), (16, 8)):
            got = probability_of_detection(
                snr_db,
                pfa,
                swerling=1,
                n_pulses=n_signal,
                n_collapsing=n_collapsing,
            )
            expected = _sw1_correlated_closed_form(snr_db, pfa, n_signal, n_collapsing)
            assert 0.0 <= got <= 1.0
            assert got == pytest.approx(expected, abs=1e-12)


def test_collapsing_against_monte_carlo() -> None:
    rng = np.random.default_rng(2024)
    pfa = 1e-3
    trials = 120_000
    n_signal, n_collapse = 16, 8  # 4 RX x (4 active + 2 empty) subbands
    n_total = n_signal + n_collapse
    from scipy.special import gammainccinv

    thr = float(gammainccinv(n_total, pfa))

    def mc(snr: float, case: int) -> float:
        if case == 0:
            g = np.ones((trials, 1))
        elif case == 1:
            g = rng.exponential(1.0, size=(trials, 1))
        else:  # case 3: chi-square(4) power normalised to mean 1 -> Gamma(2, 0.5)
            g = rng.gamma(2.0, 0.5, size=(trials, 1))
        power = snr * g * np.ones((trials, n_signal))  # shared draw across cells
        phase = rng.uniform(0.0, 2 * np.pi, size=(trials, n_signal))
        sig = np.sqrt(power) * np.exp(1j * phase)
        sig_noise = (
            rng.standard_normal((trials, n_signal))
            + 1j * rng.standard_normal((trials, n_signal))
        ) / np.sqrt(2.0)
        empty = (
            rng.standard_normal((trials, n_collapse))
            + 1j * rng.standard_normal((trials, n_collapse))
        ) / np.sqrt(2.0)
        stat = np.sum(np.abs(sig + sig_noise) ** 2, axis=1) + np.sum(
            np.abs(empty) ** 2, axis=1
        )
        return float(np.mean(stat > thr))

    for case in (0, 1, 3):
        for snr_db in (6.0, 11.0):
            snr = 10.0 ** (snr_db / 10.0)
            analytic = float(
                probability_of_detection(
                    snr_db,
                    pfa,
                    swerling=case,
                    n_pulses=n_signal,
                    n_collapsing=n_collapse,
                )
            )
            assert abs(analytic - mc(snr, case)) < 0.02, (case, snr_db)


def test_collapsing_costs_snr() -> None:
    # Adding empty cells should never increase Pd at fixed signal looks.
    pfa = 1e-6
    without = probability_of_detection(
        10.0, pfa, swerling=1, n_pulses=16, n_collapsing=0
    )
    with_empty = probability_of_detection(
        10.0, pfa, swerling=1, n_pulses=16, n_collapsing=8
    )
    assert with_empty <= without


def test_swerling2_4_collapsing_not_supported() -> None:
    for case in (2, 4):
        with pytest.raises(NotImplementedError):
            probability_of_detection(
                10.0, 1e-6, swerling=case, n_pulses=4, n_collapsing=2
            )


def _budget(processing: StandardProcessing):  # type: ignore[no-untyped-def]
    return processing.budget(_waveform(), n_tx=4, n_rx=4)


def test_ddma_production_path_bookkeeping() -> None:
    # RX non-coherent + subband non-coherent, 6 subbands (4 active + 2 empty).
    proc = StandardProcessing(
        mimo=MimoScheme.DDM,
        rx_combination=BeamCombination.NONCOHERENT,
        tx_combination=BeamCombination.NONCOHERENT,
        n_doppler_subbands=6,
    )
    b = _budget(proc)
    assert b.n_noncoherent == 16  # 4 RX x 4 active TX
    assert b.n_collapsing == 8  # 4 RX x 2 empty subbands
    assert "beamforming" not in b.losses_db  # no coherent angle combination


def test_ddma_rx_coherent_subband_noncoherent_bookkeeping() -> None:
    proc = StandardProcessing(
        mimo=MimoScheme.DDM,
        rx_combination=BeamCombination.COHERENT,
        tx_combination=BeamCombination.NONCOHERENT,
        n_doppler_subbands=6,
        beamforming_loss_db=1.0,
    )
    b = _budget(proc)
    assert b.n_noncoherent == 4  # 4 active subbands
    assert b.n_collapsing == 2  # 2 empty subbands
    assert b.losses_db["beamforming"] == 1.0


def test_full_coherent_vs_production_coherent_gain() -> None:
    wf = _waveform()
    production = StandardProcessing(
        mimo=MimoScheme.DDM,
        rx_combination=BeamCombination.NONCOHERENT,
        tx_combination=BeamCombination.NONCOHERENT,
        n_doppler_subbands=6,
    ).budget(wf, 4, 4)
    full = StandardProcessing(
        mimo=MimoScheme.DDM,
        rx_combination=BeamCombination.COHERENT,
        tx_combination=BeamCombination.COHERENT,
    ).budget(wf, 4, 4)
    assert full.n_noncoherent == 1 and full.n_collapsing == 0
    # Full coherent folds the 16 virtual channels into the coherent gain.
    assert full.coherent_gain_db - production.coherent_gain_db == pytest.approx(
        10.0 * np.log10(16.0), abs=1e-9
    )


def test_inphase_tx_beats_ddm_by_ntx() -> None:
    wf = _waveform()
    ddm_full = StandardProcessing(
        mimo=MimoScheme.DDM,
        rx_combination=BeamCombination.COHERENT,
        tx_combination=BeamCombination.COHERENT,
    ).budget(wf, 4, 4)
    inphase = StandardProcessing(
        transmit_coherent=True,
        rx_combination=BeamCombination.COHERENT,
    ).budget(wf, 4, 4)
    # In-phase TX adds a further 10 log10(n_tx) over DDM virtual combining.
    assert inphase.coherent_gain_db - ddm_full.coherent_gain_db == pytest.approx(
        10.0 * np.log10(4.0), abs=1e-9
    )


def test_coherent_combination_detects_better_than_noncoherent() -> None:
    wf = _waveform()
    element = GaussianBeamAntenna(11.0, 80.0, 20.0)
    chip = frontend.awr2e44p()

    def radar(proc: StandardProcessing) -> Radar:
        return Radar(
            frontend=chip,
            waveform=wf,
            processing=proc,
            antenna=AntennaPair.from_element(element),
        )

    production = radar(
        StandardProcessing(
            mimo=MimoScheme.DDM,
            rx_combination=BeamCombination.NONCOHERENT,
            tx_combination=BeamCombination.NONCOHERENT,
            n_doppler_subbands=6,
        )
    )
    full_coherent = radar(
        StandardProcessing(
            mimo=MimoScheme.DDM,
            rx_combination=BeamCombination.COHERENT,
            tx_combination=BeamCombination.COHERENT,
        )
    )
    tgt = target.pedestrian()
    geom = Geometry(range_m=90.0)
    pd_nc = production.probability_of_detection(tgt, geom)
    pd_co = full_coherent.probability_of_detection(tgt, geom)
    assert pd_co >= pd_nc
