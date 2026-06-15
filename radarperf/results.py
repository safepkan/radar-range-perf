"""Result type for a single range-equation evaluation.

:class:`LinkBudget` carries the headline figures (SNR, SCR, SINR) plus an
itemised breakdown of every term that went into them, so a user can see
exactly where the dBs came from -- which is most of the value of a tool like
this during design reviews.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .geometry import Geometry


@dataclass(frozen=True)
class LinkBudget:
    """Outcome of evaluating the range equation at one geometry."""

    geometry: Geometry
    snr_db: float
    sinr_db: float
    scr_db: float
    signal_power_dbm: float
    noise_power_dbm: float
    clutter_to_noise_db: float
    coherent_gain_db: float
    processing_loss_db: float
    path_loss_db: float
    n_noncoherent: int
    n_collapsing: int
    rcs_m2: float
    clutter_rcs_m2: float
    breakdown_db: Mapping[str, float] = field(default_factory=dict)

    def __str__(self) -> str:
        lines = [
            f"Range:            {self.geometry.range_m:10.1f} m"
            f"  (az {self.geometry.azimuth_deg:+.1f} deg,"
            f" el {self.geometry.elevation_deg:+.1f} deg)",
            f"Signal (per smp): {self.signal_power_dbm:10.1f} dBm",
            f"Noise  (per smp): {self.noise_power_dbm:10.1f} dBm",
            f"Coherent gain:    {self.coherent_gain_db:10.1f} dB",
            f"Processing loss:  {self.processing_loss_db:10.1f} dB",
            f"Two-way path loss:{self.path_loss_db:10.1f} dB",
            f"Non-coh looks:    {self.n_noncoherent:10d}",
        ]
        if self.n_collapsing > 0:
            lines.append(f"Collapsing cells: {self.n_collapsing:10d}")
        lines.append(f"SNR:              {self.snr_db:10.1f} dB")
        if self.clutter_rcs_m2 > 0.0:
            lines += [
                f"Clutter-to-noise: {self.clutter_to_noise_db:10.1f} dB",
                f"SCR:              {self.scr_db:10.1f} dB",
                f"SINR:             {self.sinr_db:10.1f} dB",
            ]
        return "\n".join(lines)
