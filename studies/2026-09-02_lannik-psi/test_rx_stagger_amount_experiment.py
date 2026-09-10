"""Study-local checks for the stagger-amount and TX-taper experiment."""

from __future__ import annotations

from math import comb, factorial

import numpy as np
import pytest

from lannik_psi import load_tx_antenna
from quadrant_mimo import split_tx_quadrants
from rx_resolution_experiment import CASES, HypothesisBank, build_bank
from rx_stagger_amount_experiment import (
    HORIZONTAL_ALIAS,
    HORIZONTAL_EDGE,
    LAYOUT_OPTIONS,
    VERTICAL_ALIAS,
    VERTICAL_EDGE,
    in_beam_competitor_maps,
    mismatch_margin_db,
    pair_correlation_db,
    rx_pair_correlation,
    scaled_defocus_antenna,
    simulate_multi_frame_event,
    staggered_layout,
    uniform_quadrants,
    unwrapped_excitation_phase,
)


def test_stagger_information_follows_the_column_group_phase() -> None:
    # Alternating columns differ by 2*pi*s/H at the old vertical alias, so the
    # two four-channel groups give rho = cos^2(pi s/H); horizontal stays exact.
    for fraction in (0.0, 0.125, 0.25, 0.5):
        layout = staggered_layout(fraction)
        vertical = rx_pair_correlation(layout, VERTICAL_EDGE, VERTICAL_ALIAS)
        assert vertical == pytest.approx(np.cos(np.pi * fraction) ** 2, abs=1e-9)
        horizontal = rx_pair_correlation(layout, HORIZONTAL_EDGE, HORIZONTAL_ALIAS)
        assert horizontal == pytest.approx(1.0, abs=1e-9)
    with pytest.raises(ValueError, match="fraction"):
        staggered_layout(1.5)


def test_mimo_vertical_discrimination_is_a_taper_effect() -> None:
    tx = load_tx_antenna()
    nominal = split_tx_quadrants(tx)
    # Quadrant phase centers are eight pitches apart, like the RX subarrays, so
    # untapered quadrants alias exactly at the vertical edges.
    assert pair_correlation_db(
        uniform_quadrants(nominal), VERTICAL_EDGE, VERTICAL_ALIAS
    ) == pytest.approx(0.0, abs=1e-6)
    assert pair_correlation_db(nominal, VERTICAL_EDGE, VERTICAL_ALIAS) < -25.0
    focused = split_tx_quadrants(scaled_defocus_antenna(tx, 0.0))
    assert pair_correlation_db(focused, HORIZONTAL_EDGE, HORIZONTAL_ALIAS) > -0.2
    assert mismatch_margin_db(
        nominal, nominal, VERTICAL_EDGE, VERTICAL_ALIAS
    ) == pytest.approx(-pair_correlation_db(nominal, VERTICAL_EDGE, VERTICAL_ALIAS))


def test_coherent_frames_accumulate_only_with_distinct_signatures() -> None:
    rx = np.ones(8, dtype=np.complex128) / np.sqrt(8)
    quadrants = np.ones(4, dtype=np.complex128)
    other_rx = rx * np.array([1, -1, 1, -1, 1, -1, 1, -1])
    mimo = np.kron(quadrants / 2, rx)

    def bank(second: np.ndarray) -> HypothesisBank:  # type: ignore[type-arg]
        return HypothesisBank(
            uv=np.zeros((2, 2)),
            required_rcs_dbsm=np.zeros(2),
            cell_ids=((0, 0), (0, 1)),
            cell_starts=np.array([0, 1], dtype=np.int64),
            true_cell=0,
            coherent=np.column_stack((rx, second)),
            mimo=np.column_stack((mimo, mimo)),
        )

    energies = np.array([0.0])
    identical = simulate_multi_frame_event(
        bank(rx),
        rx,
        quadrants,
        coherent_snr_db=6.0,
        mimo_to_coherent_snr=1.0,
        energies=energies,
        update_counts=(1, 4),
        trials=6000,
    )
    assert identical[:, 0] / 6000 == pytest.approx([0.5, 0.5], abs=0.025)
    trials = 20000
    distinct = simulate_multi_frame_event(
        bank(other_rx),
        rx,
        quadrants,
        coherent_snr_db=3.0,
        mimo_to_coherent_snr=1.0,
        energies=energies,
        update_counts=(1, 2, 4),
        trials=trials,
    )
    # Orthogonal fixed signatures with K square-law-summed frames follow the
    # classical L-fold diversity noncoherent binary error probability; the
    # extra noise degrees of freedom make it worse than exp(-K*SNR/2)/2.
    snr = 10**0.3
    expected = [square_law_binary_error(K, K * snr) for K in (1, 2, 4)]
    assert distinct[:, 0] / trials == pytest.approx(expected, abs=0.01)


