"""Detection statistics: single-scan Pd and multi-scan acquisition.

The forward model is a square-law detector integrating ``n_pulses`` looks
non-coherently, for Swerling cases 0-4 (5 is treated as 0).  The closed forms
used here were cross-checked against Monte-Carlo simulation:

* Swerling 0/5 -- exact, via the non-central chi-square survival function.
* Swerling 1, 2 -- exact closed forms.
* Swerling 3 -- Gauss-Laguerre quadrature of the Swerling-0 result over the
  chi-square(4) RCS distribution (slow fluctuation).
* Swerling 4 -- exact closed form derived from the per-pulse Laplace transform.

For a single coherent FMCW range-Doppler-angle cell, ``n_pulses = 1`` and the
per-pulse SNR is simply the integrated SNR from the link budget.
"""

from __future__ import annotations

from typing import Sequence, Union, cast

import numpy as np
import numpy.typing as npt
from scipy.optimize import brentq
from scipy.special import comb, gammainc, gammaincc, gammainccinv
from scipy.stats import ncx2

from .units import db_to_linear

FloatOrArray = Union[float, npt.NDArray[np.float64]]

# Gauss-Laguerre nodes for E[f] over a Gamma(2, 1) variable (Swerling 3).
_GL_X, _GL_W = np.polynomial.laguerre.laggauss(48)
_GL_WEIGHTS = _GL_W * _GL_X  # weight x * exp(-x): turns Gamma(1,1) into Gamma(2,1)


def detection_threshold(n_pulses: int, pfa: float) -> float:
    """Square-law detector threshold (in noise-power units) for a given Pfa."""
    if n_pulses < 1:
        raise ValueError("n_pulses must be >= 1")
    if not 0.0 < pfa < 1.0:
        raise ValueError("pfa must be in (0, 1)")
    return float(gammainccinv(n_pulses, pfa))


def probability_of_detection(
    snr_db: FloatOrArray,
    pfa: float,
    swerling: int = 1,
    n_pulses: int = 1,
    n_collapsing: int = 0,
) -> FloatOrArray:
    """Probability of detection for per-look ``snr_db`` and ``pfa``.

    ``snr_db`` is the per-look SNR in dB and may be a scalar or array.
    ``n_pulses`` is the number of *signal-bearing* looks integrated
    non-coherently; ``n_collapsing`` is the number of additional noise-only
    cells integrated alongside them (the collapsing-loss case, e.g. empty DDMA
    subbands).  The detection threshold is set for the total cell count while
    only the signal looks contribute energy.

    For collapsing (``n_collapsing > 0``) the spatial looks are assumed to share
    a single fluctuation realisation (correct for simultaneous array channels in
    one CPI), so only the correlated cases Swerling 0/1/3 are supported; the
    independent cases 2/4 raise :class:`NotImplementedError`.
    """
    scalar_input = np.isscalar(snr_db)
    snr = np.atleast_1d(db_to_linear(np.asarray(snr_db, dtype=float)))
    n_total = n_pulses + n_collapsing
    thr = detection_threshold(n_total, pfa)
    pd = _pd_linear(snr, thr, swerling, n_signal=n_pulses, n_total=n_total)
    pd = np.clip(pd, 0.0, 1.0)
    return float(pd[0]) if scalar_input else pd


def _pd_linear(
    snr: npt.NDArray[np.float64],
    thr: float,
    swerling: int,
    n_signal: int,
    n_total: int,
) -> npt.NDArray[np.float64]:
    case = 0 if swerling == 5 else swerling
    collapsing = n_total != n_signal
    if case == 0:
        return _pd_sw0(snr, thr, n_signal, n_total)
    if case == 1:
        if collapsing:
            return _pd_sw_correlated(snr, thr, n_signal, n_total, _GL_W)
        return _pd_sw1(snr, thr, n_signal)
    if case == 2:
        if collapsing:
            raise NotImplementedError(
                "Swerling 2 with collapsing is not supported: simultaneous "
                "array looks share one fluctuation realisation, so use "
                "Swerling 1 (or 3) for spatial non-coherent integration."
            )
        return _pd_sw2(snr, thr, n_signal)
    if case == 3:
        return _pd_sw3(snr, thr, n_signal, n_total)
    if case == 4:
        if collapsing:
            raise NotImplementedError(
                "Swerling 4 with collapsing is not supported: simultaneous "
                "array looks share one fluctuation realisation, so use "
                "Swerling 3 (or 1) for spatial non-coherent integration."
            )
        return _pd_sw4(snr, thr, n_signal)
    raise ValueError("swerling must be one of 0,1,2,3,4,5")


