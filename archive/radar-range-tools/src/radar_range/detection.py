"""Detection-probability utilities."""

from __future__ import annotations

from typing import Literal

import numpy as np
from scipy.integrate import quad
from scipy.special import roots_laguerre
from scipy.stats import binom, chi2, gamma, ncx2

from radar_range.types import ArrayLikeFloat, FloatArray, as_float_array

FluctuationModel = Literal["nonfluctuating", "swerling1", "swerling2"]


def square_law_threshold_chi2(pfa: float, noncoherent_looks: int = 1) -> float:
    """Return the chi-square-domain threshold for a square-law detector.

    ``noncoherent_looks`` is the number of independent complex noise-bearing
    square-law terms included in the detector statistic. The statistic is
    represented in chi-square units with ``2*noncoherent_looks`` degrees of
    freedom under noise alone. For one complex matched-filter output, dividing
    the returned threshold by two gives the usual exponential threshold
    ``-log(pfa)``.
    """

    _validate_pfa(pfa)
    _validate_look_counts(noncoherent_looks, None)
    return float(chi2.isf(pfa, 2 * noncoherent_looks))


def pd_nonfluctuating(
    snr_linear: ArrayLikeFloat,
    pfa: float,
    noncoherent_looks: int = 1,
    signal_looks: int | None = None,
) -> FloatArray:
    """Single-scan Pd for a nonfluctuating target.

    ``snr_linear`` is the total target signal energy divided by single-look
    noise energy after coherent processing and any noncoherent signal-energy
    summation. ``noncoherent_looks`` controls the detector threshold and degrees
    of freedom. ``signal_looks`` is accepted for API consistency and validation;
    the nonfluctuating noncentral chi-square result only needs total SNR.
    """

    _validate_look_counts(noncoherent_looks, signal_looks)
    snr = np.maximum(as_float_array(snr_linear), 0.0)
    threshold = square_law_threshold_chi2(pfa, noncoherent_looks)
    noncentrality = 2.0 * snr
    return np.asarray(
        ncx2.sf(threshold, 2 * noncoherent_looks, noncentrality),
        dtype=float,
    )


def pd_swerling1(
    snr_linear: ArrayLikeFloat,
    pfa: float,
    noncoherent_looks: int = 1,
    signal_looks: int | None = None,
    quadrature_order: int = 32,
) -> FloatArray:
    """Single-scan Pd for Swerling-I fluctuations.

    Swerling-I is modeled as one exponential RCS draw that is constant over the
    noncoherent looks in the scan. The average over the exponential RCS is done
    with Gauss-Laguerre quadrature. ``signal_looks`` is accepted for API
    consistency and validation; for this model the common RCS draw scales the
    total SNR directly.
    """

    if quadrature_order < 4:
        raise ValueError("quadrature_order must be at least four")
    _validate_look_counts(noncoherent_looks, signal_looks)
    snr = np.maximum(as_float_array(snr_linear), 0.0)
    nodes, weights = roots_laguerre(quadrature_order)
    result = np.zeros_like(snr, dtype=float)
    for node, weight in zip(nodes, weights):
        result += float(weight) * pd_nonfluctuating(
            snr * float(node),
            pfa,
            noncoherent_looks,
            signal_looks,
        )
    return result


def pd_swerling2(
    snr_linear: ArrayLikeFloat,
    pfa: float,
    noncoherent_looks: int = 1,
    signal_looks: int | None = None,
) -> FloatArray:
    """Single-scan Pd for Swerling-II fluctuations.

    Swerling-II is modeled as independent exponential RCS draws in each
    target-bearing noncoherent look. ``noncoherent_looks`` is the total number of
    noise-bearing looks included in the detector threshold. ``signal_looks`` is
    the number of those looks that contain target signal; it defaults to
    ``noncoherent_looks``.

    When ``signal_looks == noncoherent_looks``, this reduces to the usual scaled
    central chi-square result. When extra noise-only looks are present, such as
    empty DDMA subbands that are still summed by the detector, the survival
    probability is computed as a sum of two independent gamma variates.
    """

    target_looks = _validate_look_counts(noncoherent_looks, signal_looks)
    snr = np.maximum(as_float_array(snr_linear), 0.0)
    threshold_chi2 = square_law_threshold_chi2(pfa, noncoherent_looks)

    if target_looks == 0:
        return np.full_like(snr, pfa, dtype=float)

    snr_per_signal_look = snr / float(target_looks)
    if target_looks == noncoherent_looks:
        return np.asarray(
            chi2.sf(
                threshold_chi2 / (1.0 + snr_per_signal_look),
                2 * noncoherent_looks,
            ),
            dtype=float,
        )

    threshold_power = threshold_chi2 / 2.0
    noise_only_looks = noncoherent_looks - target_looks
    result = np.empty_like(snr_per_signal_look, dtype=float)
    for index, snr_per_look in np.ndenumerate(snr_per_signal_look):
        result[index] = _gamma_sum_survival(
            threshold_power,
            signal_shape=target_looks,
            signal_scale=1.0 + float(snr_per_look),
            noise_shape=noise_only_looks,
        )
    return result


