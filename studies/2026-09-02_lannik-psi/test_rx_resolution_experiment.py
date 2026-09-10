"""Study-local checks for the on-demand resolution experiment."""

from __future__ import annotations

import numpy as np
import pytest

from lannik_psi import (
    RX_EXPERIMENTAL_STAGGERED_LAYOUT,
    RX_SUPPLIED_LAYOUT,
    load_tx_antenna,
)
from quadrant_mimo import split_tx_quadrants
from rx_resolution_experiment import (
    CASES,
    HypothesisBank,
    build_bank,
    choose_cells,
    error_upper_bound,
    normalize_columns,
    simulate_event,
)


def test_bank_uses_unit_vectors_and_retains_the_true_direction() -> None:
    tx = load_tx_antenna()
    quadrants = split_tx_quadrants(tx)
    for layout in (RX_SUPPLIED_LAYOUT, RX_EXPERIMENTAL_STAGGERED_LAYOUT):
        bank = build_bank(CASES[0], layout, tx, quadrants)
        assert np.linalg.norm(bank.coherent, axis=0) == pytest.approx(1.0)
        assert np.linalg.norm(bank.mimo, axis=0) == pytest.approx(1.0)
        true = np.all(np.isclose(bank.uv, [CASES[0].u, CASES[0].v]), axis=1)
        assert np.count_nonzero(true) == 1
        assert bank.required_rcs_dbsm[true] == pytest.approx(0.0)
        assert np.all(bank.required_rcs_dbsm <= 10.0 + 1e-10)
        assert bank.cell_ids[bank.true_cell] == (0, 0)
        assert bank.cell_ids == ((0, -1), (0, 0))


def test_rcs_screen_is_nested_and_local_grid_requires_zero_offset() -> None:
    tx = load_tx_antenna()
    quadrants = split_tx_quadrants(tx)
    low = build_bank(CASES[1], RX_SUPPLIED_LAYOUT, tx, quadrants, rcs_ceiling_dbsm=6)
    high = build_bank(CASES[1], RX_SUPPLIED_LAYOUT, tx, quadrants, rcs_ceiling_dbsm=10)
    assert set(map(tuple, low.uv)).issubset(set(map(tuple, high.uv)))
    with pytest.raises(ValueError, match="odd"):
        build_bank(CASES[0], RX_SUPPLIED_LAYOUT, tx, quadrants, local_samples=8)


def test_exact_alias_ties_do_not_depend_on_cell_order() -> None:
    starts = np.array([0, 2], dtype=np.int64)
    scores = np.tile([1.0, 2.0, 2.0 + 1e-13, 0.0], (20000, 1))
    selected = choose_cells(scores, starts, np.random.default_rng(912))
    assert np.mean(selected == 0) == pytest.approx(0.5, abs=0.015)
    scores[:, 0] = 3.0
    assert np.all(choose_cells(scores, starts, np.random.default_rng(912)) == 0)


def test_mimo_resolves_a_pair_that_coherent_measurement_cannot() -> None:
    rx = np.ones(8, dtype=np.complex128) / np.sqrt(8)
    quadrants = np.ones(4, dtype=np.complex128)
    mimo_true = np.kron(quadrants / 2, rx)
    mimo_false = np.kron(np.array([1, -1, 1, -1]) / 2, rx)
    bank = HypothesisBank(
        uv=np.zeros((2, 2)),
        required_rcs_dbsm=np.zeros(2),
        cell_ids=((0, 0), (0, 1)),
        cell_starts=np.array([0, 1], dtype=np.int64),
        true_cell=0,
        coherent=np.column_stack((rx, rx)),
        mimo=np.column_stack((mimo_true, mimo_false)),
    )
    errors = simulate_event(
        bank,
        rx,
        quadrants,
        coherent_snr_db=20,
        mimo_to_coherent_snr=1,
        energies=np.array([0.0, 0.04, 1.0]),
        trials=12000,
    )
    assert errors[0] / 12000 == pytest.approx(0.5, abs=0.02)
    # Orthogonal signatures and fixed amplitude give Pe = exp(-SNR/2)/2.
    assert errors[1] / 12000 == pytest.approx(0.5 * np.exp(-4.0 / 2), abs=0.008)
    assert errors[2] == 0


def test_zero_signal_is_chance_not_mimo_noise_bias() -> None:
    rx = np.ones(8, dtype=np.complex128) / np.sqrt(8)
    quadrants = np.ones(4, dtype=np.complex128)
    other_rx = rx * np.array([1, -1, 1, -1, 1, -1, 1, -1])
    bank = HypothesisBank(
        uv=np.zeros((2, 2)),
        required_rcs_dbsm=np.zeros(2),
        cell_ids=((0, 0), (0, 1)),
        cell_starts=np.array([0, 1], dtype=np.int64),
        true_cell=0,
        coherent=np.column_stack((rx, other_rx)),
        mimo=np.column_stack(
            (np.kron(quadrants / 2, rx), np.kron(quadrants / 2, other_rx))
        ),
    )
    errors = simulate_event(
        bank,
        rx,
        quadrants,
        coherent_snr_db=-300,
        mimo_to_coherent_snr=1,
        energies=np.array([0.0, 1.0]),
        trials=6000,
    )
    assert errors / 6000 == pytest.approx([0.5, 0.5], abs=0.025)


def test_error_upper_bound_and_invalid_normalization() -> None:
    upper = error_upper_bound(np.array([0, 10, 1000], dtype=np.int64), 1000)
    assert upper[0] == pytest.approx(1 - 0.05 ** (1 / 1000))
    assert 0.01 < upper[1] < 0.02
    assert upper[2] == 1.0
    with pytest.raises(ValueError, match="nonzero"):
        normalize_columns(np.zeros((8, 1), dtype=np.complex128))