def _pd_sw0(
    snr: npt.NDArray[np.float64], thr: float, n_signal: int, n_total: int
) -> npt.NDArray[np.float64]:
    nc = 2.0 * n_signal * snr
    return cast(npt.NDArray[np.float64], ncx2.sf(2.0 * thr, 2 * n_total, nc))


def _pd_sw1(
    snr: npt.NDArray[np.float64], thr: float, n: int
) -> npt.NDArray[np.float64]:
    if n == 1:
        return np.exp(-thr / (1.0 + snr))
    a = 1.0 + 1.0 / (n * snr)
    result = (
        1.0
        - gammainc(n - 1, thr)
        + a ** (n - 1) * gammainc(n - 1, thr / a) * np.exp(-thr / (1.0 + n * snr))
    )
    return cast(npt.NDArray[np.float64], result)


def _pd_sw2(
    snr: npt.NDArray[np.float64], thr: float, n: int
) -> npt.NDArray[np.float64]:
    return cast(npt.NDArray[np.float64], gammaincc(n, thr / (1.0 + snr)))


def _pd_sw3(
    snr: npt.NDArray[np.float64], thr: float, n_signal: int, n_total: int
) -> npt.NDArray[np.float64]:
    # Gauss-Laguerre quadrature over the chi-square(4) RCS power, g ~ Gamma(2, 1):
    # instantaneous per-cell SNR p = (snr / 2) * g, shared across signal cells.
    out = np.zeros_like(snr)
    for node, weight in zip(_GL_X, _GL_WEIGHTS):
        instantaneous = node * (snr / 2.0)
        nc = 2.0 * n_signal * instantaneous
        out += weight * ncx2.sf(2.0 * thr, 2 * n_total, nc)
    return out


