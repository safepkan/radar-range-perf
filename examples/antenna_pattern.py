"""Plot the Huber+Suhner SENCITY antenna pattern cuts via radarperf.plotting.

Each row is one antenna; the columns are its azimuth and elevation cuts, with the
transmit and receive elements drawn as separate traces.  The datasheet's per-
channel ``Avg. TX``/``Avg. RX`` cuts are similar but not identical -- the toolbox
models them as distinct ``tx_antenna``/``rx_antenna`` rather than collapsing them
to one element.

Requires the plot extra (``pip install -e '.[plot]'``).  Opens an interactive
window via ``plt.show()``; under a non-interactive backend (e.g. CI with
``MPLBACKEND=Agg``) it saves a PNG to the temp directory instead.

Run with::

    python examples/antenna_pattern.py
"""

from __future__ import annotations

import os
import tempfile

import matplotlib.pyplot as plt

from radarperf import antenna
from radarperf.plotting import is_non_interactive_backend, plot_pattern_cuts

PRESETS = [antenna.sencity_this_ii, antenna.sencity_farad_iv]


def main() -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))

    for preset, (ax_az, ax_el) in zip(PRESETS, axes):
        pair = preset()
        plot_pattern_cuts(pair.tx, pair.rx, axes=(ax_az, ax_el), label=pair.name)
        ax_az.set_title(f"{pair.name} -- azimuth cut")
        ax_el.set_title(f"{pair.name} -- elevation cut")
        ax_az.set_ylim(-20.0, 20.0)
        ax_el.set_ylim(-20.0, 20.0)

    fig.suptitle("Huber+Suhner SENCITY element patterns @ 77 GHz (TX vs RX)")
    fig.tight_layout()

    if is_non_interactive_backend():
        path = os.path.join(tempfile.gettempdir(), "radarperf_antenna_pattern.png")
        fig.savefig(path, dpi=120)
        print(f"non-interactive backend; saved figure to {path}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
