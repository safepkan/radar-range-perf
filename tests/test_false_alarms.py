"""Tests for false alarms per resolution cell and the multiple-testing threshold."""

from __future__ import annotations

import copy
import pickle
from dataclasses import asdict, replace

import numpy as np
import numpy.typing as npt
import pytest
from scipy.optimize import brentq
from scipy.signal import get_window
from scipy.special import gammaincc
from scipy.stats import ncx2

from radarperf import (
    AntennaPair,
    BeamSet,
    FalseAlarmBudget,
    FftAxis,
    FmcwWaveform,
    GaussianBeamAntenna,
    Geometry,
    MultiBeamUniformArrayAntenna,
    Radar,
    StandardProcessing,
    WindowSpec,
    false_alarm_budget,
    frontend,
    probability_of_detection,
    required_snr_db,
    target,
)
from radarperf.detection import detection_threshold
from radarperf.false_alarms import (
    beam_set_tests,
    fft_axis_tests,
    hermitian_sqrt,
    window_correlation,
)
from radarperf.units import SPEED_OF_LIGHT

PFA = 1.0e-6
THRESHOLD = -np.log(PFA)
THRESHOLD_4_LOOKS = detection_threshold(4, PFA)


def _dft_beams(count: int, oversampling: int = 1) -> npt.NDArray[np.complex128]:
    """Beams of a ``count``-channel uniform line array over one period."""
    u = np.arange(count * oversampling) / (count * oversampling)
    phase = 2.0 * np.pi * np.outer(u, np.arange(count))
    return np.asarray(np.exp(1j * phase) / np.sqrt(count), dtype=np.complex128)


def test_window_correlation_of_rectangular_and_hann_windows() -> None:
    rectangular = window_correlation("boxcar", 64, [0.0, 1.0, 2.0])
    assert np.abs(rectangular) == pytest.approx([1.0, 0.0, 0.0], abs=1e-12)
    # Hann squared has Fourier coefficients 3/8, -1/4, 1/16 at lags 0, 1, 2.
    hann = window_correlation("hann", 64, [1.0, 2.0])
    assert np.abs(hann) == pytest.approx([2.0 / 3.0, 1.0 / 6.0], abs=1e-12)


def test_fft_axis_without_padding_or_extent_counts_one_test() -> None:
    # Unpadded rectangular bins are independent: a bin is a peak above T with
    # probability exp(-T)(1 - exp(-T) + exp(-2T)/3), so one test per cell.
    axis = FftAxis("boxcar", 64)
    assert fft_axis_tests(axis, THRESHOLD) == pytest.approx(1.0, abs=1e-3)
    assert fft_axis_tests(axis, THRESHOLD_4_LOOKS, looks=4) == pytest.approx(
        1.0, abs=1e-3
    )
    assert fft_axis_tests(FftAxis("hann", 1), THRESHOLD) == 1.0


