"""Reproduce the RFQ illustrations from the existing Lannik Psi study models."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

STUDY_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDY_DIR))

from lannik_psi import (  # noqa: E402
    RX_SQUARE_LAYOUT,
    RxAntennaLayout,
    load_tx_antenna,
)
from quadrant_mimo import quadrant_fields_uv, split_tx_quadrants  # noqa: E402
from rx_stagger_amount_experiment import (  # noqa: E402
    staggered_layout,
    unwrapped_excitation_phase,
)

OUTPUT_DIR = STUDY_DIR / "rfq" / "figures"
BLUE = "#236b8e"
ORANGE = "#c96b28"
INK = "#233747"


def save(fig: Figure, name: str) -> None:
    """Keep vector originals and portable bitmap figures for Markdown/PDF."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in ("svg", "png"):
        fig.savefig(OUTPUT_DIR / f"{name}.{suffix}", dpi=220, facecolor="white")
    plt.close(fig)


def plot_modes() -> None:
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.3))
    modes = ("Coherent TX", "Left/right MIMO", "Up/down MIMO")
    groups = ((-1, 1, "UR"), (1, 1, "UL"), (-1, -1, "LR"), (1, -1, "LL"))
    for mode_index, (ax, title) in enumerate(zip(axes, modes, strict=True)):
        for h, z, group in groups:
            second = (mode_index == 1 and h < 0) or (mode_index == 2 and z < 0)
            waveform = "B" if second else "A"
            color = ORANGE if second else BLUE
            ax.add_patch(
                Rectangle((h / 2 - 0.48, z / 2 - 0.48), 0.96, 0.96, color=color)
            )
            ax.text(
                h / 2,
                z / 2,
                f"{group}\nWaveform {waveform}\n2 ports",
                ha="center",
                va="center",
                color="white",
                fontsize=9,
            )
        ax.set_title(title, weight="bold", pad=10)
        ax.set(xlim=(-1.1, 1.1), ylim=(-1.35, 1.1), aspect="equal")
        ax.axis("off")
        ax.text(
            0,
            -1.19,
            "One coherent beam" if mode_index == 0 else "Two separable waveforms",
            ha="center",
            fontsize=10,
        )
    fig.text(
        0.5,
        0.035,
        "Front view: radar left is page right. Four groups × two ports = eight TX ports.\n"
        "Colors show waveform assignment; internal feed boundaries are to be designed.",
        ha="center",
        fontsize=10,
        color=INK,
    )
    fig.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.20, wspace=0.18)
    save(fig, "tx_modes")


def dimension(ax: Axes, start: tuple[float, float], end: tuple[float, float]) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={"arrowstyle": "|-|", "color": INK, "linewidth": 0.9},
    )


def plot_rx_layouts() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 5.0))
    layouts: tuple[tuple[str, RxAntennaLayout], ...] = (
        ("Large RX: staggered rectangles", staggered_layout(0.25)),
        ("Small RX: squares", RX_SQUARE_LAYOUT),
    )
    for ax, (title, layout) in zip(axes, layouts, strict=True):
        horizontal, vertical = layout.channel_center_positions_m
        width = layout.subarray_width_m * 1000
        height = layout.subarray_height_m * 1000
        for index, (h, z) in enumerate(
            zip(horizontal * 1000, vertical * 1000, strict=True)
        ):
            ax.add_patch(
                Rectangle(
                    (h - width / 2, z - height / 2),
                    width,
                    height,
                    facecolor="#e1eef3",
                    edgecolor=BLUE,
                    linewidth=1.2,
                )
            )
            ax.plot(h, z, "o", color=BLUE, markersize=3)
            ax.text(h + 0.8, z + 0.9, str(index + 1), color=INK, fontsize=10)
        overall_w = layout.overall_width_m * 1000
        overall_h = layout.overall_height_m * 1000
        dimension(ax, (-overall_w / 2, -25), (overall_w / 2, -25))
        ax.text(0, -27.5, f"{overall_w:.2f} mm", ha="center", fontsize=10)
        dimension(ax, (-24, -overall_h / 2), (-24, overall_h / 2))
        ax.text(-26, 0, f"{overall_h:.2f} mm", rotation=90, va="center", fontsize=10)
        if layout is layouts[0][1]:
            offset = height / 8
            dimension(ax, (23, -offset), (23, offset))
            ax.text(24.5, 0, "s = 4.70 mm", rotation=90, va="center", fontsize=10)
            ax.plot([-19, 22], [offset, offset], ":", color="0.5", linewidth=0.7)
            ax.plot([-19, 22], [-offset, -offset], ":", color="0.5", linewidth=0.7)
        ax.set_title(title, weight="bold", pad=12)
        ax.set(
            xlim=(-30, 30),
            ylim=(-30, 27),
            aspect="equal",
            xlabel="h: positive towards radar left [mm]",
            ylabel="z: up [mm]",
            xticks=(-20, 0, 20),
            yticks=(-20, 0, 20),
        )
        ax.spines[["top", "right"]].set_visible(False)
    fig.text(
        0.5,
        0.035,
        "Front view; common scale. Rectangles are nominal subarray cells, dots are channel centres.\n"
        "Each RX aperture has its own origin; TX/RX placement and the housing are not shown.",
        ha="center",
        fontsize=10,
        color=INK,
    )
    fig.subplots_adjust(left=0.08, right=0.97, top=0.87, bottom=0.22, wspace=0.28)
    save(fig, "rx_layouts")


