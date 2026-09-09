"""Provisional Lannik Psi RX-layout and channel-array-factor experiment.

This script compares the equal-weight array factors of the eight RX channel
phase centers. Principal cuts overlay the common TX and RX subarray gains for
context; a separate comparison includes the MIMO signatures. It intentionally
does not change the main range-performance baseline.

Two supplier concepts received on 2026-09-08 are represented:

* square subarrays in a densely packed 2 x 4 channel layout; and
* the supplied-size rectangular subarrays in a 4 x 2 layout, with alternating
  two-channel columns separated vertically by one eighth of a subarray height.

The square layout is shown geometrically as the likely fixed prototype. The
electrical trade plots focus on the relevant second-prototype choice: identical
rectangular subarrays with and without the proposed stagger.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from matplotlib.axes import Axes
from matplotlib.colors import Normalize
from matplotlib.patches import Circle, Rectangle

from lannik_psi import (
    CENTER_FREQUENCY_HZ,
    RX_EXPERIMENTAL_STAGGERED_LAYOUT,
    RX_SOURCE_SUBARRAY_HEIGHT_M,
    RX_SOURCE_SUBARRAY_WIDTH_M,
    RX_SQUARE_LAYOUT,
    RX_SUPPLIED_LAYOUT,
    RxAntennaLayout,
    load_tx_antenna,
)
from quadrant_mimo import normalized_correlation, quadrant_fields_uv, split_tx_quadrants
from radarperf.units import SPEED_OF_LIGHT, linear_to_db

ARRAY_FACTOR_FLOOR_DB = -35.0
UV_MAP_LIMIT = 1.0
CUT_LIMIT = 0.7
UV_SAMPLES = 501
CUT_SAMPLES = 8001
ALIAS_UV_LIMIT = 0.55
ALIAS_UV_SAMPLES = 441


@dataclass(frozen=True)
class LayoutCase:
    """One RX phase-center geometry shown in the comparison."""

    name: str
    layout: RxAntennaLayout
    color: str
    provisional: bool


SQUARE_CASE = LayoutCase(
    "Likely fixed square prototype\n2 × 4 channels",
    RX_SQUARE_LAYOUT,
    "C0",
    True,
)
UNSTAGGERED_CASE = LayoutCase(
    "Unstaggered rectangle",
    RX_SUPPLIED_LAYOUT,
    "0.35",
    False,
)
STAGGERED_CASE = LayoutCase(
    "Staggered rectangle\nheight/8 between adjacent columns",
    RX_EXPERIMENTAL_STAGGERED_LAYOUT,
    "C3",
    True,
)
GEOMETRY_CASES = (
    SQUARE_CASE,
    UNSTAGGERED_CASE,
    STAGGERED_CASE,
)
RECTANGLE_CASES = (
    UNSTAGGERED_CASE,
    STAGGERED_CASE,
)


def channel_array_factor_power(
    layout: RxAntennaLayout,
    u: npt.ArrayLike,
    v: npt.ArrayLike,
    *,
    steering_u: float = 0.0,
    steering_v: float = 0.0,
) -> npt.NDArray[np.float64]:
    """Return the equal-weight channel-array factor, normalized to unity peak."""
    u_array, v_array = np.broadcast_arrays(
        np.asarray(u, dtype=float), np.asarray(v, dtype=float)
    )
    horizontal_m, vertical_m = layout.channel_center_positions_m
    direction_shape = (1,) * u_array.ndim
    horizontal = horizontal_m.reshape((-1,) + direction_shape)
    vertical = vertical_m.reshape((-1,) + direction_shape)
    phase = (
        2.0
        * np.pi
        * CENTER_FREQUENCY_HZ
        / SPEED_OF_LIGHT
        * (
            horizontal * (u_array[None, ...] - steering_u)
            + vertical * (v_array[None, ...] - steering_v)
        )
    )
    voltage = np.mean(np.exp(1.0j * phase), axis=0)
    return np.asarray(np.abs(voltage) ** 2, dtype=float)


def channel_steering_vectors(
    layout: RxAntennaLayout,
    u: npt.ArrayLike,
    v: npt.ArrayLike,
) -> npt.NDArray[np.complex128]:
    """Return one unit-magnitude spatial response per RX channel."""
    u_array, v_array = np.broadcast_arrays(
        np.asarray(u, dtype=float), np.asarray(v, dtype=float)
    )
    horizontal_m, vertical_m = layout.channel_center_positions_m
    direction_shape = (1,) * u_array.ndim
    horizontal = horizontal_m.reshape((-1,) + direction_shape)
    vertical = vertical_m.reshape((-1,) + direction_shape)
    phase = (
        2.0
        * np.pi
        * CENTER_FREQUENCY_HZ
        / SPEED_OF_LIGHT
        * (horizontal * u_array[None, ...] + vertical * v_array[None, ...])
    )
    return np.asarray(np.exp(1.0j * phase), dtype=np.complex128)


def _array_factor_db(power: npt.ArrayLike) -> npt.NDArray[np.float64]:
    return np.asarray(
        linear_to_db(np.maximum(np.asarray(power, dtype=float), 1.0e-30)),
        dtype=float,
    )


def _draw_layout(ax: Axes, case: LayoutCase) -> None:
    wavelength_m = SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ
    layout = case.layout
    horizontal_m, vertical_m = layout.channel_center_positions_m
    width = layout.subarray_width_m / wavelength_m
    height = layout.subarray_height_m / wavelength_m
    horizontal = horizontal_m / wavelength_m
    vertical = vertical_m / wavelength_m
    for center_u, center_v in zip(horizontal, vertical, strict=True):
        ax.add_patch(
            Rectangle(
                (center_u - 0.5 * width, center_v - 0.5 * height),
                width,
                height,
                facecolor=case.color,
                edgecolor="black",
                linewidth=0.9,
                alpha=0.22,
            )
        )
    ax.scatter(
        horizontal,
        vertical,
        s=28.0,
        facecolors="white",
        edgecolors=case.color,
        linewidths=1.2,
        zorder=3,
    )
    margin = 0.12 * max(layout.overall_width_m, layout.overall_height_m) / wavelength_m
    ax.set_xlim(
        float(np.min(horizontal) - 0.5 * width - margin),
        float(np.max(horizontal) + 0.5 * width + margin),
    )
    ax.set_ylim(
        float(np.min(vertical) - 0.5 * height - margin),
        float(np.max(vertical) + 0.5 * height + margin),
    )
    ax.set_title(case.name)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.2)
    ax.set_xlabel("horizontal aperture coordinate / λ (u axis)")
    ax.set_ylabel("vertical aperture coordinate / λ (v axis)")


def plot_geometries(path: Path) -> None:
    """Show the two provisional layouts and the unstaggered reference."""
    fig, axes = plt.subplots(1, len(GEOMETRY_CASES), figsize=(12.5, 4.8))
    for ax, case in zip(axes, GEOMETRY_CASES, strict=True):
        _draw_layout(ax, case)
    fig.suptitle("Provisional Lannik Psi RX geometries", fontsize=14)
    fig.text(
        0.5,
        0.025,
        "Rectangles: uniform RX subarrays | circles: channel phase centers | "
        "layouts are provisional and shown in their own local coordinates",
        ha="center",
        fontsize=8,
        color="0.3",
    )
    fig.tight_layout(rect=(0.0, 0.07, 1.0, 0.94))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  saved {path}")


def plot_array_factors_uv(path: Path) -> None:
    """Compare the rectangular options' boresight channel-array factors."""
    uv_axis = np.linspace(-UV_MAP_LIMIT, UV_MAP_LIMIT, UV_SAMPLES)
    u, v = np.meshgrid(uv_axis, uv_axis, indexing="xy")
    fig, axes = plt.subplots(1, len(RECTANGLE_CASES), figsize=(9.8, 4.9))
    image = None
    for ax, case in zip(axes, RECTANGLE_CASES, strict=True):
        factor_db = _array_factor_db(channel_array_factor_power(case.layout, u, v))
        factor_db = np.where(u**2 + v**2 <= 1.0, factor_db, np.nan)
        image = ax.pcolormesh(
            u,
            v,
            np.maximum(factor_db, ARRAY_FACTOR_FLOOR_DB),
            shading="auto",
            cmap="viridis",
            vmin=ARRAY_FACTOR_FLOOR_DB,
            vmax=0.0,
        )
        ax.add_patch(
            Circle(
                (0.0, 0.0),
                1.0,
                fill=False,
                edgecolor="white",
                linewidth=0.8,
                linestyle=":",
            )
        )
        ax.plot(0.0, 0.0, marker="+", color="red", markersize=7.0)
        if case.layout is RX_EXPERIMENTAL_STAGGERED_LAYOUT:
            wavelength_m = SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ
            period_u = wavelength_m / RX_SOURCE_SUBARRAY_WIDTH_M
            old_period_v = wavelength_m / RX_SOURCE_SUBARRAY_HEIGHT_M
            for replica_u in (-0.5 * period_u, 0.5 * period_u):
                for replica_v in (-4.0 * old_period_v, 4.0 * old_period_v):
                    ax.plot(
                        replica_u,
                        replica_v,
                        marker="o",
                        markersize=5.0,
                        markerfacecolor="none",
                        markeredgecolor="red",
                    )
        ax.set_title(case.name)
        ax.set_xlabel("u")
        ax.set_ylabel("v")
        ax.set_aspect("equal")
        ax.set_xlim(-UV_MAP_LIMIT, UV_MAP_LIMIT)
        ax.set_ylim(-UV_MAP_LIMIT, UV_MAP_LIMIT)
    if image is None:
        raise RuntimeError("at least one layout case is required")
    colorbar = fig.colorbar(image, ax=axes, orientation="horizontal", fraction=0.08)
    colorbar.set_label("boresight channel-array factor [dB relative to peak]")
    fig.suptitle(
        "Rectangular RX alternatives: channel-array factors\n"
        "subarray pattern not included",
        fontsize=14,
    )
    fig.subplots_adjust(left=0.07, right=0.98, bottom=0.20, top=0.80, wspace=0.20)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  saved {path}")