def _pd_sw_correlated(
    snr: npt.NDArray[np.float64],
    thr: float,
    n_signal: int,
    n_total: int,
    weights: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Swerling 1 with collapsing: average the Swerling-0 result over the shared
    Rayleigh power g ~ Exp(1) via Gauss-Laguerre quadrature."""
    out = np.zeros_like(snr)
    for node, weight in zip(_GL_X, weights):
        nc = 2.0 * n_signal * snr * node
        out += weight * ncx2.sf(2.0 * thr, 2 * n_total, nc)
    return out


def _pd_sw4(
    snr: npt.NDArray[np.float64], thr: float, n: int
) -> npt.NDArray[np.float64]:
    b = snr / 2.0
    a = 1.0 + b
    total = np.zeros_like(snr)
    for k in range(n + 1):
        total += comb(n, k) * b**k * gammaincc(n + k, thr / a)
    return a ** (-n) * total


def required_snr_db(
    pd: float,
    pfa: float,
    swerling: int = 1,
    n_pulses: int = 1,
    *,
    bracket_db: tuple[float, float] = (-30.0, 80.0),
) -> float:
    """Per-pulse SNR [dB] needed to achieve ``pd`` at ``pfa`` (exact inversion)."""
    if not 0.0 < pd < 1.0:
        raise ValueError("pd must be in (0, 1)")

    def deficit(snr_db: float) -> float:
        return float(probability_of_detection(snr_db, pfa, swerling, n_pulses)) - pd

    lo, hi = bracket_db
    if deficit(lo) > 0.0:
        return lo
    if deficit(hi) < 0.0:
        raise ValueError("required SNR exceeds bracket; widen bracket_db")
    return float(brentq(deficit, lo, hi, xtol=1e-4))


def albersheim_required_snr_db(pd: float, pfa: float, n_pulses: int = 1) -> float:
    """Albersheim's approximation for a non-fluctuating (Swerling 0) target.

    Valid roughly for 0.1 <= Pd <= 0.9 and 1e-7 <= Pfa <= 1e-3.
    """
    a = np.log(0.62 / pfa)
    b = np.log(pd / (1.0 - pd))
    n = n_pulses
    return float(
        -5.0 * np.log10(n)
        + (6.2 + 4.54 / np.sqrt(n + 0.44)) * np.log10(a + 0.12 * a * b + 1.7 * b)
    )


def shnidman_required_snr_db(
    pd: float, pfa: float, n_pulses: int = 1, swerling: int = 1
) -> float:
    """Shnidman's approximation for required per-pulse SNR, Swerling 0-4."""
    n = n_pulses
    k_map = {0: np.inf, 5: np.inf, 1: 1.0, 2: float(n), 3: 2.0, 4: 2.0 * n}
    k = k_map[swerling]

    alpha = 0.0 if n < 40 else 0.25
    eta = np.sqrt(-0.8 * np.log(4.0 * pfa * (1.0 - pfa))) + np.sign(pd - 0.5) * np.sqrt(
        -0.8 * np.log(4.0 * pd * (1.0 - pd))
    )
    x_inf = eta * (eta + 2.0 * np.sqrt(n / 2.0 + (alpha - 0.25)))

    if np.isinf(k):
        correction_db = 0.0
    else:
        c1 = (((17.7006 * pd - 18.4496) * pd + 14.5339) * pd - 3.525) / k
        c2 = (1.0 / k) * (
            np.exp(27.31 * pd - 25.14)
            + (pd - 0.8) * (0.7 * np.log(1.0e-5 / pfa) + (2.0 * n - 20.0) / 80.0)
        )
        correction_db = c1 if pd <= 0.872 else c1 + c2

    correction = 10.0 ** (correction_db / 10.0)
    snr_per_pulse = correction * x_inf / n
    return float(10.0 * np.log10(snr_per_pulse))


def cumulative_pd(pd_per_scan: Sequence[float]) -> npt.NDArray[np.float64]:
    """Cumulative probability of *at least one* detection by each scan."""
    miss = 1.0 - np.asarray(pd_per_scan, dtype=float)
    return cast(npt.NDArray[np.float64], 1.0 - np.cumprod(miss))


def probability_of_acquisition_mofn(
    pd_per_scan: Sequence[float], m: int, n: int
) -> npt.NDArray[np.float64]:
    """Probability a track is confirmed by each scan under a sliding M-of-N rule.

    Returns, for each scan index, the probability that at least ``m`` detections
    have occurred within some window of the last ``n`` scans up to and including
    that scan (first-crossing / cumulative).  Exact, via a DP over the pattern of
    the most recent ``n - 1`` looks.
    """
    if not 1 <= m <= n:
        raise ValueError("require 1 <= m <= n")
    pd = np.asarray(pd_per_scan, dtype=float)

    # State: tuple of the last (n-1) detection outcomes (oldest first).
    from itertools import product

    states = list(product((0, 1), repeat=n - 1)) if n > 1 else [()]
    index = {s: i for i, s in enumerate(states)}
    prob = np.zeros(len(states))
    prob[index[tuple([0] * (n - 1))]] = 1.0  # start with empty history

    confirmed = np.zeros(len(pd))
    confirmed_mass = 0.0
    for scan, p_det in enumerate(pd):
        new_prob = np.zeros_like(prob)
        newly_confirmed = 0.0
        for state, i in index.items():
            mass = prob[i]
            if mass == 0.0:
                continue
            for outcome, p_out in ((1, p_det), (0, 1.0 - p_det)):
                window = state + (outcome,)
                if sum(window) >= m:
                    newly_confirmed += mass * p_out
                else:
                    next_state = window[1:] if n > 1 else ()
                    new_prob[index[next_state]] += mass * p_out
        prob = new_prob
        confirmed_mass += newly_confirmed
        confirmed[scan] = confirmed_mass
    return confirmed
