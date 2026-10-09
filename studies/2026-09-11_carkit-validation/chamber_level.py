"""Chamber captures: the reflector's level against the model, at face value.

TX1 alone (02-single-tx), the chamber reflector (10 dBsm) at its apparent
range. The measured SNR is its zero-Doppler power per RX over the receiver's
noise per range-Doppler cell (Blackman-Harris range, Hann Doppler, the
model's windows), from chamber_background.py's floor densities at 4-7 MHz,
centred on 5.3 MHz like the other sessions' baselines, and at 10-12 MHz. The
reflector's beat frequency, 181 kHz, is deep in the high-pass, so its power is
corrected by the high-pass response (chamber_common.high_pass_db) with the
corner chamber_tx1.py measured on the reflector and with the nominal 300 kHz,
and for the finite reflector at short range (chamber_common.pair_power_db,
ideal 77.8 mm edge: TX1's factor as mean power over the eight RX, which
includes the on-axis near-field loss).

The model is field_common.reference_radar's (datasheet typical TX power and
noise figure at the recorded RX gain, 0 dB here; FARAD-IV directivity; no
hardware losses) with the TX power lowered by the recorded 20 dB backoff. That
backoff lies outside the CTRX8188F's specified output power reduction range
(0-15 dB, target datasheet rev. 0.20, Table 24), which the user manual says
must not be left (Table 48, Configure_TX_Power), so the TX power actually
radiated is not known and the result is no evidence on the absolute level.

Writes generated/chamber/level/summary.json.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from carkit_common import SPEED_OF_LIGHT, db, enbw_bins, write_summary
from chamber_common import (
    GENERATED_DIR,
    HIGH_PASS_NOMINAL_HZ,
    REFLECTOR_EDGE_M,
    REFLECTOR_RCS_DBSM,
    SINGLE_CASE,
    TX_POSITION_M,
    data_argument,
    high_pass_db,
    load,
    measured_high_pass_corner_hz,
    pair_power_db,
    reflector_beat,
    reflector_gains,
    rx_positions_m,
)
from field_common import reference_radar
from radarperf import ConstantRcsTarget, Geometry
from radarperf.frontend import GenericFrontend
from window_common import doppler_window, range_window

# The output power reduction range the datasheet specifies (Table 24).
SPECIFIED_BACKOFF_DB = (0.0, 15.0)
NOISE_BANDS = {"5.3 MHz": "4-7", "11 MHz": "10-12"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_argument(parser)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "level")
    args = parser.parse_args()
    background = json.loads((GENERATED_DIR / "background" / "summary.json").read_text())
    corner_hz = measured_high_pass_corner_hz()

    capture = load(SINGLE_CASE, args.data, verify=True)
    nc, ns, _ = capture.shape
    beat = reflector_beat(capture)
    range_m = float(beat * SPEED_OF_LIGHT / (2 * capture.slope_hz_per_s))
    zero = reflector_gains(capture, beat)[0].mean(axis=1)  # [frame, RX]
    level = float(db(np.mean(np.abs(zero) ** 2)))
    wavelength = SPEED_OF_LIGHT / capture.center_frequency_hz
    pairs = pair_power_db(
        REFLECTOR_EDGE_M, range_m, TX_POSITION_M[:1], rx_positions_m(), wavelength
    )[0]
    finite = float(db(np.mean(10 ** (pairs / 10))))

    radar = reference_radar(capture)
    if not isinstance(radar.frontend, GenericFrontend):
        raise TypeError("expected the CTRX8188F preset's GenericFrontend")
    backed_off = radar.frontend.tx_power_w * 10 ** (-capture.tx_backoff_db / 10)
    radar = replace(radar, frontend=replace(radar.frontend, tx_power_w=backed_off))
    model = radar.link_budget(
        ConstantRcsTarget.from_dbsm(REFLECTOR_RCS_DBSM, swerling=0),
        Geometry(range_m=range_m),
    ).snr_db

    densities = background["receiver_noise"]["db_counts2_per_hz"][
        f"chamber {SINGLE_CASE}"
    ]
    cell = float(
        db(
            capture.sample_rate_hz
            / 2
            * enbw_bins(range_window(ns))
            / ns
            * enbw_bins(doppler_window(nc))
            / nc
        )
    )
    corners = {"measured": corner_hz, "nominal": HIGH_PASS_NOMINAL_HZ}
    rows = {}
    for corner_name, corner in corners.items():
        correction = float(high_pass_db(beat, corner))
        for noise_name, band in NOISE_BANDS.items():
            noise = densities[band] + cell
            snr = level - correction - finite - noise
            rows[f"{corner_name} corner, noise at {noise_name}"] = {
                "high_pass_at_reflector_db": correction,
                "noise_per_cell_db_counts2": noise,
                "measured_snr_db": snr,
                "measured_minus_model_db": snr - model,
            }
    write_summary(
        args.output,
        {
            "reflector_range_m": range_m,
            "reflector_beat_khz": beat / 1e3,
            "reflector_rcs_dbsm": REFLECTOR_RCS_DBSM,
            "finite_reflector_db": finite,
            "zero_doppler_level_db_counts2": level,
            "tx_backoff_db": capture.tx_backoff_db,
            "specified_backoff_range_db": list(SPECIFIED_BACKOFF_DB),
            "rx_gain_db": capture.rx_gain_db,
            "model_snr_db": model,
            "range_sensitivity_db_per_cm": float(40 * np.log10(1 + 0.01 / range_m)),
            "comparisons": rows,
        },
    )


if __name__ == "__main__":
    main()
