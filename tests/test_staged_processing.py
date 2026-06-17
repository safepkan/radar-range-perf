"""Generic staged (named multi-axis) combining model.

`StagedProcessing` must reproduce `StandardProcessing` on the shared DDMA
detection path and generalise cleanly to arbitrary coherent/non-coherent axes.
"""

from __future__ import annotations

import numpy as np
import pytest

from radarperf import (
    AntennaPair,
    BeamCombination,
    CombiningStage,
    FmcwWaveform,
    GaussianBeamAntenna,
    Geometry,
    MimoScheme,
    Radar,
    StagedProcessing,
    StandardProcessing,
    frontend,
    target,
)

WF = FmcwWaveform(
    center_frequency_hz=77e9,
    bandwidth_hz=1e9,
    sample_rate_hz=20e6,
    n_samples=256,
    n_chirps=128,
    chirp_repetition_time_s=50e-6,
)
ANT = GaussianBeamAntenna(11.0, 80.0, 20.0)


def _ddma_staged() -> StagedProcessing:
    return StagedProcessing(
        combining_stages=(
            CombiningStage("rx", 4, BeamCombination.NONCOHERENT),
            CombiningStage("subband", 6, BeamCombination.NONCOHERENT, signal_count=4),
        )
    )


def test_staged_reproduces_standard_ddma_budget() -> None:
    standard = StandardProcessing(
        mimo=MimoScheme.DDM,
        rx_combination=BeamCombination.NONCOHERENT,
        tx_combination=BeamCombination.NONCOHERENT,
        n_doppler_subbands=6,
    ).budget(WF, n_tx=4, n_rx=4)
    staged = _ddma_staged().budget(WF, n_tx=4, n_rx=4)

    assert np.isclose(staged.coherent_gain_db, standard.coherent_gain_db, atol=1e-9)
    assert staged.n_noncoherent == standard.n_noncoherent == 16
    assert staged.n_collapsing == standard.n_collapsing == 8
    assert np.isclose(staged.total_loss_db, standard.total_loss_db, atol=1e-9)


def test_staged_matches_standard_pd_through_engine() -> None:
    def radar(processing: object) -> Radar:
        return Radar(
            frontend=frontend.awr2e44p(),
            waveform=WF,
            processing=processing,  # type: ignore[arg-type]
            antenna=AntennaPair.from_element(ANT),
        )

    standard = radar(
        StandardProcessing(
            mimo=MimoScheme.DDM,
            rx_combination=BeamCombination.NONCOHERENT,
            tx_combination=BeamCombination.NONCOHERENT,
            n_doppler_subbands=6,
        )
    )
    staged = radar(_ddma_staged())
    geom = Geometry(range_m=90.0)
    tgt = target.pedestrian()
    assert np.isclose(
        standard.probability_of_detection(tgt, geom),
        staged.probability_of_detection(tgt, geom),
        atol=1e-12,
    )


def test_coherent_stage_multiplies_gain_without_looks() -> None:
    base = StagedProcessing().budget(WF, 1, 1)
    with_beamform = StagedProcessing(
        combining_stages=(CombiningStage("array", 4, BeamCombination.COHERENT),)
    ).budget(WF, 1, 1)
    assert np.isclose(
        with_beamform.coherent_gain_db - base.coherent_gain_db,
        10.0 * np.log10(4.0),
        atol=1e-9,
    )
    assert with_beamform.n_noncoherent == 1
    assert with_beamform.n_collapsing == 0


def test_noncoherent_stages_multiply_looks_and_collapsing() -> None:
    budget = StagedProcessing(
        combining_stages=(
            CombiningStage("a", 4, BeamCombination.NONCOHERENT),
            CombiningStage("b", 6, BeamCombination.NONCOHERENT, signal_count=4),
        )
    ).budget(WF, 1, 1)
    assert budget.n_noncoherent == 16
    assert budget.n_collapsing == 8


def test_empty_model_is_single_coherent_look() -> None:
    budget = StagedProcessing().budget(WF, 1, 1)
    assert budget.n_noncoherent == 1
    assert budget.n_collapsing == 0
    assert np.isclose(budget.coherent_gain_db, 10.0 * np.log10(256 * 128), atol=1e-9)


def test_coherent_stage_rejects_noise_only_cells() -> None:
    with pytest.raises(ValueError, match="coherent"):
        CombiningStage("x", 4, BeamCombination.COHERENT, signal_count=2)


def test_combining_stage_validation() -> None:
    with pytest.raises(ValueError):
        CombiningStage("x", 0, BeamCombination.NONCOHERENT)
    with pytest.raises(ValueError):
        CombiningStage("x", 4, BeamCombination.NONCOHERENT, signal_count=5)