def plot_array_factor_cuts(path: Path) -> None:
    """Compare boresight RX factors alongside the common TX and RX gains."""
    direction = np.linspace(-CUT_LIMIT, CUT_LIMIT, CUT_SAMPLES)
    zeros = np.zeros_like(direction)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.7), sharey=True)
    for case in RECTANGLE_CASES:
        linestyle = "-" if case.provisional else "--"
        axes[0].plot(
            direction,
            _array_factor_db(channel_array_factor_power(case.layout, direction, zeros)),
            color=case.color,
            linestyle=linestyle,
            label=case.name.replace("\n", ": "),
        )
        axes[1].plot(
            direction,
            _array_factor_db(channel_array_factor_power(case.layout, zeros, direction)),
            color=case.color,
            linestyle=linestyle,
            label=case.name.replace("\n", ": "),
        )
    wavelength_m = SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ
    subarray_patterns_db = (
        _array_factor_db(
            np.sinc(RX_SOURCE_SUBARRAY_WIDTH_M * direction / wavelength_m) ** 2
        ),
        _array_factor_db(
            np.sinc(RX_SOURCE_SUBARRAY_HEIGHT_M * direction / wavelength_m) ** 2
        ),
    )
    tx_antenna = load_tx_antenna()
    tx_boresight_gain_db = float(tx_antenna.gain_dbi_uv(0.0, 0.0))
    tx_patterns_db = (
        np.asarray(tx_antenna.gain_dbi_uv(direction, zeros)) - tx_boresight_gain_db,
        np.asarray(tx_antenna.gain_dbi_uv(zeros, direction)) - tx_boresight_gain_db,
    )
    for ax, subarray_pattern_db, tx_pattern_db in zip(
        axes, subarray_patterns_db, tx_patterns_db, strict=True
    ):
        ax.plot(
            direction,
            subarray_pattern_db,
            color="C0",
            linestyle=":",
            linewidth=1.4,
            alpha=0.65,
            label="RX subarray gain (uniform rectangle)",
        )
        ax.plot(
            direction,
            tx_pattern_db,
            color="C2",
            linestyle="-.",
            linewidth=1.5,
            label="TX sum-beam gain",
        )
    for ax, title, label in (
        (axes[0], "Horizontal cut", "u (v = 0)"),
        (axes[1], "Vertical cut", "v (u = 0)"),
    ):
        ax.set_title(title)
        ax.set_xlabel(label)
        ax.set_xlim(-CUT_LIMIT, CUT_LIMIT)
        ax.set_ylim(ARRAY_FACTOR_FLOOR_DB, 1.0)
        ax.grid(True, alpha=0.25)
    axes[0].set_ylabel("gain / array factor [dB relative to boresight]")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, fontsize=8)
    fig.suptitle(
        "Rectangular RX alternatives: boresight gain components\n"
        "TX gain + RX subarray gain + RX channel-array factor",
        fontsize=14,
    )
    fig.tight_layout(rect=(0.0, 0.15, 1.0, 0.92))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  saved {path}")


