"""The range-equation engine.

:class:`Radar` bundles a front-end, transmit/receive antennas, a waveform and a
processing chain.  Given a target, a geometry and an environment it returns a
:class:`~radarperf.results.LinkBudget` (SNR/SCR/SINR with full breakdown) and,
on top of that, a single-scan probability of detection.

The SNR is built in the unambiguous "single-sample SNR times dimensionless
integration gain" form of the FMCW radar equation::

    snr_sample = Pt G_t G_r lambda^2 sigma
                 / ((4 pi)^3 R^4 k T0 F f_s L_path)
    SNR        = snr_sample * coherent_gain / processing_losses

where the noise power per complex sample is ``k T0 F f_s`` (noise bandwidth
equal to the sample rate) and ``coherent_gain`` / losses come from the
processing model.  Antenna gains are element gains; coherent array gain is in
``coherent_gain``.

The core physics is computed once, vectorised, in :meth:`Radar._budget_terms`.
It broadcasts over the fields of the supplied :class:`~radarperf.geometry.Geometry`,
so a single scalar point and a whole sweep grid go through exactly the same
code.  :meth:`Radar.link_budget` wraps it for a single point (and builds the
itemised breakdown); :mod:`radarperf.sweeps` calls it once per array geometry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .detection import probability_of_detection
from .environment import FreeSpace
from .geometry import Geometry
from .protocols import Antenna, Environment, Frontend, Processing, Target, Waveform
from .results import LinkBudget
from .units import (
    BOLTZMANN,
    REFERENCE_TEMPERATURE,
    FloatOrArray,
    db_to_linear,
    linear_to_db,
    watt_to_dbm,
)

_FOUR_PI_CUBED = (4.0 * math.pi) ** 3


@dataclass(frozen=True)
class _BudgetTerms:
    """Vectorised range-equation outputs for a (possibly batched) geometry.

    The dB/power/RCS fields broadcast to the geometry shape; the integration
    figures are geometry-independent scalars.
    """

    snr_db: FloatOrArray
    sinr_db: FloatOrArray
    scr_db: FloatOrArray
    cnr_db: FloatOrArray
    signal_power_dbm: FloatOrArray
    noise_power_dbm: float
    tx_gain_dbi: FloatOrArray
    rx_gain_dbi: FloatOrArray
    rcs_m2: FloatOrArray
    clutter_rcs_m2: FloatOrArray
    path_loss_db: FloatOrArray
    coherent_gain_db: float
    processing_loss_db: float
    n_noncoherent: int
    n_collapsing: int


@dataclass(frozen=True)
class Radar:
    """A composed radar configuration ready to be evaluated."""

    frontend: Frontend
    waveform: Waveform
    processing: Processing
    tx_antenna: Antenna
    rx_antenna: Antenna
    default_pfa: float = 1.0e-6

    def _budget_terms(
        self,
        target: Target,
        geometry: Geometry,
        environment: Environment = FreeSpace(),
    ) -> _BudgetTerms:
        """Evaluate the range equation, broadcasting over the geometry."""
        wf = self.waveform
        lam = wf.wavelength_m

        gt_db = np.asarray(
            self.tx_antenna.gain_dbi(geometry.azimuth_deg, geometry.elevation_deg),
            dtype=float,
        )
        gr_db = np.asarray(
            self.rx_antenna.gain_dbi(geometry.azimuth_deg, geometry.elevation_deg),
            dtype=float,
        )
        gt = db_to_linear(gt_db)
        gr = db_to_linear(gr_db)

        pt = self.frontend.tx_power_w
        sigma = np.asarray(target.rcs_m2(geometry), dtype=float)
        rng = np.asarray(geometry.range_m, dtype=float)
        path_loss_db = np.asarray(
            environment.two_way_loss_db(geometry, wf), dtype=float
        )
        l_path = db_to_linear(path_loss_db)

        noise_factor = db_to_linear(self.frontend.noise_figure_db)
        noise_per_sample_w = (
            BOLTZMANN * REFERENCE_TEMPERATURE * noise_factor * wf.sample_rate_hz
        )

        common = pt * gt * gr * lam**2 / (_FOUR_PI_CUBED * rng**4 * l_path)
        signal_per_sample_w = common * sigma
        snr_sample = signal_per_sample_w / noise_per_sample_w

        budget = self.processing.budget(wf, self.frontend.n_tx, self.frontend.n_rx)
        proc_loss_db = budget.total_loss_db
        gain_minus_loss = budget.coherent_gain_db - proc_loss_db
        snr_db = linear_to_db(snr_sample) + gain_minus_loss

        sigma_c = np.asarray(
            environment.clutter_rcs_m2(geometry, wf, self.rx_antenna), dtype=float
        )
        has_clutter = sigma_c > 0.0
        cnr_sample = common * sigma_c / noise_per_sample_w
        cnr_db = np.where(
            has_clutter, linear_to_db(cnr_sample) + gain_minus_loss, -np.inf
        )
        scr_db = np.where(has_clutter, snr_db - cnr_db, np.inf)
        # snr - 10log10(1 + cnr_lin); db_to_linear(-inf) = 0 leaves sinr == snr.
        sinr_db = snr_db - linear_to_db(1.0 + db_to_linear(cnr_db))

        return _BudgetTerms(
            snr_db=snr_db,
            sinr_db=sinr_db,
            scr_db=scr_db,
            cnr_db=cnr_db,
            signal_power_dbm=watt_to_dbm(signal_per_sample_w),
            noise_power_dbm=float(watt_to_dbm(noise_per_sample_w)),
            tx_gain_dbi=gt_db,
            rx_gain_dbi=gr_db,
            rcs_m2=sigma,
            clutter_rcs_m2=sigma_c,
            path_loss_db=path_loss_db,
            coherent_gain_db=budget.coherent_gain_db,
            processing_loss_db=proc_loss_db,
            n_noncoherent=budget.n_noncoherent,
            n_collapsing=budget.n_collapsing,
        )

    def link_budget(
        self,
        target: Target,
        geometry: Geometry,
        environment: Environment = FreeSpace(),
    ) -> LinkBudget:
        """Evaluate SNR / SCR / SINR (with breakdown) at one geometry."""
        if not geometry.is_scalar:
            raise ValueError(
                "link_budget expects a single-point Geometry; use the helpers in "
                "radarperf.sweeps for array (batched) geometries."
            )
        t = self._budget_terms(target, geometry, environment)

        breakdown = {
            "tx_power_dbm": float(watt_to_dbm(self.frontend.tx_power_w)),
            "tx_gain_dbi": float(t.tx_gain_dbi),
            "rx_gain_dbi": float(t.rx_gain_dbi),
            "rcs_dbsm": float(linear_to_db(np.asarray(t.rcs_m2, dtype=float))),
            "coherent_gain_db": t.coherent_gain_db,
            "processing_loss_db": t.processing_loss_db,
            "path_loss_db": float(t.path_loss_db),
        }

        return LinkBudget(
            geometry=geometry,
            snr_db=float(t.snr_db),
            sinr_db=float(t.sinr_db),
            scr_db=float(t.scr_db),
            signal_power_dbm=float(t.signal_power_dbm),
            noise_power_dbm=t.noise_power_dbm,
            clutter_to_noise_db=float(t.cnr_db),
            coherent_gain_db=t.coherent_gain_db,
            processing_loss_db=t.processing_loss_db,
            path_loss_db=float(t.path_loss_db),
            n_noncoherent=t.n_noncoherent,
            n_collapsing=t.n_collapsing,
            rcs_m2=float(t.rcs_m2),
            clutter_rcs_m2=float(t.clutter_rcs_m2),
            breakdown_db=breakdown,
        )

    def probability_of_detection(
        self,
        target: Target,
        geometry: Geometry,
        environment: Environment = FreeSpace(),
        *,
        pfa: Optional[float] = None,
        swerling: Optional[int] = None,
        use_sinr: bool = True,
    ) -> float:
        """Single-scan Pd at one geometry.

        Uses the SINR (signal vs noise+clutter) by default; set
        ``use_sinr=False`` to detect against thermal noise only.  The Swerling
        case defaults to the target's, and ``n_pulses`` is the number of
        non-coherent looks reported by the processing model.
        """
        budget = self.link_budget(target, geometry, environment)
        metric_db = budget.sinr_db if use_sinr else budget.snr_db
        case = target.swerling if swerling is None else swerling
        return float(
            probability_of_detection(
                metric_db,
                self.default_pfa if pfa is None else pfa,
                swerling=case,
                n_pulses=budget.n_noncoherent,
                n_collapsing=budget.n_collapsing,
            )
        )