def plot_tx_excitation() -> None:
    tx = load_tx_antenna()
    h = tx.horizontal_positions_m * 1000
    z = tx.vertical_positions_m * 1000
    amplitude_db = 20 * np.log10(
        np.abs(tx.excitations) / np.max(np.abs(tx.excitations))
    )
    phase_deg = np.degrees(unwrapped_excitation_phase(np.asarray(tx.excitations)))
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 3.8), layout="constrained")
    for ax, values, title, cmap, low, high, ticks in (
        (
            axes[0],
            amplitude_db,
            "Relative excitation magnitude [dB]",
            "viridis",
            -30,
            0,
            [-30, -15, 0],
        ),
        (
            axes[1],
            phase_deg,
            "Unwrapped excitation phase [deg]",
            "cividis",
            -360,
            0,
            [-360, -180, 0],
        ),
    ):
        mesh = ax.pcolormesh(
            h, z, values.T, cmap=cmap, vmin=low, vmax=high, shading="nearest"
        )
        ax.axhline(0, color="white", linestyle="--", linewidth=0.8)
        ax.axvline(0, color="white", linestyle="--", linewidth=0.8)
        ax.set(
            title=title,
            xlabel="h [mm]",
            ylabel="z [mm]",
            aspect="equal",
            xticks=(-15, 0, 15),
            yticks=(-15, 0, 15),
        )
        fig.colorbar(mesh, ax=ax, ticks=ticks, shrink=0.9)
    save(fig, "tx_reference_taper")


def plot_tx_patterns() -> None:
    tx = load_tx_antenna()
    quadrants = split_tx_quadrants(tx)
    angles = np.linspace(-25, 25, 1001)
    fields = quadrant_fields_uv(
        quadrants, np.sin(np.radians(angles)), np.zeros_like(angles)
    )
    # Unit-power quadrant fields receive one quarter of the fixed total TX power.
    left = (fields[2] + fields[3]) / 2
    right = (fields[0] + fields[1]) / 2
    coherent = np.abs(left + right) ** 2
    reference = float(coherent[angles.size // 2])
    fig, ax = plt.subplots(figsize=(9.8, 3.05), layout="constrained")
    for power, label, color, style in (
        (np.abs(left) ** 2, "Left half, waveform A", BLUE, "-"),
        (np.abs(right) ** 2, "Right half, waveform B", ORANGE, "-"),
        (coherent, "Coherent full aperture", INK, ":"),
        (np.abs(left) ** 2 + np.abs(right) ** 2, "MIMO power sum", "#666666", "--"),
    ):
        ax.plot(
            angles,
            10 * np.log10(np.maximum(power / reference, 1e-12)),
            style,
            color=color,
            label=label,
        )
    ax.set(
        xlim=(-25, 25),
        ylim=(-25, 1),
        xlabel="Azimuth [deg]; positive is radar left",
        ylabel="Power relative to coherent\nboresight [dB]",
    )
    ax.grid(alpha=0.2)
    ax.legend(loc="lower center", ncol=2, fontsize=9, framealpha=0.95)
    save(fig, "tx_reference_patterns")


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.labelcolor": INK,
            "text.color": INK,
            "svg.hashsalt": "lannik-psi-rfq",
        }
    )
    plot_modes()
    plot_rx_layouts()
    plot_tx_excitation()
    plot_tx_patterns()


if __name__ == "__main__":
    main()
