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
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .detection import probability_of_detection
from .environment import FreeSpace
from .geometry import Geometry
from .protocols import Antenna, Environment, Frontend, Processing, Target, Waveform
from .results import LinkBudget
from .units import (
    BOLTZMANN,
    REFERENCE_TEMPERATURE,
    db_to_linear,
    linear_to_db,
    watt_to_dbm,
)

_FOUR_PI_CUBED = (4.0 * math.pi) ** 3


@dataclass(frozen=True)
class Radar:
    """A composed radar configuration ready to be evaluated."""

    frontend: Frontend
    waveform: Waveform
    processing: Processing
    tx_antenna: Antenna
    rx_antenna: Antenna
    default_pfa: float = 1.0e-6

    def link_budget(
        self,
        target: Target,
        geometry: Geometry,
        environment: Environment = FreeSpace(),
    ) -> LinkBudget:
        """Evaluate SNR / SCR / SINR (with breakdown) at one geometry."""
        wf = self.waveform
        lam = wf.wavelength_m
        az, el = geometry.azimuth_deg, geometry.elevation_deg

        gt_db = self.tx_antenna.gain_dbi(az, el)
        gr_db = self.rx_antenna.gain_dbi(az, el)
        gt = float(db_to_linear(gt_db))
        gr = float(db_to_linear(gr_db))

        pt = self.frontend.tx_power_w
        sigma = target.rcs_m2(geometry)
        rng = geometry.range_m
        path_loss_db = environment.two_way_loss_db(geometry, wf)
        l_path = float(db_to_linear(path_loss_db))

        noise_factor = float(db_to_linear(self.frontend.noise_figure_db))
        noise_per_sample_w = (
            BOLTZMANN * REFERENCE_TEMPERATURE * noise_factor * wf.sample_rate_hz
        )

        common = pt * gt * gr * lam**2 / (_FOUR_PI_CUBED * rng**4 * l_path)
        signal_per_sample_w = common * sigma
        snr_sample = signal_per_sample_w / noise_per_sample_w

        budget = self.processing.budget(wf, self.frontend.n_tx, self.frontend.n_rx)
        proc_loss_db = budget.total_loss_db
        snr_db = (
            float(linear_to_db(snr_sample)) + budget.coherent_gain_db - proc_loss_db
        )

        sigma_c = environment.clutter_rcs_m2(geometry, wf, self.rx_antenna)
        if sigma_c > 0.0:
            clutter_per_sample_w = common * sigma_c
            cnr_sample = clutter_per_sample_w / noise_per_sample_w
            cnr_db = (
                float(linear_to_db(cnr_sample)) + budget.coherent_gain_db - proc_loss_db
            )
            scr_db = snr_db - cnr_db
            sinr_db = float(
                linear_to_db(db_to_linear(snr_db) / (1.0 + db_to_linear(cnr_db)))
            )
        else:
            cnr_db = float("-inf")
            scr_db = float("inf")
            sinr_db = snr_db

        breakdown = {
            "tx_power_dbm": float(watt_to_dbm(pt)),
            "tx_gain_dbi": gt_db,
            "rx_gain_dbi": gr_db,
            "rcs_dbsm": float(linear_to_db(sigma)),
            "coherent_gain_db": budget.coherent_gain_db,
            "processing_loss_db": proc_loss_db,
            "path_loss_db": path_loss_db,
        }

        return LinkBudget(
            geometry=geometry,
            snr_db=snr_db,
            sinr_db=sinr_db,
            scr_db=scr_db,
            signal_power_dbm=float(watt_to_dbm(signal_per_sample_w)),
            noise_power_dbm=float(watt_to_dbm(noise_per_sample_w)),
            clutter_to_noise_db=cnr_db,
            coherent_gain_db=budget.coherent_gain_db,
            processing_loss_db=proc_loss_db,
            path_loss_db=path_loss_db,
            n_noncoherent=budget.n_noncoherent,
            n_collapsing=budget.n_collapsing,
            rcs_m2=sigma,
            clutter_rcs_m2=sigma_c,
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