def square_law_binary_error(diversity: int, total_snr: float) -> float:
    coefficients = [
        sum(comb(2 * diversity - 1, k) for k in range(diversity - n)) / factorial(n)
        for n in range(diversity)
    ]
    return float(
        np.exp(-total_snr / 2)
        / 2 ** (2 * diversity - 1)
        * sum(c * (total_snr / 2) ** n for n, c in enumerate(coefficients))
    )


def test_supplied_phase_unwraps_to_a_smooth_quadratic_defocus() -> None:
    tx = load_tx_antenna()
    phase = unwrapped_excitation_phase(np.asarray(tx.excitations))
    # Smooth: no residual 2*pi jumps between neighbours along either axis.
    assert np.max(np.abs(np.diff(phase, axis=0))) < 1.0
    assert np.max(np.abs(np.diff(phase, axis=1))) < 1.0
    # Quadratic defocus: about -180 deg at the edge centres, -360 at corners.
    assert phase[0, 8] == pytest.approx(-np.pi, abs=0.15)
    assert phase[0, 0] == pytest.approx(-2 * np.pi, abs=0.15)
    # Unit scale reproduces the nominal quadrant discrimination.
    nominal = pair_correlation_db(split_tx_quadrants(tx), VERTICAL_EDGE, VERTICAL_ALIAS)
    rebuilt = pair_correlation_db(
        split_tx_quadrants(scaled_defocus_antenna(tx, 1.0)),
        VERTICAL_EDGE,
        VERTICAL_ALIAS,
    )
    assert rebuilt == pytest.approx(nominal, abs=0.05)


def test_worst_mimo_competitor_is_searched_independently() -> None:
    tx = load_tx_antenna()
    maps = in_beam_competitor_maps(
        tx, split_tx_quadrants(tx), LAYOUT_OPTIONS[:1], samples=3, grid_samples=161
    )
    assert np.all(maps.mimo_worst >= maps.mimo_at_coherent_competitor - 1e-12)
    # TX correlation never exceeds one, so the MIMO competitor cannot beat the
    # strongest coherent competitor; a strict gap shows the search differs.
    assert np.all(maps.mimo_worst <= maps.coherent_rho + 1e-12)
    assert np.any(maps.mimo_worst > maps.mimo_at_coherent_competitor + 1e-6)


def test_half_period_seeds_add_the_diagonal_competitor_family() -> None:
    tx = load_tx_antenna()
    quadrants = split_tx_quadrants(tx)
    layout = staggered_layout(0.25)
    default = build_bank(CASES[2], layout, tx, quadrants)
    dense = build_bank(CASES[2], layout, tx, quadrants, u_seed_fraction=0.5)
    assert len(dense.cell_ids) > len(default.cell_ids)
    assert any(ku % 2 == 1 for ku, _ in dense.cell_ids)
    assert dense.cell_ids[dense.true_cell] == (0, 0)
    with pytest.raises(ValueError, match="u_seed_fraction"):
        build_bank(CASES[2], layout, tx, quadrants, u_seed_fraction=0.3)