def _fold_to_reference_cell(
    coordinate: npt.NDArray[np.float64], period: float
) -> npt.NDArray[np.float64]:
    """Fold using the unstaggered rectangle's independent u/v periods."""
    return np.asarray((coordinate + 0.5 * period) % period - 0.5 * period)


def plot_rectangle_alias_comparison(path: Path) -> None:
    """Compare complete ideal MIMO alias correlation with and without stagger."""
    wavelength_m = SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ
    period_u = wavelength_m / RX_SOURCE_SUBARRAY_WIDTH_M
    period_v = wavelength_m / RX_SOURCE_SUBARRAY_HEIGHT_M
    axis = np.linspace(-ALIAS_UV_LIMIT, ALIAS_UV_LIMIT, ALIAS_UV_SAMPLES)
    u, v = np.meshgrid(axis, axis, indexing="xy")
    folded_u = _fold_to_reference_cell(u, period_u)
    folded_v = _fold_to_reference_cell(v, period_v)

    tx_antenna = load_tx_antenna()
    quadrants = split_tx_quadrants(tx_antenna)
    tx_correlation = normalized_correlation(
        quadrant_fields_uv(quadrants, u, v),
        quadrant_fields_uv(quadrants, folded_u, folded_v),
    )
    rx_correlations = tuple(
        normalized_correlation(
            channel_steering_vectors(case.layout, u, v),
            channel_steering_vectors(case.layout, folded_u, folded_v),
        )
        for case in RECTANGLE_CASES
    )
    combined_correlations = tuple(
        tx_correlation * rx_correlation for rx_correlation in rx_correlations
    )

    inside_principal = (np.abs(u) <= 0.5 * period_u) & (np.abs(v) <= 0.5 * period_v)
    visible = u**2 + v**2 <= 1.0
    plot_mask = visible & ~inside_principal
    combined_db = tuple(
        np.where(
            plot_mask,
            _array_factor_db(combined_correlation),
            np.nan,
        )
        for combined_correlation in combined_correlations
    )
    stagger_contribution_db = np.where(
        plot_mask,
        _array_factor_db(rx_correlations[1]),
        np.nan,
    )

    correlation_norm = Normalize(vmin=-35.0, vmax=0.0)
    contribution_norm = Normalize(vmin=-12.0, vmax=0.0)
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 6.0))
    correlation_image = None
    for ax, case, correlation_db in zip(
        axes[:2], RECTANGLE_CASES, combined_db, strict=True
    ):
        correlation_image = ax.pcolormesh(
            u,
            v,
            correlation_db,
            shading="auto",
            cmap="magma",
            norm=correlation_norm,
        )
        ax.set_title(f"{case.name}\ncomplete 4-quadrant MIMO")
    contribution_image = axes[2].pcolormesh(
        u,
        v,
        stagger_contribution_db,
        shading="auto",
        cmap="viridis_r",
        norm=contribution_norm,
    )
    axes[2].set_title("Additional RX decorrelation\nprovided by stagger")

    for ax in axes:
        ax.add_patch(
            Rectangle(
                (-0.5 * period_u, -0.5 * period_v),
                period_u,
                period_v,
                fill=False,
                edgecolor="cyan",
                linestyle="--",
                linewidth=1.0,
            )
        )
        ax.set_xlim(-ALIAS_UV_LIMIT, ALIAS_UV_LIMIT)
        ax.set_ylim(-ALIAS_UV_LIMIT, ALIAS_UV_LIMIT)
        ax.set_xlabel("u")
        ax.set_ylabel("v")
        ax.set_aspect("equal")
        ax.set_facecolor("0.82")
    if correlation_image is None:
        raise RuntimeError("at least one rectangular layout case is required")
    correlation_colorbar_ax = fig.add_axes((0.09, 0.07, 0.55, 0.035))
    correlation_colorbar = fig.colorbar(
        correlation_image, cax=correlation_colorbar_ax, orientation="horizontal"
    )
    correlation_colorbar.set_label(
        "squared correlation with reference-cell hypothesis [dB]"
    )
    contribution_colorbar_ax = fig.add_axes((0.70, 0.07, 0.25, 0.035))
    contribution_colorbar = fig.colorbar(
        contribution_image, cax=contribution_colorbar_ax, orientation="horizontal"
    )
    contribution_colorbar.set_label("stagger RX contribution [dB]")
    fig.suptitle(
        "Rectangular RX alternatives: ideal folded-alias discrimination\n"
        "cyan rectangle is the unstaggered reference cell; more negative is better",
        fontsize=14,
    )
    fig.subplots_adjust(left=0.05, right=0.98, bottom=0.20, top=0.72, wspace=0.20)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  saved {path}")