@pytest.mark.parametrize(
    ("window", "length", "padding", "looks", "frames"),
    [
        ("hann", 64, 2, 1, 16_000),
        # Padded, with the power summed over four non-coherent looks.
        ("hann", 64, 4, 4, 16_000),
        # Nearly a single nonzero sample: about one peak along the axis.
        (("kaiser", 8.0), 2, 4, 1, 800_000),
    ],
)
def test_fft_axis_tests_match_brute_force_peak_counts(
    window: WindowSpec, length: int, padding: int, looks: int, frames: int
) -> None:
    # Simulated noise through the window and a padded FFT, summed over the
    # looks; count local maxima above the threshold that one bin exceeds with
    # probability 1e-2, per unpadded bin (8000-12 000 peaks, so the tolerance
    # is about five standard deviations).
    rng = np.random.default_rng(5)
    threshold = detection_threshold(looks, 1.0e-2)
    taper = get_window(window, length, fftbins=True)
    chunk = max(1, 500_000 // (looks * length * padding))
    peaks = 0
    for start in range(0, frames, chunk):
        count = min(chunk, frames - start)
        noise = (
            rng.standard_normal((count, looks, length))
            + 1j * rng.standard_normal((count, looks, length))
        ) / np.sqrt(2.0)
        spectrum = np.fft.fft(noise * taper, n=length * padding, axis=2)
        power = np.sum(np.abs(spectrum) ** 2, axis=1) / np.sum(taper**2)
        peaks += int(
            np.sum(
                (power >= np.roll(power, 1, axis=1))
                & (power > np.roll(power, -1, axis=1))
                & (power > threshold)
            )
        )
    brute = peaks / (frames * length) / 1.0e-2
    computed = fft_axis_tests(
        FftAxis(window, length, length * padding), threshold, looks
    )
    assert computed == pytest.approx(brute, rel=0.05)


def test_single_nonzero_window_sample_gives_one_detection_per_axis() -> None:
    # A two-point periodic Hann window is [0, 1] (Blackman nearly so): every
    # bin has the same power, so one detection along the axis, 1/2 per cell,
    # padded or not. Windows that approach this case tend to the same count.
    assert fft_axis_tests(FftAxis("hann", 2), THRESHOLD) == 0.5
    assert fft_axis_tests(FftAxis("hann", 2, 16), THRESHOLD) == 0.5
    assert fft_axis_tests(FftAxis("blackman", 2), THRESHOLD) == 0.5
    near = fft_axis_tests(FftAxis(("kaiser", 12.0), 2), THRESHOLD)
    assert near == pytest.approx(0.5, rel=1e-3)


@pytest.mark.parametrize("window", ["hann", "boxcar"])
def test_heavily_padded_fft_axis_approaches_the_rice_limit(window: str) -> None:
    # Rice: envelope up-crossings of the power level T at sqrt(lambda T / pi)
    # exp(-T) per bin, lambda = (2 pi)^2 times the variance of the sample
    # index in window lengths, weighted by the squared window.
    length = 64
    w2 = get_window(window, length, fftbins=True) ** 2
    index = np.arange(length) / length
    mean = np.sum(index * w2) / np.sum(w2)
    variance = np.sum((index - mean) ** 2 * w2) / np.sum(w2)
    rice = np.sqrt((2.0 * np.pi) ** 2 * variance * THRESHOLD / np.pi)
    padded = fft_axis_tests(FftAxis(window, length, 16 * length), THRESHOLD)
    assert padded == pytest.approx(rice, rel=0.015)
    assert fft_axis_tests(FftAxis(window, length, 4 * length), THRESHOLD) < padded


def test_beam_set_tests_for_identical_orthogonal_and_single_beams() -> None:
    beams = _dft_beams(8)
    assert beam_set_tests(beams[:1], THRESHOLD) == 1.0
    # Identical beams always exceed together: one test.
    assert beam_set_tests(np.repeat(beams[:1], 5, axis=0), THRESHOLD) == (
        pytest.approx(1.0)
    )
    # Orthogonal beams are independent tests, with any number of looks.
    assert beam_set_tests(beams, THRESHOLD) == pytest.approx(8.0, rel=1e-3)
    assert beam_set_tests(beams, THRESHOLD_4_LOOKS, looks=4) == pytest.approx(
        8.0, rel=1e-3
    )
    # Unnormalised weights describe the same beams.
    assert beam_set_tests(3.0 * beams, THRESHOLD) == beam_set_tests(beams, THRESHOLD)


@pytest.mark.parametrize("looks", [1, 4])
def test_beam_set_tests_match_brute_force(looks: int) -> None:
    # Eight channels, 16 correlated beams at half the orthogonal spacing, beam
    # power summed over the looks; one beam exceeds the threshold with
    # probability 1e-2 (about 20 000 best-beam exceedances).
    rng = np.random.default_rng(8)
    beams, threshold = _dft_beams(8, 2), detection_threshold(looks, 1.0e-2)
    exceedances = 0
    samples, chunk = 200_000, 50_000
    for _ in range(samples // chunk):
        noise = (
            rng.standard_normal((chunk, looks, 8))
            + 1j * rng.standard_normal((chunk, looks, 8))
        ) / np.sqrt(2.0)
        beam_power = np.sum(np.abs(noise @ beams.conj().T) ** 2, axis=1)
        exceedances += int(np.sum(np.max(beam_power, axis=1) > threshold))
    brute = exceedances / samples / 1.0e-2
    assert beam_set_tests(beams, threshold, looks) == pytest.approx(brute, rel=0.03)


def _direct_2d_tests(window: str, padding: int, threshold: float) -> float:
    """Peaks per range-Doppler cell over all eight neighbours, by conditioning.

    The 1-D derivation in ``radarperf.false_alarms`` carries over: each
    neighbour is below the centre power p exactly when p exceeds the square of
    its positive root, so the centre is a 2-D peak when p exceeds the largest.
    """
    lags = (np.arange(3)[:, None] - np.arange(3)[None, :]).ravel() / padding
    axis_cov = window_correlation(window, 64, lags).reshape(3, 3)
    cov = np.kron(axis_cov, axis_cov)  # bins (range, Doppler) -> 3 r + d
    others = [index for index in range(9) if index != 4]
    gain = cov[others, 4]
    residual = cov[np.ix_(others, others)] - np.outer(gain, gain.conj())
    root = hermitian_sqrt(residual)
    rng = np.random.default_rng(13)
    white = (
        rng.standard_normal((200_000, 8)) + 1j * rng.standard_normal((200_000, 8))
    ) / np.sqrt(2.0)
    residual_draws = white @ root.T
    cross = np.real(gain.conj() * residual_draws)
    spread = 1.0 - np.abs(gain) ** 2
    positive_root = (
        cross + np.sqrt(cross**2 + spread * np.abs(residual_draws) ** 2)
    ) / spread
    levels = np.max(positive_root**2, axis=1)
    peaks = padding**2 * np.mean(np.exp(-np.maximum(levels, threshold)))
    return float(peaks / np.exp(-threshold))


@pytest.mark.parametrize(
    ("window", "padding"),
    [
        ("hann", 2),
        ("hann", 4),
        ("hann", 8),
        ("boxcar", 2),
        ("boxcar", 4),
        ("boxcar", 8),
    ],
)
def test_range_doppler_product_matches_a_direct_2d_peak_count(
    window: str, padding: int
) -> None:
    # The product of the 1-D factors lies a few percent above the direct count
    # with eight neighbours (fourfold padding at 1e-6: Hann 3.13 against 3.02,
    # rectangular 9.53 against 9.35), which moves the threshold by under
    # 0.02 dB up to eightfold padding (largest, Hann eightfold: 0.017 dB).
    axis = FftAxis(window, 64, 64 * padding)
    product = fft_axis_tests(axis, THRESHOLD) ** 2
    direct = _direct_2d_tests(window, padding, THRESHOLD)
    assert direct < product
    shift_db = 10.0 * np.log10(
        (THRESHOLD + np.log(product)) / (THRESHOLD + np.log(direct))
    )
    assert shift_db < 0.02


def test_range_and_angle_factors_multiply_in_a_simulated_search() -> None:
    # Eight channels, 16 beams, Hann range FFT padded twofold: count range
    # peaks of the best-beam power above T = ln(1000) (about 12 000 peaks).
    rng = np.random.default_rng(21)
    length, padding, threshold = 64, 2, np.log(1000.0)
    frames, chunk = 12_000, 2_000
    beams = _dft_beams(8, 2)
    taper = get_window("hann", length, fftbins=True)
    peaks = 0
    for _ in range(frames // chunk):
        noise = (
            rng.standard_normal((chunk, length, 8))
            + 1j * rng.standard_normal((chunk, length, 8))
        ) / np.sqrt(2.0)
        spectrum = np.fft.fft(noise * taper[None, :, None], n=length * padding, axis=1)
        spectrum /= np.sqrt(np.sum(taper**2))
        best = np.max(np.abs(spectrum @ beams.conj().T) ** 2, axis=2)
        peaks += int(
            np.sum(
                (best >= np.roll(best, 1, axis=1))
                & (best > np.roll(best, -1, axis=1))
                & (best > threshold)
            )
        )
    joint = peaks / (frames * length) / np.exp(-threshold)
    product = fft_axis_tests(
        FftAxis("hann", length, length * padding), threshold
    ) * beam_set_tests(beams, threshold)
    assert product == pytest.approx(joint, rel=0.05)


def test_false_alarm_budget_multiplies_axes_and_holds_the_cell_pfa() -> None:
    range_axis = FftAxis("hann", 256, 512)
    doppler_axis = FftAxis("hann", 128, 512)
    beams = _dft_beams(8, 2)
    budget = false_alarm_budget(
        PFA,
        range_axis=range_axis,
        doppler_axis=doppler_axis,
        beam_weights=beams,
    )
    threshold = budget.threshold
    assert budget.tests["range"] == pytest.approx(
        fft_axis_tests(range_axis, threshold), rel=1e-6
    )
    assert budget.tests["doppler"] == pytest.approx(
        fft_axis_tests(doppler_axis, threshold), rel=1e-6
    )
    assert budget.tests["angle"] == pytest.approx(
        beam_set_tests(beams, threshold), rel=1e-6
    )
    assert budget.effective_tests * budget.pfa_per_test == pytest.approx(PFA)
    assert gammaincc(1, threshold) == pytest.approx(budget.pfa_per_test)
    assert budget.threshold_increase_db == pytest.approx(
        10.0 * np.log10(threshold / THRESHOLD)
    )
    # The doppler axis is padded fourfold, range only twofold.
    assert 1.0 < budget.tests["range"] < budget.tests["doppler"] < 2.0


def test_false_alarm_budget_without_axes_and_with_looks() -> None:
    plain = false_alarm_budget(PFA, looks=4)
    assert plain.pfa_per_test == PFA
    assert plain.effective_tests == 1.0
    assert plain.threshold_increase_db == 0.0
    assert gammaincc(4, plain.threshold) == pytest.approx(PFA)


def test_false_alarm_budget_validates_inputs() -> None:
    with pytest.raises(ValueError, match="pfa_per_cell"):
        false_alarm_budget(0.0)
    with pytest.raises(ValueError, match="looks"):
        false_alarm_budget(PFA, looks=0)
    # About one bin in three is a local maximum, which caps the false
    # detections per cell whatever the threshold.
    with pytest.raises(ValueError, match="too large"):
        false_alarm_budget(0.9, range_axis=FftAxis("hann", 64))
    with pytest.raises(ValueError, match="shape"):
        false_alarm_budget(PFA, beam_weights=np.ones(8))
    with pytest.raises(ValueError, match="fft_size"):
        FftAxis("hann", 64, 32)


def test_threshold_near_the_largest_reachable_pfa() -> None:
    # Four-point Hann on both axes with four looks: the product model's false
    # detections per cell peak at about 0.104 near T = 3.5. At 0.1 the fixed
    # point converges too slowly, and the bracketed search finds the root on
    # the falling branch; above the peak no threshold reaches the value.
    axis = FftAxis("hann", 4)

    def per_cell(threshold: float) -> float:
        return float(fft_axis_tests(axis, threshold, 4) ** 2 * gammaincc(4, threshold))

    budget = false_alarm_budget(0.1, 4, range_axis=axis, doppler_axis=axis)
    threshold = budget.threshold
    assert per_cell(threshold) == pytest.approx(0.1, rel=1e-6)
    # The upper root, past the peak and below the single-test threshold, with
    # false detections falling as the threshold rises.
    assert 3.5 < threshold < detection_threshold(4, 0.1)
    assert per_cell(threshold + 0.1) < 0.1 < per_cell(threshold - 0.1)
    with pytest.raises(ValueError, match="too large"):
        false_alarm_budget(0.11, 4, range_axis=axis, doppler_axis=axis)


def test_hermitian_sqrt_ignores_eigenvector_phases() -> None:
    # Any column phases of the eigenvectors give the same principal root, so
    # seeded noise samples do not depend on the LAPACK implementation.
    lags = (np.arange(3)[:, None] - np.arange(3)[None, :]).ravel() / 4.0
    cov = window_correlation("hann", 64, lags).reshape(3, 3)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    rephased = eigenvectors * np.exp(1j * np.array([0.3, -1.2, 2.5]))
    rebuilt = (rephased * eigenvalues) @ rephased.conj().T
    root = hermitian_sqrt(cov)
    assert hermitian_sqrt(rebuilt) == pytest.approx(root, abs=1e-12)
    assert root @ root == pytest.approx(cov, abs=1e-12)
    assert root == pytest.approx(root.conj().T, abs=1e-14)


def test_strongest_beam_pd_is_conservative_when_beams_share_the_target() -> None:
    # Pd is evaluated in the beam with the strongest expected signal. With an
    # equal response in two orthogonal beams (independent noise, a shared
    # Swerling 1 amplitude) either beam may detect: at a per-test Pfa of 5e-7
    # (1e-6 per cell over the two beams) the strongest-beam Pd of 0.50 is
    # 0.57 for any beam. Integrate the two Rician misses over the shared
    # exponential target power.
    pfa_per_test = 5.0e-7
    snr_db = required_snr_db(0.5, pfa_per_test, swerling=1)
    snr = 10.0 ** (snr_db / 10.0)
    nodes, weights = np.polynomial.laguerre.laggauss(80)
    miss = ncx2.cdf(2.0 * -np.log(pfa_per_test), df=2, nc=2.0 * snr * nodes)
    any_beam = 1.0 - float(np.sum(weights * miss**2))
    assert probability_of_detection(snr_db, pfa_per_test) == pytest.approx(
        0.5, abs=1e-4
    )
    assert any_beam == pytest.approx(0.572, abs=0.001)

    # As SNR: either beam reaches Pd 0.5 with about 1 dB less.
    def any_beam_pd(trial_db: float) -> float:
        trial = 10.0 ** (trial_db / 10.0)
        trial_miss = ncx2.cdf(2.0 * -np.log(pfa_per_test), df=2, nc=2.0 * trial * nodes)
        return 1.0 - float(np.sum(weights * trial_miss**2))

    gap_db = snr_db - brentq(lambda x: any_beam_pd(x) - 0.5, snr_db - 5.0, snr_db)
    assert gap_db == pytest.approx(0.98, abs=0.01)


def _radar(n_chirps: int = 128, **processing: object) -> Radar:
    waveform = FmcwWaveform(
        center_frequency_hz=77e9,
        bandwidth_hz=1e9,
        sample_rate_hz=20e6,
        n_samples=256,
        n_chirps=n_chirps,
    )
    return Radar(
        frontend=frontend.awr2243(),
        waveform=waveform,
        processing=StandardProcessing(**processing),  # type: ignore[arg-type]
        antenna=AntennaPair.from_element(GaussianBeamAntenna(12.0, 60.0, 12.0)),
    )


def test_radar_counts_padding_and_keeps_the_per_test_convention() -> None:
    unpadded = _radar()
    padded = _radar(range_fft_size=1024, doppler_fft_size=512)
    plain = unpadded.false_alarm_budget()
    assert plain.tests["range"] == pytest.approx(0.98, abs=0.01)
    assert plain.tests["angle"] == 1.0
    assert padded.false_alarm_budget().pfa_per_test < plain.pfa_per_test

    per_test = replace(padded, pfa_reference="test").false_alarm_budget()
    assert per_test.pfa_per_test == padded.default_pfa
    assert per_test.pfa_per_cell is None
    assert per_test.threshold_increase_db == 0.0
    with pytest.raises(ValueError, match="pfa_reference"):
        replace(padded, pfa_reference="beam")  # type: ignore[arg-type]


def test_radar_with_two_hann_chirps_counts_one_doppler_detection() -> None:
    # Regression: the two-point Hann Doppler window made the count NaN, and
    # link_budget() raised a misleading "pfa_per_cell is too large".
    radar = _radar(n_chirps=2)
    budget = radar.false_alarm_budget()
    assert budget.tests["doppler"] == 0.5
    assert budget.pfa_per_test == pytest.approx(PFA / (budget.tests["range"] * 0.5))
    car, geometry = target.car(), Geometry(range_m=50.0)
    assert radar.link_budget(car, geometry).false_alarms == budget
    assert 0.0 < radar.probability_of_detection(car, geometry) < 1.0


def test_explicit_pfa_overrides_an_unreachable_default() -> None:
    # Regression: probability_of_detection() built the link budget at
    # default_pfa first, so an unreachable default raised even with a valid
    # override. The reported budget now matches the Pfa used for Pd.
    radar = replace(_radar(range_fft_size=1024), default_pfa=0.9)
    car, geometry = target.car(), Geometry(range_m=120.0)
    with pytest.raises(ValueError, match="too large"):
        radar.link_budget(car, geometry)
    budget = radar.link_budget(car, geometry, pfa=PFA)
    assert budget.false_alarms == radar.false_alarm_budget(PFA)
    expected = probability_of_detection(
        budget.sinr_db, radar.false_alarm_budget(PFA).pfa_per_test
    )
    assert radar.probability_of_detection(car, geometry, pfa=PFA) == (
        pytest.approx(expected)
    )


def test_budget_copies_protect_the_cache_and_serialise() -> None:
    # Each call gets its own tests mapping: changing it leaves the cache, and
    # later identical calls, intact; budgets still copy and pickle.
    axis = FftAxis("hann", 64, 128)
    budget = false_alarm_budget(PFA, range_axis=axis)
    budget.tests["range"] = 1.0  # type: ignore[index]
    again = false_alarm_budget(PFA, range_axis=axis)
    assert again.effective_tests * again.pfa_per_test == pytest.approx(PFA)
    assert pickle.loads(pickle.dumps(again)) == again
    assert copy.deepcopy(again) == again
    link = _radar(range_fft_size=512).link_budget(target.car(), Geometry(120.0))
    assert asdict(link)["false_alarms"]["tests"]["range"] > 1.0


def test_false_alarm_budget_validates_per_test_values() -> None:
    with pytest.raises(ValueError, match="pfa_per_test"):
        FalseAlarmBudget(pfa_per_test=0.0, looks=1)
    with pytest.raises(ValueError, match="looks"):
        FalseAlarmBudget(pfa_per_test=1e-6, looks=0)
    radar = replace(_radar(), default_pfa=1.5, pfa_reference="test")
    with pytest.raises(ValueError, match="pfa_per_test"):
        radar.false_alarm_budget()


def test_radar_detects_at_the_per_test_pfa() -> None:
    radar = _radar(range_fft_size=1024)
    car, geometry = target.car(), Geometry(range_m=120.0)
    budget = radar.link_budget(car, geometry)
    assert budget.false_alarms == radar.false_alarm_budget()
    expected = probability_of_detection(
        budget.sinr_db, radar.false_alarm_budget().pfa_per_test, swerling=car.swerling
    )
    assert radar.probability_of_detection(car, geometry) == pytest.approx(expected)
    text = str(budget)
    assert "Pfa per cell" in text and "range tests" in text


def test_radar_counts_receive_beams_as_tests() -> None:
    element = GaussianBeamAntenna(12.0, 80.0, 30.0)
    beams = MultiBeamUniformArrayAntenna(
        element,
        horizontal_count=4,
        vertical_count=2,
        horizontal_spacing_m=1.0,
        vertical_spacing_m=0.5,
        center_frequency_hz=SPEED_OF_LIGHT,
        steering_u=[-0.25, 0.0, 0.25, 0.5],
        steering_v=[0.0, 0.0, 0.0, 0.0],
    )
    assert isinstance(beams, BeamSet)
    radar = replace(_radar(), antenna=AntennaPair(tx=element, rx=beams))
    # Four channels one wavelength apart: beams 1/4 apart in u are orthogonal,
    # hence four independent tests.
    assert radar.false_alarm_budget().tests["angle"] == pytest.approx(4.0, rel=1e-3)


def test_multi_beam_weights_reproduce_the_array_factor() -> None:
    element = GaussianBeamAntenna(12.0, 80.0, 30.0)
    beams = MultiBeamUniformArrayAntenna(
        element,
        horizontal_count=4,
        vertical_count=2,
        horizontal_spacing_m=0.6,
        vertical_spacing_m=0.9,
        center_frequency_hz=SPEED_OF_LIGHT,
        steering_u=[0.0, 0.1, -0.2],
        steering_v=[0.0, 0.05, 0.1],
    )
    weights = beams.beam_weights()
    assert weights.shape == (3, 8)
    assert np.linalg.norm(weights, axis=1) == pytest.approx(np.ones(3))
    coupling_db = 10.0 * np.log10(np.abs(weights.conj() @ weights.T) ** 2)
    for k in range(3):
        expected = beams.beam(k).array_factor_relative_db_uv(
            beams.steering_u, beams.steering_v
        )
        assert coupling_db[:, k] == pytest.approx(expected, abs=1e-9)
