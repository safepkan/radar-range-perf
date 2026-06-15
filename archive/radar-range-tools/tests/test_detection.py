from __future__ import annotations

import numpy as np

from radar_range.detection import (
    pd_from_snr,
    pd_nonfluctuating,
    probability_m_of_n,
    square_law_threshold_chi2,
)


def test_threshold_single_look_matches_exponential_convention() -> None:
    pfa = 1.0e-6
    threshold_chi2 = square_law_threshold_chi2(pfa, noncoherent_looks=1)
    np.testing.assert_allclose(threshold_chi2 / 2.0, -np.log(pfa))


def test_pd_is_monotonic_with_snr() -> None:
    snr = np.asarray([0.0, 1.0, 10.0, 100.0])
    pd = pd_nonfluctuating(snr, pfa=1.0e-6)
    assert np.all(np.diff(pd) >= 0.0)


def test_swerling_dispatch_shape() -> None:
    snr = np.linspace(0.0, 20.0, 5)
    pd = pd_from_snr(snr, pfa=1.0e-6, fluctuation_model="swerling1")
    assert pd.shape == snr.shape


def test_probability_m_of_n() -> None:
    pd = probability_m_of_n(0.5, m=2, n=3)
    np.testing.assert_allclose(pd, 0.5)


def test_pd_with_empty_noise_looks_reduces_to_pfa_at_zero_snr() -> None:
    pfa = 1.0e-6
    pd_nonfluct = pd_nonfluctuating(
        0.0,
        pfa=pfa,
        noncoherent_looks=24,
        signal_looks=16,
    )
    pd_swerling2_empty = pd_from_snr(
        0.0,
        pfa=pfa,
        fluctuation_model="swerling2",
        noncoherent_looks=24,
        signal_looks=16,
    )

    np.testing.assert_allclose(pd_nonfluct, pfa, rtol=1.0e-10)
    np.testing.assert_allclose(pd_swerling2_empty, pfa, rtol=1.0e-10)