def print_diagnostics() -> None:
    """Print the principal alias changes introduced by the proposed stagger."""
    wavelength_m = SPEED_OF_LIGHT / CENTER_FREQUENCY_HZ
    period_u = wavelength_m / RX_SOURCE_SUBARRAY_WIDTH_M
    old_period_v = wavelength_m / RX_SOURCE_SUBARRAY_HEIGHT_M
    stagger = RX_SOURCE_SUBARRAY_HEIGHT_M / 8.0
    stagger_layout = RX_EXPERIMENTAL_STAGGERED_LAYOUT

    vertical_search = np.linspace(0.5 * old_period_v, 1.5 * old_period_v, 20001)
    vertical_factor = channel_array_factor_power(
        stagger_layout, np.zeros_like(vertical_search), vertical_search
    )
    peak_index = int(np.argmax(vertical_factor))
    first_peak_v = float(vertical_search[peak_index])
    first_peak_db = float(_array_factor_db(vertical_factor[peak_index]))

    old_vertical_replica_db = float(
        _array_factor_db(channel_array_factor_power(stagger_layout, 0.0, old_period_v))
    )
    exact_skew_u = 0.5 * period_u
    exact_skew_v = 4.0 * old_period_v
    exact_skew_db = float(
        _array_factor_db(
            channel_array_factor_power(stagger_layout, exact_skew_u, exact_skew_v)
        )
    )

    print("Provisional staggered rectangular RX channel array")
    print(
        f"  subarray width x height : {period_u:.4f} u-period x {old_period_v:.4f} v-period"
    )
    print(f"  alternating displacement: {1e3 * stagger:.3f} mm = height / 8")
    print(
        f"  old first vertical replica at Δv={old_period_v:.4f}: "
        f"{old_vertical_replica_db:.2f} dB"
    )
    print(
        f"  nearby vertical-cut peak at v={first_peak_v:.4f}: "
        f"{first_peak_db:.2f} dB"
    )
    print(
        "  first exact skew replica at "
        f"(Δu,Δv)=({exact_skew_u:.4f},{exact_skew_v:.4f}): "
        f"{exact_skew_db:.2f} dB"
    )
    print("  pure horizontal replicas remain unchanged")

    tx_antenna = load_tx_antenna()
    quadrants = split_tx_quadrants(tx_antenna)
    for name, first_u, first_v, second_u, second_v in (
        (
            "opposite horizontal edges",
            0.5 * period_u,
            0.0,
            -0.5 * period_u,
            0.0,
        ),
        (
            "opposite vertical edges",
            0.0,
            0.5 * old_period_v,
            0.0,
            -0.5 * old_period_v,
        ),
    ):
        tx_correlation = float(
            normalized_correlation(
                quadrant_fields_uv(quadrants, np.asarray(first_u), np.asarray(first_v)),
                quadrant_fields_uv(
                    quadrants, np.asarray(second_u), np.asarray(second_v)
                ),
            )
        )
        comparison = []
        for case in RECTANGLE_CASES:
            rx_correlation = float(
                normalized_correlation(
                    channel_steering_vectors(case.layout, first_u, first_v),
                    channel_steering_vectors(case.layout, second_u, second_v),
                )
            )
            comparison.append(float(_array_factor_db(tx_correlation * rx_correlation)))
        print(
            f"  full MIMO {name:27s}: "
            f"{comparison[0]:6.2f} dB unstaggered / "
            f"{comparison[1]:6.2f} dB staggered"
        )


def main() -> None:
    output_dir = Path(__file__).parent / "generated" / "experimental"
    output_dir.mkdir(parents=True, exist_ok=True)
    print_diagnostics()
    plot_geometries(output_dir / "rx_provisional_geometries.png")
    plot_array_factors_uv(output_dir / "rx_channel_array_factor_uv.png")
    plot_array_factor_cuts(output_dir / "rx_channel_array_factor_cuts.png")
    plot_rectangle_alias_comparison(output_dir / "rx_rectangle_alias_correlation.png")


if __name__ == "__main__":
    main()
