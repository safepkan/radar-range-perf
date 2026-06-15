"""Tests for the detection module."""

from __future__ import annotations

import numpy as np
import pytest

from radarperf import detection
from radarperf.detection import (
    cumulative_pd,
    probability_of_acquisition_mofn,
    probability_of_detection,
    required_snr_db,
)


def test_single_pulse_swerling1_closed_form() -> None:
    # Swerling 1, N=1: Pd = Pfa ** (1 / (1 + SNR)).
    pfa = 1e-4
    for snr_db in (5.0, 10.0, 15.0):
        snr = 10.0 ** (snr_db / 10.0)
        expected = pfa ** (1.0 / (1.0 + snr))
        got = probability_of_detection(snr_db, pfa, swerling=1, n_pulses=1)
        assert np.isclose(got, expected, atol=1e-6)


def test_pd_floor_is_pfa() -> None:
    pfa = 1e-3
    # Very low SNR -> Pd approaches Pfa.
    for case in (0, 1, 2, 3, 4):
        pd = probability_of_detection(-40.0, pfa, swerling=case, n_pulses=1)
        assert pd == pytest.approx(pfa, abs=5e-4)


def test_pd_monotonic_in_snr() -> None:
    snr = np.linspace(-10.0, 30.0, 50)
    for case in (0, 1, 2, 3, 4):
        pd = np.asarray(probability_of_detection(snr, 1e-6, swerling=case))
        assert np.all(np.diff(pd) >= -1e-9)
        assert pd[0] < pd[-1]


def test_required_snr_round_trip() -> None:
    pfa = 1e-6
    for case in (0, 1, 2, 3, 4):
        for pd_target in (0.5, 0.9):
            snr_db = required_snr_db(pd_target, pfa, swerling=case, n_pulses=1)
            pd = probability_of_detection(snr_db, pfa, swerling=case, n_pulses=1)
            assert pd == pytest.approx(pd_target, abs=1e-3)


def test_albersheim_matches_exact_swerling0() -> None:
    pfa = 1e-6
    for pd_target in (0.5, 0.8, 0.9):
        for n in (1, 4, 8):
            approx = detection.albersheim_required_snr_db(pd_target, pfa, n)
            exact = required_snr_db(pd_target, pfa, swerling=0, n_pulses=n)
            assert abs(approx - exact) < 1.0  # Albersheim accurate to ~0.2 dB


def test_shnidman_matches_exact() -> None:
    pfa = 1e-6
    for case in (1, 3):
        for pd_target in (0.5, 0.8):
            for n in (1, 10):
                approx = detection.shnidman_required_snr_db(pd_target, pfa, n, case)
                exact = required_snr_db(pd_target, pfa, swerling=case, n_pulses=n)
                assert abs(approx - exact) < 1.5


def test_swerling_against_monte_carlo() -> None:
    rng = np.random.default_rng(12345)
    pfa = 1e-3
    trials = 120_000

    def mc(n: int, snr: float, case: int) -> float:
        thr = detection.detection_threshold(n, pfa)
        if case == 0:
            power = snr * np.ones((trials, n))
        elif case == 1:
            power = rng.exponential(snr, size=(trials, 1)) * np.ones((trials, n))
        elif case == 2:
            power = rng.exponential(snr, size=(trials, n))
        elif case == 3:
            power = rng.gamma(2.0, snr / 2.0, size=(trials, 1)) * np.ones((trials, n))
        else:
            power = rng.gamma(2.0, snr / 2.0, size=(trials, n))
        phase = rng.uniform(0.0, 2 * np.pi, size=(trials, n))
        signal = np.sqrt(power) * np.exp(1j * phase)
        noise = (
            rng.standard_normal((trials, n)) + 1j * rng.standard_normal((trials, n))
        ) / np.sqrt(2.0)
        statistic = np.sum(np.abs(signal + noise) ** 2, axis=1)
        return float(np.mean(statistic > thr))

    for case in (0, 1, 2, 3, 4):
        for n in (1, 3):
            for snr_db in (8.0, 13.0):
                snr = 10.0 ** (snr_db / 10.0)
                analytic = float(
                    probability_of_detection(snr_db, pfa, swerling=case, n_pulses=n)
                )
                simulated = mc(n, snr, case)
                assert abs(analytic - simulated) < 0.02, (case, n, snr_db)


def test_cumulative_pd() -> None:
    pd = [0.2, 0.2, 0.2]
    cum = cumulative_pd(pd)
    assert np.isclose(cum[0], 0.2)
    assert np.isclose(cum[-1], 1.0 - 0.8**3)
    assert np.all(np.diff(cum) >= 0.0)


def test_mofn_reduces_to_cumulative_for_1_of_1() -> None:
    pd = [0.3, 0.3, 0.3, 0.3]
    one_of_one = probability_of_acquisition_mofn(pd, m=1, n=1)
    assert np.allclose(one_of_one, cumulative_pd(pd))


def test_mofn_perfect_detection() -> None:
    pd = [1.0] * 6
    confirmed = probability_of_acquisition_mofn(pd, m=2, n=3)
    # With perfect detection, 2-of-3 is satisfied exactly at the 2nd scan.
    assert confirmed[0] == pytest.approx(0.0)
    assert confirmed[1] == pytest.approx(1.0)
    assert np.all(np.diff(confirmed) >= 0.0)


def test_mofn_bounds_and_monotonic() -> None:
    rng = np.random.default_rng(0)
    pd = rng.uniform(0.2, 0.8, size=20).tolist()
    confirmed = probability_of_acquisition_mofn(pd, m=3, n=5)
    assert np.all((confirmed >= 0.0) & (confirmed <= 1.0))
    assert np.all(np.diff(confirmed) >= -1e-12)
