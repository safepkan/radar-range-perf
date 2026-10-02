"""Field captures: absolute reflector levels against the walk and the model.

The walk's reflector, on a small tripod at about the radar's height, at each
placement with both waveforms. Its zero-Doppler power per RX and CPI, in ADC
counts squared with sum-normalized windows (independent of window length and
padding), is scaled to 16 m by R^-4 at its apparent range. Two corrections
follow:

- the receiver's IF response at the reflector's beat frequency, relative to
  2.5 MHz, from field_if.py's chained octave ratios, where they reach;
- the reflector's near-field loss (field_common.near_field_loss_db).

The walk's inbound leg, scaled the same way from walk_extract.py's per-frame
powers, is the comparison: same reflector, same receiver noise density (both
computed here), Infineon's firmware. Each placement's azimuth comes from the
per-RX phases (field_common.azimuth_deg), with the FARAD-IV preset's two-way
pattern loss there. The model is walk_model.py's reference model (datasheet TX
power and noise figure, FARAD-IV directivity, no hardware losses) with the
field waveform and windows and the walking reflector's 11.27 dBsm; the measured
SNR uses the TX-off background at the reflector's beat frequency (local) or at
18-24 MHz. Writes generated/field/level/summary.json and levels.png.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

from carkit_common import STUDY_DIR, db, enbw_bins, write_summary
from field_common import (
    GENERATED_DIR,
    NOMINAL_RANGES_M,
    REFLECTOR_EDGE_M,
    WAVEFORMS,
    azimuth_deg,
    data_argument,
    kept_frames,
    load,
    near_field_loss_db,
    placement_case,
    read_summary,
    reference_radar,
    wavelength_m,
    zero_doppler_amplitudes,
)
from walk_common import WALKING_RCS_DBSM, window_enbw_bins
from window_common import Capture, doppler_window, range_window
from window_scene import BACKGROUND_REFERENCE_HZ
from radarperf import ConstantRcsTarget, Geometry, antenna

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SCALE_RANGE_M = 16.0
WALK_TRACK = STUDY_DIR / "generated" / "walk" / "extract" / "per_frame.csv"
# Inbound bands of the walk's range-structure table (NOTES).
WALK_BANDS_M = ((15.0, 27.0), (27.0, 38.0), (38.0, 52.0))
# Beat frequencies closer than this fraction count as the same point of the
# chained IF response (field_if.CHAIN_TOLERANCE).
IF_MATCH_TOLERANCE = 0.10


def if_correction_db(beat_hz: float, response: dict[str, float]) -> float | None:
    """The chained IF response at ``beat_hz`` [dB], or None outside the chain."""
    if not response:
        return None
    nearest = min(response, key=lambda f: abs(float(f) / beat_hz - 1))
    if abs(float(nearest) / beat_hz - 1) > IF_MATCH_TOLERANCE:
        return None
    return response[nearest]


def walk_levels() -> dict[str, Any]:
    """Walk inbound powers scaled to SCALE_RANGE_M and its far-quarter noise."""
    if not WALK_TRACK.is_file():
        raise SystemExit(f"{WALK_TRACK} not found; run walk_extract.py first")
    rows = list(csv.DictReader(WALK_TRACK.open()))
    channels = range(1, 9)
    inbound = [row for row in rows if row["leg"] == "inbound"]
    range_m = np.array([float(row["range_m"]) for row in inbound])
    power = np.array(
        [[float(row[f"rx{c}_signal_power_db"]) for c in channels] for row in inbound]
    )
    scaled = db(np.mean(10 ** (power / 10), axis=1)) + 40 * np.log10(
        range_m / SCALE_RANGE_M
    )
    bands = {}
    for low, high in WALK_BANDS_M:
        mask = (range_m >= low) & (range_m < high)
        bands[f"{low:g}-{high:g}"] = {
            "cpis": int(mask.sum()),
            "mean_db": float(scaled[mask].mean()),
            "std_db": float(scaled[mask].std()),
        }
    legs = [row for row in rows if row["leg"] in ("inbound", "outbound")]
    noise = np.array(
        [
            float(row[f"rx{c}_signal_power_db"]) - float(row[f"rx{c}_far_snr_db"])
            for row in legs
            for c in channels
        ]
    )
    per_cell_db = float(db(np.mean(10 ** (noise / 10))))
    per_sample_db = per_cell_db + float(
        db(512 / window_enbw_bins(512)) + db(1024 / window_enbw_bins(1024))
    )
    return {
        "inbound_scaled_db_counts2": bands,
        "far_quarter_noise_db_counts2_per_cell": per_cell_db,
        "noise_density_db_counts2_per_sample": per_sample_db,
    }


def placement(
    capture: Capture,
    centre_hz: float,
    response: dict[str, float],
    background: dict[str, Any],
) -> dict[str, Any]:
    frames, dropped = kept_frames(capture)
    beat, values = zero_doppler_amplitudes(capture, frames, centre_hz)
    power = np.abs(values) ** 2  # [frame, RX]
    range_m = float(beat / capture.beat_frequency_hz(1.0))
    level = float(db(power.mean()))
    scaled = level + 40 * float(np.log10(range_m / SCALE_RANGE_M))
    correction = if_correction_db(beat, response)
    near_field = float(
        near_field_loss_db(REFLECTOR_EDGE_M, range_m, wavelength_m(capture))
    )
    angle, coherence = azimuth_deg(values.mean(axis=0), wavelength_m(capture))
    pair = antenna.sencity_farad_iv()
    pattern = float(
        pair.tx.gain_dbi(angle, 0.0)
        + pair.rx.gain_dbi(angle, 0.0)
        - pair.tx.gain_dbi(0.0, 0.0)
        - pair.rx.gain_dbi(0.0, 0.0)
    )
    local = float(np.interp(beat, background["beat_hz"], db(background["floor"])))
    model = (
        reference_radar(capture)
        .link_budget(
            ConstantRcsTarget.from_dbsm(WALKING_RCS_DBSM, swerling=0),
            Geometry(range_m=range_m),
        )
        .snr_db
    )
    return {
        "case": capture.case,
        "cpis_used": len(frames),
        "cpis_dropped_interference": dropped,
        "range_m": range_m,
        "beat_hz": float(beat),
        "power_db_counts2": level,
        "cpi_std_db": float(db(power.mean(axis=1)).std()),
        "per_rx_db": (db(power.mean(axis=0)) - level).tolist(),
        "scaled_db_counts2": scaled,
        "if_response_db": correction,
        "near_field_loss_db": near_field,
        "corrected_db_counts2": (
            None if correction is None else scaled - correction + near_field
        ),
        "azimuth_deg": angle,
        "array_coherence": coherence,
        "two_way_pattern_db": pattern,
        "snr_local_db": level - local,
        "snr_high_if_db": level - background["high_if_db"],
        "model_snr_db": model,
        "residual_local_db": level - local - model,
        "residual_high_if_db": level - background["high_if_db"] - model,
    }


def plot(output: Path, rows: list[dict[str, Any]], walk: dict[str, Any]) -> None:
    figure, axis = plt.subplots(figsize=(9, 5.5), layout="constrained")
    markers = {"medium": "o", "short": "s"}
    for waveform in WAVEFORMS:
        mine = [r for r in rows if r["case"].startswith(waveform)]
        axis.plot(
            [r["range_m"] for r in mine],
            [r["scaled_db_counts2"] for r in mine],
            markers[waveform],
            mfc="none",
            color="0.6",
            label=f"{waveform}, as measured",
        )
        corrected = [r for r in mine if r["corrected_db_counts2"] is not None]
        axis.plot(
            [r["range_m"] for r in corrected],
            [r["corrected_db_counts2"] for r in corrected],
            markers[waveform],
            color="C0" if waveform == "medium" else "C1",
            label=f"{waveform}, IF response and near field corrected",
        )
    for i, (band, values) in enumerate(walk["inbound_scaled_db_counts2"].items()):
        low, high = (float(x) for x in band.split("-"))
        axis.fill_between(
            [low, high],
            values["mean_db"] - values["std_db"],
            values["mean_db"] + values["std_db"],
            color="C2",
            alpha=0.25,
            label="Walk inbound, mean ± std" if i == 0 else None,
        )
        axis.plot([low, high], [values["mean_db"]] * 2, color="C2")
    axis.set(
        xscale="log",
        xlabel="Apparent range [m]",
        ylabel=f"Reflector power scaled to {SCALE_RANGE_M:g} m by R⁻⁴ [dB ADC-count²]",
        title="Walking reflector on a tripod (field, our firmware) against the walk",
    )
    axis.grid(alpha=0.3, which="both")
    axis.legend(fontsize=8)
    figure.savefig(output / "levels.png", dpi=120)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_argument(parser)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "level")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    if_summary = read_summary("if")
    response: dict[str, float] = if_summary["if_response_db"]
    pairs: list[dict[str, Any]] = if_summary["pairs"]
    stored = np.load(GENERATED_DIR / "if" / "notx_background.npz")
    beat = stored["beat_hz"]
    reference = (beat >= BACKGROUND_REFERENCE_HZ[0]) & (
        beat <= BACKGROUND_REFERENCE_HZ[1]
    )
    background = {
        "beat_hz": beat,
        "floor": stored["independent_floor"],
        "high_if_db": float(np.median(db(stored["independent_floor"][reference]))),
    }
    walk = walk_levels()

    rows = []
    for nominal in NOMINAL_RANGES_M:
        pair = next(
            p for p in pairs if p["medium_case"] == placement_case("medium", nominal)
        )
        centres = {
            "medium": pair["medium_beat_hz"],
            "short": pair["short_full_beat_hz"],
        }
        for waveform in WAVEFORMS:
            capture = load(placement_case(waveform, nominal), args.data)
            rows.append(placement(capture, centres[waveform], response, background))
            row = rows[-1]
            print(
                f"{row['case']:12s} {row['range_m']:6.2f} m  {row['scaled_db_counts2']:5.1f} -> "
                f"{row['corrected_db_counts2']} dB  az {row['azimuth_deg']:+5.1f} deg  "
                f"model residual {row['residual_local_db']:+.1f} dB"
            )

    # The field noise density at 18-24 MHz, TX off, total remote-Doppler power.
    capture = load(placement_case("medium", NOMINAL_RANGES_M[0]), args.data)
    total_db = float(np.median(db(stored["total_floor"][reference])))
    field_density = total_db + float(
        db(capture.n_samples / enbw_bins(range_window(capture.n_samples)))
        + db(capture.n_chirps / enbw_bins(doppler_window(capture.n_chirps)))
    )
    walk_reference = walk["inbound_scaled_db_counts2"]["15-27"]["mean_db"]
    comparable = [
        r
        for r in rows
        if r["corrected_db_counts2"] is not None and 15.0 <= r["range_m"] <= 38.0
    ]
    plot(args.output, rows, walk)
    write_summary(
        args.output,
        {
            "scale_range_m": SCALE_RANGE_M,
            "reflector_rcs_dbsm_in_model": WALKING_RCS_DBSM,
            "reflector_edge_m": REFLECTOR_EDGE_M,
            "walk": walk,
            "field_noise_density_db_counts2_per_sample": field_density,
            "high_if_background_db_counts2_per_cell": background["high_if_db"],
            "placements": rows,
            "field_minus_walk_15_27_m_db": {
                r["case"]: r["corrected_db_counts2"] - walk_reference
                for r in comparable
            },
        },
    )


if __name__ == "__main__":
    main()
