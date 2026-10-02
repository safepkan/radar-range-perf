"""False alarms per resolution cell: effective tests and the detection threshold.

Convention
----------
``Radar.default_pfa`` is the false-alarm probability per range-Doppler
resolution cell: the expected number of false detections per bin of the
*unpadded* range and Doppler FFTs, over all beams formed in that cell.  False
alarms per frame are this value times the numbers of range and Doppler cells.
A detection is a local maximum of the detection statistic along each FFT axis
(peak grouping), so a noise peak spread over neighbouring bins counts once.

The detector compares every test -- one FFT bin of one beam -- with a single
threshold ``T`` in units of the noise power per look.  With ``Q(n, T)`` the
probability that one test exceeds it (square-law detection of ``n``
non-coherent looks; :func:`~radarperf.detection.detection_threshold`), the
false detections per cell are ``tests(T) Q(n, T)``.  ``tests(T)`` is the
*effective number of tests* per cell.  It is close to 1 for an unpadded FFT
and one beam; zero padding and beam sets raise it, so ``T`` must rise to hold
the per-cell value.  :func:`false_alarm_budget` solves for that threshold.

Range and Doppler
-----------------
For one FFT axis padded ``P`` times, neighbouring bins are ``1/P``
resolution cells apart.  A bin is a peak if its power exceeds that of both
neighbours.  The three bins are jointly complex Gaussian with the correlation
of the windowed FFT (:func:`window_correlation`).  Conditional on the centre
bin's looks ``x0`` with ``|x0|^2 = p``, each neighbour is ``c x0 + W`` with
``W`` Gaussian and independent of ``x0``.  By unitary invariance over the looks,
its power is ``|c|^2 p + 2 sqrt(p) Re(c* W_1) + |W|^2``.  The neighbour is
below the centre if and only if ``p`` exceeds the square of the positive root
of ``(1 - |c|^2) x^2 - 2 Re(c* W_1) x - |W|^2``.  Each sample of ``W``
therefore gives one level ``p*`` above which the centre is a peak, and

    peaks per cell above T = P E[Q(n, max(T, p*))],

with no rare events to sample.  For large ``P`` the count approaches Rice's
level-crossing rate of the envelope, ``sqrt(lambda T / pi) exp(-T)`` per cell
for one look, where ``lambda`` is ``(2 pi)^2`` times the variance of the sample
index (in window lengths) weighted by the squared window.

A window with a single nonzero sample (such as a two-point periodic Hann
window, or a one-point axis) makes ``|c| = 1``: every bin of the axis has the
same power, and a detector with peak grouping reports one detection along the
whole axis, ``1 / length`` per cell.  Windows that approach that case have
that count as their limit.

Angle
-----
For a set of ``K`` beams with unit-norm weights the per-cell statistic is the
largest beam power.  Writing ``A_k`` for "beam ``k`` exceeds ``T``" and ``C``
for the number of beams that do,

    P(any A_k) = E[sum_k 1(A_k) / C] = sum_k P(A_k) E[1 / C | A_k],

and every ``P(A_k)`` equals ``Q(n, T)``.  The angle factor is therefore
``K E[1 / C]`` with the beam ``k`` drawn uniformly and the noise drawn given
``A_k``.  ``1 / C`` lies in ``(0, 1]``, so a few thousand samples fix the
factor to a fraction of a percent at any threshold.

Combining the axes
------------------
The total is the product of the range, Doppler and angle factors.  This is
an approximation for small Pfa, where exceedances are nearly independent
between axes; ``docs/losses.md`` lists the cases it has been checked for.
It is not a false-detection rate at high Pfa: there the product can even
rise with the threshold before it falls.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Callable, Final, Mapping

import numpy as np
import numpy.typing as npt
from scipy.optimize import brentq
from scipy.signal import get_window
from scipy.special import gammaincc, gammainccinv

from .detection import detection_threshold
from .protocols import FftAxis, WindowSpec
from .units import linear_to_db

# Seeded Monte Carlo sample sizes.  The FFT-axis count reaches about 0.1 %
# and the beam count a few tenths of a percent (both checked in the tests);
# 1 % in the tests changes the threshold by under 0.003 dB at Pfa 1e-6.
_FFT_SAMPLES: Final[int] = 200_000
_FFT_SEED: Final[int] = 20261001
_BEAM_SAMPLES: Final[int] = 20_000
_BEAM_SEED: Final[int] = 20261002
_BEAM_CHUNK: Final[int] = 2_000
_MAX_ITERATIONS: Final[int] = 50
# Below this ``1 - |c|^2`` a neighbour's power equals the centre's to within
# rounding: the window has a single nonzero sample.
_DEGENERATE_SPREAD: Final[float] = 1.0e-12
_TOO_LARGE: Final[str] = (
    "pfa_per_cell is too large: no threshold gives that many false detections "
    "per cell"
)

# The effective tests per axis and their product at a threshold.
_TestCount = Callable[[float], tuple[dict[str, float], float]]


@dataclass(frozen=True)
class FalseAlarmBudget:
    """How the false-alarm probability sets the detection threshold.

    ``pfa_per_test`` is the probability that one test (one FFT bin of one
    beam) exceeds the threshold; the detector uses it.  When the radar's Pfa
    is per range-Doppler cell, ``pfa_per_cell`` holds it and ``tests`` the
    effective tests per cell on each axis (``"range"``, ``"doppler"``,
    ``"angle"``; 1 for an axis that adds none).  When the Pfa is given per
    test, ``pfa_per_cell`` is ``None`` and ``tests`` is empty.
    :func:`false_alarm_budget` caches its results and returns each caller its
    own copy of ``tests``.
    """

    pfa_per_test: float
    looks: int
    pfa_per_cell: float | None = None
    tests: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 < self.pfa_per_test < 1.0:
            raise ValueError("pfa_per_test must be in (0, 1)")
        _check_looks(self.looks)
        if self.pfa_per_cell is not None and not 0.0 < self.pfa_per_cell < 1.0:
            raise ValueError("pfa_per_cell must be in (0, 1)")

    @property
    def threshold(self) -> float:
        """Detection threshold per test, in units of the noise power per look."""
        return detection_threshold(self.looks, self.pfa_per_test)

    @property
    def effective_tests(self) -> float:
        """Effective tests per range-Doppler cell, all axes together."""
        return float(math.prod(self.tests.values()))

    @property
    def threshold_increase_db(self) -> float:
        """Threshold relative to testing a single bin at the per-cell Pfa [dB].

        Zero when the Pfa is given per test.
        """
        if self.pfa_per_cell is None:
            return 0.0
        single = detection_threshold(self.looks, self.pfa_per_cell)
        return float(linear_to_db(self.threshold / single))


def window_correlation(
    window: WindowSpec, length: int, lag_bins: npt.ArrayLike
) -> npt.NDArray[np.complex128]:
    """Correlation of windowed-FFT outputs ``lag_bins`` unpadded bins apart.

    ``E[X(f + lag) X(f)*] / E[|X(f)|^2]`` for white noise through the periodic
    ``length``-point window from :func:`scipy.signal.get_window`.
    """
    if length < 1:
        raise ValueError("length must be >= 1")
    w2 = np.asarray(get_window(window, length, fftbins=True), dtype=float) ** 2
    lags = np.atleast_1d(np.asarray(lag_bins, dtype=float))
    phase = np.exp(-2j * np.pi * np.outer(lags, np.arange(length)) / length)
    return np.asarray(phase @ w2 / np.sum(w2), dtype=np.complex128)


def fft_axis_tests(axis: FftAxis, threshold: float, looks: int = 1) -> float:
    """Effective tests per resolution cell of one FFT axis.

    The expected number of local maxima above ``threshold`` per unpadded bin,
    divided by the probability ``Q(looks, threshold)`` that a single bin
    exceeds it.  ``threshold`` is in units of the noise power per look.  If
    the window has a single nonzero sample, every bin has the same power and
    the count is ``1 / axis.length``: one detection along the axis.
    """
    _check_looks(looks)
    levels = _peak_levels(axis, looks)
    if levels is None:
        return 1.0 / axis.length
    exceed = float(gammaincc(looks, threshold))
    peaks = float(np.mean(gammaincc(looks, np.maximum(levels, threshold))))
    return axis.padding * peaks / exceed


def beam_set_tests(
    beam_weights: npt.ArrayLike, threshold: float, looks: int = 1
) -> float:
    """Effective tests per cell of a set of beams formed from the same channels.

    ``beam_weights`` has shape ``(beams, channels)``; each row is normalised to
    unit norm, which models a threshold set relative to each beam's own noise
    power.  Returns ``P(largest beam power > threshold) / Q(looks, threshold)``
    for white channel noise.
    """
    _check_looks(looks)
    weights = _unit_rows(beam_weights)
    return _beam_set_tests(weights, threshold, looks)


def false_alarm_budget(
    pfa_per_cell: float,
    looks: int = 1,
    *,
    range_axis: FftAxis | None = None,
    doppler_axis: FftAxis | None = None,
    beam_weights: npt.ArrayLike | None = None,
) -> FalseAlarmBudget:
    """Per-test Pfa and threshold that hold ``pfa_per_cell``.

    ``looks`` counts all cells the detector sums non-coherently, including
    noise-only (collapsing) cells.  An axis left as ``None`` contributes one
    test per cell.  The threshold solves ``tests(T) Q(looks, T) =
    pfa_per_cell`` by fixed-point iteration; ``tests`` depends only weakly
    on ``T``, so a few iterations suffice.  Results are cached.

    The model is meant for small Pfa per cell.  Near the largest value it can
    produce (around 0.1 per cell), the iteration converges slowly; a bracketed
    search then solves on the branch where the false detections fall with
    the threshold.  Larger values raise :class:`ValueError`.
    """
    if not 0.0 < pfa_per_cell < 1.0:
        raise ValueError("pfa_per_cell must be in (0, 1)")
    _check_looks(looks)
    weights = None if beam_weights is None else _unit_rows(beam_weights)
    key = (
        pfa_per_cell,
        looks,
        range_axis,
        doppler_axis,
        None if weights is None else (weights.shape, weights.tobytes()),
    )
    cached = _BUDGET_CACHE.get(key)
    if cached is not None:
        return replace(cached, tests=dict(cached.tests))

    def tests_at(threshold: float) -> tuple[dict[str, float], float]:
        tests = {
            "range": (
                1.0
                if range_axis is None
                else fft_axis_tests(range_axis, threshold, looks)
            ),
            "doppler": (
                1.0
                if doppler_axis is None
                else fft_axis_tests(doppler_axis, threshold, looks)
            ),
            "angle": (
                1.0 if weights is None else _beam_set_tests(weights, threshold, looks)
            ),
        }
        total = math.prod(tests.values())
        if not (math.isfinite(total) and total > 0.0):
            raise RuntimeError(f"effective tests per cell are invalid: {tests}")
        return tests, total

    solution = _fixed_point(tests_at, pfa_per_cell, looks)
    if solution is None:
        # Each FFT axis counts at most ``padding`` tests, a beam set at most
        # its beam count.
        most_tests = (
            (1.0 if range_axis is None else range_axis.padding)
            * (1.0 if doppler_axis is None else doppler_axis.padding)
            * (1.0 if weights is None else float(weights.shape[0]))
        )
        threshold = _bracketed_threshold(tests_at, pfa_per_cell, looks, most_tests)
        solution = tests_at(threshold)
    tests, total = solution

    budget = FalseAlarmBudget(
        pfa_per_test=pfa_per_cell / total,
        looks=looks,
        pfa_per_cell=pfa_per_cell,
        tests=tests,
    )
    _BUDGET_CACHE[key] = budget
    return replace(budget, tests=dict(tests))


_BUDGET_CACHE: dict[tuple[object, ...], FalseAlarmBudget] = {}


def _fixed_point(
    tests_at: _TestCount, pfa_per_cell: float, looks: int
) -> tuple[dict[str, float], float] | None:
    """Iterate ``T = Q^-1(looks, pfa_per_cell / tests(T))``; None if it fails.

    The iteration is stable only where the false detections fall with the
    threshold, so a converged result is on that branch.
    """
    threshold = detection_threshold(looks, pfa_per_cell)
    for _ in range(_MAX_ITERATIONS):
        tests, total = tests_at(threshold)
        pfa_per_test = pfa_per_cell / total
        if not pfa_per_test < 1.0:
            return None
        updated = detection_threshold(looks, pfa_per_test)
        if abs(updated - threshold) <= 1.0e-9 * updated:
            return tests, total
        threshold = updated
    return None


def _bracketed_threshold(
    tests_at: _TestCount, pfa_per_cell: float, looks: int, most_tests: float
) -> float:
    """Solve for the threshold on the branch where false detections fall with it.

    At ``Q^-1(looks, pfa_per_cell / most_tests)`` the false detections per
    cell are at most ``pfa_per_cell``.  If they are below it already at the
    single-test threshold, step down until they reach it; if they stop rising
    first, the value is beyond the model's largest.
    """

    def excess(threshold: float) -> float:
        rate = tests_at(threshold)[1] * float(gammaincc(looks, threshold))
        return math.log(rate / pfa_per_cell)

    lower = detection_threshold(looks, pfa_per_cell)
    upper = detection_threshold(looks, pfa_per_cell / most_tests)
    current = excess(lower)
    if current < 0.0:
        step = max(0.05 * lower, 0.05)
        while True:
            candidate = lower - step
            if candidate <= 0.0:
                raise ValueError(_TOO_LARGE)
            value = excess(candidate)
            if value >= 0.0:
                lower, upper = candidate, lower
                break
            if value <= current:
                raise ValueError(_TOO_LARGE)
            lower, current = candidate, value
    return float(brentq(excess, lower, upper, xtol=1.0e-12))


def _check_looks(looks: int) -> None:
    if looks < 1:
        raise ValueError("looks must be >= 1")


def _unit_rows(beam_weights: npt.ArrayLike) -> npt.NDArray[np.complex128]:
    weights = np.asarray(beam_weights, dtype=np.complex128)
    if weights.ndim != 2 or weights.shape[0] < 1 or weights.shape[1] < 1:
        raise ValueError("beam_weights must have shape (beams, channels)")
    norms = np.linalg.norm(weights, axis=1, keepdims=True)
    if not np.all(np.isfinite(weights)) or np.any(norms == 0.0):
        raise ValueError("beam weights must be finite and nonzero")
    return np.asarray(weights / norms, dtype=np.complex128)


@lru_cache(maxsize=64)
def _peak_levels(axis: FftAxis, looks: int) -> npt.NDArray[np.float64] | None:
    """Centre power above which the centre bin is a peak, one per sample.

    ``None`` if the neighbours are perfectly correlated with the centre.
    """
    step = 1.0 / axis.padding
    lags = (np.arange(3)[:, None] - np.arange(3)[None, :]).ravel() * step
    # E[X_j X_k*] for the bins j, k = -1, 0, +1 (rows 0, 1, 2).
    cov = window_correlation(axis.window, axis.length, lags).reshape(3, 3)
    neighbours = [0, 2]
    gain = cov[neighbours, 1]  # E[X_i X_0*] / E[|X_0|^2], i = -1, +1
    spread = 1.0 - np.abs(gain) ** 2
    if np.min(spread) <= _DEGENERATE_SPREAD:
        return None
    residual = cov[np.ix_(neighbours, neighbours)] - np.outer(gain, gain.conj())
    root = hermitian_sqrt(residual)

    rng = np.random.default_rng(_FFT_SEED)
    cross = np.zeros((_FFT_SAMPLES, 2))
    energy = np.zeros((_FFT_SAMPLES, 2))
    for look in range(looks):
        white = (
            rng.standard_normal((_FFT_SAMPLES, 2))
            + 1j * rng.standard_normal((_FFT_SAMPLES, 2))
        ) / np.sqrt(2.0)
        residual_look = white @ root.T
        if look == 0:
            cross = np.real(gain.conj() * residual_look)
        energy += np.abs(residual_look) ** 2
    # The positive root, in the form without cancellation for either sign of
    # ``cross``: (cross + r) / spread = energy / (r - cross).
    radical = np.sqrt(cross**2 + spread * energy)
    rising = cross >= 0.0
    positive_root = np.empty_like(radical)
    positive_root[rising] = (cross + radical)[rising] / np.broadcast_to(
        spread, radical.shape
    )[rising]
    positive_root[~rising] = energy[~rising] / (radical - cross)[~rising]
    levels = np.asarray(np.max(positive_root**2, axis=1), dtype=float)
    levels.flags.writeable = False
    return levels


def hermitian_sqrt(matrix: npt.ArrayLike) -> npt.NDArray[np.complex128]:
    """Principal square root of a Hermitian positive semi-definite matrix.

    ``S`` with ``S @ S == matrix`` and ``S`` Hermitian.  Unlike the factor
    ``V sqrt(L)`` from an eigendecomposition, it does not depend on the
    eigenvector phases or bases that a LAPACK implementation chooses, so seeded
    samples ``white @ S.T`` are the same on every platform.  Negative
    eigenvalues from rounding are clipped to zero.
    """
    eigenvalues, eigenvectors = np.linalg.eigh(np.asarray(matrix, dtype=complex))
    scaled = eigenvectors * np.sqrt(np.clip(eigenvalues, 0.0, None))
    return np.asarray(scaled @ eigenvectors.conj().T, dtype=np.complex128)


def _beam_set_tests(
    weights: npt.NDArray[np.complex128], threshold: float, looks: int
) -> float:
    beam_count, channel_count = weights.shape
    if beam_count == 1:
        return 1.0
    gram = weights.conj() @ weights.T  # gram[j, k] = w_j^H w_k
    tail = float(gammaincc(looks, threshold))
    rng = np.random.default_rng(_BEAM_SEED)
    inverse_count_sum = 0.0
    for start in range(0, _BEAM_SAMPLES, _BEAM_CHUNK):
        count = min(_BEAM_CHUNK, _BEAM_SAMPLES - start)
        rows = np.arange(count)
        beam = rng.integers(beam_count, size=count)
        # Beam ``beam`` exceeds the threshold: its power over the looks is a
        # Gamma(looks) variable conditioned above it, in a uniform direction.
        power = gammainccinv(looks, rng.random(count) * tail)
        direction = rng.standard_normal((count, looks)) + 1j * rng.standard_normal(
            (count, looks)
        )
        direction *= np.sqrt(power)[:, None] / np.linalg.norm(
            direction, axis=1, keepdims=True
        )
        # The rest of the noise is white; replace its component along the
        # chosen beam by ``direction``.
        noise = (
            rng.standard_normal((count, channel_count, looks))
            + 1j * rng.standard_normal((count, channel_count, looks))
        ) / np.sqrt(2.0)
        outputs = weights.conj() @ noise  # (count, beams, looks)
        along = direction - outputs[rows, beam, :]
        outputs += gram[:, beam].T[:, :, None] * along[:, None, :]
        beam_power = np.sum(np.abs(outputs) ** 2, axis=2)
        beam_power[rows, beam] = np.inf
        inverse_count_sum += float(np.sum(1.0 / np.sum(beam_power > threshold, axis=1)))
    return float(beam_count * inverse_count_sum / _BEAM_SAMPLES)
