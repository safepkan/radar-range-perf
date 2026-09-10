"""On-demand MIMO resolution events for the provisional rectangular RX layouts.

One full coherent-TX observation is followed by one ideal MIMO measurement with
variable illumination energy. A fixed 1 m² target is already known to exist in
a range/Doppler gate; trials are NOT conditioned on crossing a detection
threshold. Unknown complex amplitude is fitted independently in each mode.
The decision maximizes summed projection energy over a common angle dictionary,
then reports its lobe index. It is not a Bayesian publication-confidence rule.

Candidate lobes are seeded at every visible old-URA alias with a local 2-D angle
grid, and screened using a noiseless reference measurement and a chosen RCS
ceiling. This is a bounded, finite-grid experiment, not a global manifold search
or a tracker. It deliberately excludes RCS fluctuations, motion, interference,
waveform implementation losses and end-to-end latency. See RX_LAYOUT.md.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from scipy.stats import beta

from lannik_psi import (
    CENTER_FREQUENCY_HZ,
    RX_SOURCE_SUBARRAY_HEIGHT_M,
    RX_SOURCE_SUBARRAY_WIDTH_M,
    TARGET,
    RxAntennaLayout,
    lannik_psi,
    load_tx_antenna,
)
from quadrant_mimo import (
    ComplexArray,
    FloatArray,
    TxQuadrant,
    mimo_tx_gain_dbi,
    quadrant_fields_uv,
    split_tx_quadrants,
)
from radarperf import Geometry, RectangularArrayAntenna
from radarperf.units import SPEED_OF_LIGHT
from rx_layout_experiment import RECTANGLE_CASES, channel_steering_vectors

WAVELENGTH_M = SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ
PERIODS = WAVELENGTH_M / np.array(
    [RX_SOURCE_SUBARRAY_WIDTH_M, RX_SOURCE_SUBARRAY_HEIGHT_M]
)
ENERGIES = np.array([0.0, 0.125, 0.25, 0.375, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 8.0])
COHERENT_SNR_DB = (10.0, 16.0)
PHASE_RMS_DEG = (0.0, 10.0)
SEED = 20260909


@dataclass(frozen=True)
class EventCase:
    name: str
    u: float
    v: float


CASES = (
    EventCase("Vertical edge", 0.0, float(PERIODS[1] / 2)),
    EventCase("Horizontal edge", float(PERIODS[0] / 2), 0.0),
    EventCase("Corner", float(PERIODS[0] / 2), float(PERIODS[1] / 2)),
)


@dataclass(frozen=True)
class HypothesisBank:
    uv: FloatArray
    required_rcs_dbsm: FloatArray
    cell_ids: tuple[tuple[int, int], ...]
    cell_starts: npt.NDArray[np.int64]
    true_cell: int
    coherent: ComplexArray  # unit-norm columns, shape (8, n_angles)
    mimo: ComplexArray  # unit-norm columns, shape (32, n_angles)


def normalize_columns(vectors: ComplexArray) -> ComplexArray:
    norms = np.linalg.norm(vectors, axis=0)
    if np.any(norms <= 0.0) or not np.all(np.isfinite(norms)):
        raise ValueError("steering columns must have finite, nonzero norm")
    return np.asarray(vectors / norms, dtype=np.complex128)


def subarray_relative_gain_db(u: FloatArray, v: FloatArray) -> FloatArray:
    voltage = np.sinc(u / PERIODS[0]) * np.sinc(v / PERIODS[1])
    return np.asarray(20 * np.log10(np.maximum(np.abs(voltage), 1e-15)))


def coherent_gain_db(tx: RectangularArrayAntenna, uv: FloatArray) -> FloatArray:
    """Two-way directional gain, omitting the common RX peak constant."""
    return np.asarray(tx.gain_dbi_uv(uv[:, 0], uv[:, 1])) + subarray_relative_gain_db(
        uv[:, 0], uv[:, 1]
    )


def build_bank(
    case: EventCase,
    layout: RxAntennaLayout,
    tx: RectangularArrayAntenna,
    quadrants: tuple[TxQuadrant, ...],
    *,
    rcs_ceiling_dbsm: float = 10.0,
    local_samples: int = 17,
) -> HypothesisBank:
    """Enumerate old-alias neighborhoods; screen individual angles by RCS.

    A neighborhood extends +/-0.75*period/channel_count in each axis, so
    neighborhoods do not overlap and include the nearby sheared RX replica.
    All layouts use the same neighborhood and noiseless RCS-screen convention.
    """
    if local_samples < 3 or local_samples % 2 != 1:
        raise ValueError("local_samples must be odd and at least 3")
    if not np.isfinite(rcs_ceiling_dbsm) or rcs_ceiling_dbsm < 0:
        raise ValueError("rcs_ceiling_dbsm must be finite and >= 0 for the 1 m² target")
    true_uv = np.array([[case.u, case.v]])
    reference_gain = float(coherent_gain_db(tx, true_uv)[0])
    radius = 0.75 * PERIODS / np.array([4, 2])
    du, dv = np.meshgrid(
        np.linspace(-radius[0], radius[0], local_samples),
        np.linspace(-radius[1], radius[1], local_samples),
        indexing="ij",
    )
    offsets = np.column_stack((du.ravel(), dv.ravel()))
    limits = np.ceil((1 + np.abs(true_uv[0]) + radius) / PERIODS).astype(int)
    cells: list[tuple[int, int]] = []
    starts: list[int] = []
    points: list[FloatArray] = []
    rcs_values: list[FloatArray] = []
    point_count = 0
    for ku in range(-int(limits[0]), int(limits[0]) + 1):
        for kv in range(-int(limits[1]), int(limits[1]) + 1):
            uv = true_uv + np.array([ku, kv]) * PERIODS + offsets
            visible = np.sum(uv**2, axis=1) <= 1.0
            required_rcs = reference_gain - coherent_gain_db(tx, uv)
            keep = visible & (required_rcs <= rcs_ceiling_dbsm + 1e-10)
            if not np.any(keep):
                continue
            cells.append((ku, kv))
            starts.append(point_count)
            points.append(uv[keep])
            rcs_values.append(required_rcs[keep])
            point_count += int(np.count_nonzero(keep))
    uv = np.concatenate(points)
    rx = normalize_columns(channel_steering_vectors(layout, uv[:, 0], uv[:, 1]))
    fields = normalize_columns(quadrant_fields_uv(quadrants, uv[:, 0], uv[:, 1]))
    mimo = np.asarray(np.einsum("qk,rk->qrk", fields, rx).reshape(32, -1))
    return HypothesisBank(
        uv=uv,
        required_rcs_dbsm=np.concatenate(rcs_values),
        cell_ids=tuple(cells),
        cell_starts=np.asarray(starts, dtype=np.int64),
        true_cell=cells.index((0, 0)),
        coherent=rx,
        mimo=mimo,
    )


def choose_cells(
    point_scores: FloatArray,
    cell_starts: npt.NDArray[np.int64],
    rng: np.random.Generator,
) -> npt.NDArray[np.int64]:
    """Maximize over angles per lobe, resolving numerical ties uniformly."""
    scores = np.maximum.reduceat(point_scores, cell_starts, axis=1)
    tied = np.isclose(scores, np.max(scores, axis=1, keepdims=True), rtol=0, atol=1e-10)
    # Exact URA aliases must not be 'resolved' by floating-point error or order.
    tie_breakers = np.where(tied, rng.random(scores.shape), -1.0)
    return np.asarray(np.argmax(tie_breakers, axis=1), dtype=np.int64)


def complex_noise(rng: np.random.Generator, shape: tuple[int, int]) -> ComplexArray:
    return np.asarray(
        (rng.standard_normal(shape) + 1j * rng.standard_normal(shape)) / np.sqrt(2),
        dtype=np.complex128,
    )


def simulate_event(
    bank: HypothesisBank,
    true_rx: ComplexArray,
    true_quadrants: ComplexArray,
    *,
    coherent_snr_db: float,
    mimo_to_coherent_snr: float,
    energies: FloatArray,
    trials: int,
    phase_rms_deg: float = 0.0,
    seed: int = SEED,
) -> npt.NDArray[np.int64]:
    """Wrong-lobe counts for one coherent observation plus a MIMO measurement.

    Positive energies scale one coherent MIMO integration, not independent
    Swerling CPIs. At zero energy no MIMO noise/statistic is added. Phase errors
    are drawn per trial (unit/event), fixed across both modes, with independent
    RX-channel and TX-quadrant offsets. TX offsets also perturb the coherent
    sum. There is no coherent phase integration between the two modes.
    """
    if trials < 1 or energies.ndim != 1 or not np.all(np.isfinite(energies)):
        raise ValueError("positive trials and a finite 1-D energy array are required")
    if np.any(energies < 0) or mimo_to_coherent_snr <= 0 or phase_rms_deg < 0:
        raise ValueError(
            "energies/phase RMS must be nonnegative and SNR ratio positive"
        )
    rng = np.random.default_rng(seed)
    # Changing the energy grid or candidate count must not change the raw
    # signal/noise realizations used to compare layouts and RCS screens.
    decision_rng = np.random.default_rng(seed + 1)
    errors = np.zeros(energies.size, dtype=np.int64)
    snr = 10 ** (coherent_snr_db / 10)
    quadrant_norm = np.linalg.norm(true_quadrants)
    quadrant_sum = np.sum(true_quadrants)
    if abs(quadrant_sum) == 0 or quadrant_norm == 0:
        raise ValueError("the event must have nonzero coherent and MIMO illumination")
    for start in range(0, trials, 1000):
        count = min(1000, trials - start)
        rx_errors = np.exp(
            1j * np.radians(phase_rms_deg) * rng.standard_normal((count, true_rx.size))
        )
        tx_errors = np.exp(
            1j * np.radians(phase_rms_deg) * rng.standard_normal((count, 4))
        )
        rx_signal = true_rx[None, :] * rx_errors
        tx_fields = true_quadrants[None, :] * tx_errors
        coherent_signal = (
            rx_signal * (np.sum(tx_fields, axis=1) / quadrant_sum)[:, None]
        )
        mimo_signal = (
            tx_fields[:, :, None] * rx_signal[:, None, :] / quadrant_norm
        ).reshape(count, -1)
        coherent_data = np.sqrt(snr) * coherent_signal + complex_noise(
            rng, (count, true_rx.size)
        )
        coherent_scores = np.abs(coherent_data @ bank.coherent.conj()) ** 2
        mimo_noise_projection = (
            complex_noise(rng, (count, mimo_signal.shape[1])) @ bank.mimo.conj()
        )
        mimo_signal_projection = mimo_signal @ bank.mimo.conj()
        for index, energy in enumerate(energies):
            scores = coherent_scores
            if energy > 0:
                scores = (
                    scores
                    + np.abs(
                        np.sqrt(energy * snr * mimo_to_coherent_snr)
                        * mimo_signal_projection
                        + mimo_noise_projection
                    )
                    ** 2
                )
            chosen = choose_cells(scores, bank.cell_starts, decision_rng)
            errors[index] += np.count_nonzero(chosen != bank.true_cell)
    return errors


def error_upper_bound(errors: npt.NDArray[np.int64], trials: int) -> FloatArray:
    """One-sided 95% Clopper-Pearson upper bound, including zero-error trials."""
    upper = beta.ppf(0.95, errors + 1, np.maximum(trials - errors, 1))
    return np.asarray(np.where(errors == trials, 1.0, upper), dtype=float)


def plot_results(records: list[dict[str, object]], path: Path, trials: int) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 8.0), sharex=True, sharey=True)
    for record in records:
        row = COHERENT_SNR_DB.index(float(str(record["coherent_snr_db"])))
        column = [case.name for case in CASES].index(str(record["case"]))
        ax = axes[row, column]
        errors = np.asarray(record["errors"], dtype=int)
        upper = error_upper_bound(errors, trials)
        # Do not connect confidence bounds to point estimates: that would
        # create artificial increases when an observed error count becomes zero.
        plotted = np.where(errors > 0, errors / trials, np.nan)
        stagger = bool(record["staggered"])
        ax.plot(
            ENERGIES,
            plotted,
            color="C3" if stagger else "0.25",
            linestyle="-" if stagger else "--",
            marker="o",
            markersize=3,
            label="Staggered" if stagger else "URA",
        )
        ax.scatter(
            ENERGIES[errors == 0],
            upper[errors == 0],
            marker="v",
            color="C3" if stagger else "0.25",
            s=25,
        )
        ax.set_title(
            f"{record['case']} | nominal SNR {record['coherent_snr_db']:g} dB\n"
            f"1 m² reference range {record['range_m']:.0f} m; {record['candidate_lobes']} lobes"
        )
    for ax in axes.flat:
        ax.set_xscale("symlog", linthresh=0.125, base=2)
        ax.set_yscale("log")
        ax.set_ylim(3e-5, 1.0)
        ticks = [0.0, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0]
        ax.set_xticks(ticks, [f"{energy:g}" for energy in ticks])
        ax.axhline(
            0.01, color="0.4", linestyle=":", linewidth=1, label="1% error reference"
        )
        ax.grid(True, alpha=0.25, which="both")
        ax.set_ylabel("wrong-lobe decision probability")
        ax.set_xlabel("additional MIMO illumination [baseline CPI equivalents]")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.075))
    phase_rms = records[0]["phase_rms_deg"]
    fig.suptitle(
        "On-demand resolution: one coherent observation + variable MIMO illumination\n"
        f"RX / TX-quadrant residual phase RMS: {phase_rms:g}°",
        fontsize=14,
    )
    fig.text(
        0.5,
        0.015,
        f"Fixed 1 m² target; known range/Doppler gate; {trials:,} trials | RCS screen +{records[0]['rcs_ceiling_dbsm']:g} dBsm (noiseless reference)\n"
        "Unknown amplitude per mode; angle nuisance search within each lobe | ▼: zero errors, shown at 95% upper bound\n"
        "Ideal coherent MIMO energy scaling, not elapsed latency; no Swerling fluctuations or full-search detection threshold",
        ha="center",
        fontsize=8,
        color="0.3",
    )
    fig.tight_layout(rect=(0, 0.13, 1, 0.91))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  saved {path}")


def run(
    output_dir: Path, *, trials: int, local_samples: int, rcs_ceiling_dbsm: float
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    tx = load_tx_antenna()
    quadrants = split_tx_quadrants(tx)
    product = lannik_psi()
    boresight_snr_100m = product.radar.link_budget(TARGET, Geometry(range_m=100)).snr_db
    tx_boresight = float(tx.gain_dbi_uv(0.0, 0.0))
    records: list[dict[str, object]] = []
    for case in CASES:
        fields = quadrant_fields_uv(quadrants, np.asarray(case.u), np.asarray(case.v))
        coherent_tx = float(tx.gain_dbi_uv(case.u, case.v))
        mimo_tx = float(
            mimo_tx_gain_dbi(quadrants, np.asarray(case.u), np.asarray(case.v))
        )
        ratio = 10 ** ((mimo_tx - coherent_tx) / 10)
        directional_snr_100m = (
            boresight_snr_100m
            + coherent_tx
            - tx_boresight
            + float(subarray_relative_gain_db(np.asarray(case.u), np.asarray(case.v)))
        )
        for layout_case in RECTANGLE_CASES:
            bank = build_bank(
                case,
                layout_case.layout,
                tx,
                quadrants,
                rcs_ceiling_dbsm=rcs_ceiling_dbsm,
                local_samples=local_samples,
            )
            rx = normalize_columns(
                channel_steering_vectors(
                    layout_case.layout, np.array([case.u]), np.array([case.v])
                )
            )[:, 0]
            print(
                f"{case.name}, {layout_case.name.splitlines()[0]}: {len(bank.cell_ids)} lobes, {bank.uv.shape[0]} angles; MIMO SNR difference {mimo_tx-coherent_tx:.2f} dB",
                flush=True,
            )
            for snr_db in COHERENT_SNR_DB:
                for phase_rms in PHASE_RMS_DEG:
                    errors = simulate_event(
                        bank,
                        rx,
                        fields,
                        coherent_snr_db=snr_db,
                        mimo_to_coherent_snr=ratio,
                        energies=ENERGIES,
                        trials=trials,
                        phase_rms_deg=phase_rms,
                    )
                    upper = error_upper_bound(errors, trials)
                    meets = np.flatnonzero(upper <= 0.01)
                    first_energy = float(ENERGIES[meets[0]]) if meets.size else None
                    record: dict[str, object] = dict(
                        case=case.name,
                        true_uv=[case.u, case.v],
                        staggered=layout_case.provisional,
                        coherent_snr_db=snr_db,
                        range_m=float(
                            100 * 10 ** ((directional_snr_100m - snr_db) / 40)
                        ),
                        mimo_snr_difference_db=mimo_tx - coherent_tx,
                        phase_rms_deg=phase_rms,
                        rcs_ceiling_dbsm=rcs_ceiling_dbsm,
                        candidate_lobes=len(bank.cell_ids),
                        cell_ids=bank.cell_ids,
                        candidate_angles=bank.uv.shape[0],
                        errors=errors.tolist(),
                        error_upper_95=upper.tolist(),
                        first_sampled_energy_with_upper_error_below_1pct=first_energy,
                    )
                    records.append(record)
                    print(
                        f"  SNR {snr_db:g}, phase RMS {phase_rms:g}: first sampled energy meeting 1% (95% upper bound) = {first_energy}",
                        flush=True,
                    )
    summary = dict(
        seed=SEED,
        trials=trials,
        local_samples=local_samples,
        energy_cpi_equivalents=ENERGIES.tolist(),
        baseline_active_sampling_time_ms=1000 * product.waveform.dwell_time_s,
        notes="Fixed-RCS known-target event, not detection-conditioned; one coherent observation and one coherent MIMO integration; noiseless RCS screen; finite local grids; not wall-clock latency or a publication posterior.",
        records=records,
    )
    (output_dir / "resolution_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    for phase_rms in PHASE_RMS_DEG:
        selected = [
            record for record in records if record["phase_rms_deg"] == phase_rms
        ]
        plot_results(
            selected, output_dir / f"resolution_phase_{phase_rms:g}deg.png", trials
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=20000)
    parser.add_argument("--local-samples", type=int, default=17)
    parser.add_argument("--rcs-ceiling-dbsm", type=float, default=10.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "generated" / "experimental" / "on_demand",
    )
    args = parser.parse_args()
    run(
        args.output_dir,
        trials=args.trials,
        local_samples=args.local_samples,
        rcs_ceiling_dbsm=args.rcs_ceiling_dbsm,
    )


if __name__ == "__main__":
    main()