def pd_from_snr(
    snr_linear: ArrayLikeFloat,
    pfa: float,
    fluctuation_model: FluctuationModel = "nonfluctuating",
    noncoherent_looks: int = 1,
    signal_looks: int | None = None,
) -> FloatArray:
    """Dispatch helper for the supported single-scan Pd models."""

    if fluctuation_model == "nonfluctuating":
        return pd_nonfluctuating(snr_linear, pfa, noncoherent_looks, signal_looks)
    if fluctuation_model == "swerling1":
        return pd_swerling1(snr_linear, pfa, noncoherent_looks, signal_looks)
    if fluctuation_model == "swerling2":
        return pd_swerling2(snr_linear, pfa, noncoherent_looks, signal_looks)
    raise ValueError(f"Unsupported fluctuation model: {fluctuation_model}")


def probability_m_of_n(pd: ArrayLikeFloat, m: int, n: int) -> FloatArray:
    """Probability of at least ``m`` detections in ``n`` independent scans."""

    if n < 1:
        raise ValueError("n must be at least one")
    if m < 1 or m > n:
        raise ValueError("m must satisfy 1 <= m <= n")
    pd_array = np.clip(as_float_array(pd), 0.0, 1.0)
    return np.asarray(binom.sf(m - 1, n, pd_array), dtype=float)


def _gamma_sum_survival(
    threshold: float,
    *,
    signal_shape: int,
    signal_scale: float,
    noise_shape: int,
) -> float:
    """Survival of Gamma(signal_shape, signal_scale)+Gamma(noise_shape, 1)."""

    if threshold <= 0.0:
        return 1.0
    if signal_shape < 0 or noise_shape < 0:
        raise ValueError("gamma shapes must be non-negative")
    if signal_scale <= 0.0:
        raise ValueError("signal_scale must be positive")
    if signal_shape == 0:
        return float(gamma.sf(threshold, noise_shape, scale=1.0))
    if noise_shape == 0:
        return float(gamma.sf(threshold, signal_shape, scale=signal_scale))
    if np.isclose(signal_scale, 1.0, rtol=1.0e-12, atol=1.0e-12):
        return float(gamma.sf(threshold, signal_shape + noise_shape, scale=1.0))

    noise_tail = float(gamma.sf(threshold, noise_shape, scale=1.0))

    def integrand(noise_power: float) -> float:
        return float(
            gamma.pdf(noise_power, noise_shape, scale=1.0)
            * gamma.sf(
                threshold - noise_power,
                signal_shape,
                scale=signal_scale,
            )
        )

    integral, _ = quad(
        integrand,
        0.0,
        threshold,
        epsabs=1.0e-12,
        epsrel=1.0e-10,
        limit=100,
    )
    return float(np.clip(noise_tail + integral, 0.0, 1.0))


def _validate_pfa(pfa: float) -> None:
    if pfa <= 0.0 or pfa >= 1.0:
        raise ValueError("pfa must be between zero and one")


def _validate_look_counts(
    noncoherent_looks: int,
    signal_looks: int | None,
) -> int:
    if noncoherent_looks < 1:
        raise ValueError("noncoherent_looks must be at least one")
    resolved_signal_looks = (
        noncoherent_looks if signal_looks is None else signal_looks
    )
    if resolved_signal_looks < 0 or resolved_signal_looks > noncoherent_looks:
        raise ValueError(
            "signal_looks must satisfy 0 <= signal_looks <= noncoherent_looks"
        )
    return resolved_signal_looks
