"""Result type for a single range-equation evaluation.

:class:`LinkBudget` carries the headline figures (SNR, SCR, SINR) plus an
itemised breakdown of every term that went into them, so a user can see
exactly where the dBs came from -- which is most of the value of a tool like
this during design reviews.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .false_alarms import FalseAlarmBudget
from .geometry import Geometry


@dataclass(frozen=True)
class LinkBudget:
    """Outcome of evaluating the range equation at one geometry.

    Signal and noise powers are per sample at the front-end's RF reference
    plane, so ``signal_power_dbm`` already includes the path and system losses.
    ``system_loss_db`` is the sum of the signal-path items in
    ``system_losses_db``; that mapping also lists the noise-figure derating,
    which acts on ``noise_power_dbm`` instead.  Both itemised mappings keep
    zero-valued terms, so an omitted term shows as an explicit zero.

    ``false_alarms`` is the threshold side: the Pfa per cell, the effective
    tests per axis and the per-test Pfa the detector uses.  Its threshold
    increase is not part of ``snr_db``; it acts through the per-test Pfa.
    """

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
    system_loss_db: float
    n_noncoherent: int
    n_collapsing: int
    rcs_m2: float
    clutter_rcs_m2: float
    breakdown_db: Mapping[str, float] = field(default_factory=dict)
    processing_losses_db: Mapping[str, float] = field(default_factory=dict)
    system_losses_db: Mapping[str, float] = field(default_factory=dict)
    false_alarms: FalseAlarmBudget | None = None

    def __str__(self) -> str:
        system_items = dict(self.system_losses_db)
        nf_derating = system_items.pop("noise_figure_derating", 0.0)
        lines = [
            f"Range:            {self.geometry.range_m:10.1f} m"
            f"  (az {self.geometry.azimuth_deg:+.1f} deg,"
            f" el {self.geometry.elevation_deg:+.1f} deg)",
            f"Signal (per smp): {self.signal_power_dbm:10.1f} dBm",
            f"Noise  (per smp): {self.noise_power_dbm:10.1f} dBm",
            f"Coherent gain:    {self.coherent_gain_db:10.1f} dB",
            f"Processing loss:  {self.processing_loss_db:10.1f} dB",
            *_item_lines(self.processing_losses_db),
            *_false_alarm_lines(self.false_alarms),
            f"Two-way path loss:{self.path_loss_db:10.1f} dB",
            f"System loss:      {self.system_loss_db:10.1f} dB",
            *_item_lines(system_items),
            f"NF derating:      {nf_derating:10.1f} dB",
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


_ITEM_LABELS = {
    "cfar": "CFAR",
    "mimo": "MIMO",
    "tx_power_derating": "TX power derating",
    "tx_feed": "TX feed",
    "tx_antenna": "TX antenna",
    "radome_two_way": "radome (two-way)",
    "rx_antenna": "RX antenna",
    "rx_feed": "RX feed",
}


def _false_alarm_lines(budget: FalseAlarmBudget | None) -> list[str]:
    """The Pfa per cell, its effective tests and the per-test threshold."""
    if budget is None:
        return []
    if budget.pfa_per_cell is None:
        return [f"Pfa per test:     {budget.pfa_per_test:10.1e}"]
    return [
        f"Pfa per cell:     {budget.pfa_per_cell:10.1e}",
        *(
            f"  {name + ' tests':<20}{value:6.2f}"
            for name, value in budget.tests.items()
        ),
        f"  {'Pfa per test':<20}{budget.pfa_per_test:.1e}",
        f"  {'threshold increase':<20}{budget.threshold_increase_db:6.2f} dB",
    ]


def _item_lines(items: Mapping[str, float]) -> list[str]:
    """Indented ``label  value dB`` lines for an itemised loss mapping."""
    return [
        f"  {_ITEM_LABELS.get(name, name.replace('_', ' ')):<20}{value:6.2f} dB"
        for name, value in items.items()
    ]
