"""Antenna (element) models of increasing sophistication.

* :class:`ConstantGainAntenna` -- just a boresight gain. The simplest useful
  model; you still supply beamwidths so clutter cell sizing works.
* :class:`GaussianBeamAntenna` -- a separable parabolic-in-dB main beam derived
  from the azimuth/elevation 3 dB beamwidths, with a sidelobe floor.
* :class:`PatternCutAntenna` -- separable azimuth and elevation cuts, each given
  as tabulated gain-vs-angle (exactly what the Huber+Suhner SENCITY datasheets
  plot).
* :class:`PatternUVAntenna` -- a full gain map over (azimuth, elevation),
  bilinearly interpolated, for when the complete pattern is available.
* :class:`AntennaPair` -- a transmit/receive element pair, as a real module
  ships (or as two designs combined during a study).  This is what the engine
  takes as its ``antenna``.

:func:`load_pattern_cut_csv` builds a single :class:`PatternCutAntenna` from a CSV
table of gain-vs-angle cuts, and :func:`load_antenna_pair_csv` builds a TX/RX
:class:`AntennaPair` from a table with separate transmit/receive columns; the
:func:`sencity_this_ii` and :func:`sencity_farad_iv` presets use the latter to
load the digitised Huber+Suhner SENCITY datasheet patterns shipped under
``radarperf/data/``.

All report *element* gain; coherent array gain is handled in the processing
model.
"""

from __future__ import annotations

import csv
import importlib.resources
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import IO, Optional, Sequence, cast

import numpy as np
import numpy.typing as npt
from scipy.interpolate import RegularGridInterpolator

from .protocols import Antenna
from .units import FloatOrArray

# Planes recognised in CSV pattern tables, mapped to azimuth/elevation.
_AZ_PLANES = {"azimuth", "az", "h", "horizontal"}
_EL_PLANES = {"elevation", "el", "v", "vertical"}


@dataclass(frozen=True)
class ConstantGainAntenna:
    """Isotropic-within-the-beam model: boresight gain in every direction."""

    boresight_gain_dbi: float
    beamwidth_az_deg: float = 90.0
    beamwidth_el_deg: float = 90.0

    def gain_dbi(
        self, azimuth_deg: FloatOrArray, elevation_deg: FloatOrArray
    ) -> FloatOrArray:
        return self.boresight_gain_dbi


@dataclass(frozen=True)
class GaussianBeamAntenna:
    """Separable main beam: ``-12 (theta / HPBW)^2`` dB on each axis.

    Down 3 dB at the half-beamwidth on each axis, clamped to ``sidelobe_floor``.
    A pragmatic stand-in when only the beamwidths and peak gain are known.
    """

    boresight_gain_dbi: float
    beamwidth_az_deg: float
    beamwidth_el_deg: float
    sidelobe_floor_dbi: float = -30.0

    def gain_dbi(
        self, azimuth_deg: FloatOrArray, elevation_deg: FloatOrArray
    ) -> FloatOrArray:
        az = np.asarray(azimuth_deg, dtype=float)
        el = np.asarray(elevation_deg, dtype=float)
        roll_off = (
            12.0 * (az / self.beamwidth_az_deg) ** 2
            + 12.0 * (el / self.beamwidth_el_deg) ** 2
        )
        gain = np.maximum(self.boresight_gain_dbi - roll_off, self.sidelobe_floor_dbi)
        return cast(FloatOrArray, gain)


@dataclass(frozen=True)
class PatternCutAntenna:
    """Separable antenna built from azimuth and elevation pattern cuts.

    Parameters
    ----------
    boresight_gain_dbi:
        On-axis gain [dBi].
    az_angles_deg, az_relative_db:
        Azimuth cut: angles and *relative* gain (dB relative to boresight,
        usually <= 0) at those angles.  Linearly interpolated; clamped to the
        endpoints outside range.
    el_angles_deg, el_relative_db:
        Elevation cut, same convention.

    The total gain is ``boresight + rel_az(az) + rel_el(el)`` -- a separability
    assumption that is good near boresight and a reasonable engineering
    approximation elsewhere.  Build from tabulated *relative* cuts with
    :meth:`from_cuts`, from *absolute* gain cuts with :meth:`from_absolute_cuts`,
    or from a CSV pattern table with :func:`load_pattern_cut_csv`.
    """

    boresight_gain_dbi: float
    az_angles_deg: npt.NDArray[np.float64]
    az_relative_db: npt.NDArray[np.float64]
    el_angles_deg: npt.NDArray[np.float64]
    el_relative_db: npt.NDArray[np.float64]
    beamwidth_az_deg: float = float("nan")
    beamwidth_el_deg: float = float("nan")

    @classmethod
    def from_cuts(
        cls,
        boresight_gain_dbi: float,
        az_cut: Sequence[tuple[float, float]],
        el_cut: Sequence[tuple[float, float]],
    ) -> "PatternCutAntenna":
        """Build from ``[(angle_deg, relative_db), ...]`` cut definitions."""
        az = np.array(sorted(az_cut), dtype=float)
        el = np.array(sorted(el_cut), dtype=float)
        return cls(
            boresight_gain_dbi=boresight_gain_dbi,
            az_angles_deg=az[:, 0],
            az_relative_db=az[:, 1],
            el_angles_deg=el[:, 0],
            el_relative_db=el[:, 1],
            beamwidth_az_deg=_estimate_beamwidth(az[:, 0], az[:, 1]),
            beamwidth_el_deg=_estimate_beamwidth(el[:, 0], el[:, 1]),
        )

    @classmethod
    def from_absolute_cuts(
        cls,
        az_cut: Sequence[tuple[float, float]],
        el_cut: Sequence[tuple[float, float]],
    ) -> "PatternCutAntenna":
        """Build from ``[(angle_deg, absolute_gain_dbi), ...]`` cuts.

        Each cut is referenced to its own on-axis (0 deg) gain to form the
        relative pattern, and the reported ``boresight_gain_dbi`` is the mean of
        the two on-axis gains -- they nominally agree, but independently
        digitised cuts differ by a few tenths of a dB, and averaging avoids
        favouring one plane.  (A consequence of separability: where a cut ripples
        slightly above its on-axis value the relative gain is slightly positive.)
        """
        az = np.array(sorted(az_cut), dtype=float)
        el = np.array(sorted(el_cut), dtype=float)
        az_boresight = float(np.interp(0.0, az[:, 0], az[:, 1]))
        el_boresight = float(np.interp(0.0, el[:, 0], el[:, 1]))
        return cls(
            boresight_gain_dbi=0.5 * (az_boresight + el_boresight),
            az_angles_deg=az[:, 0],
            az_relative_db=az[:, 1] - az_boresight,
            el_angles_deg=el[:, 0],
            el_relative_db=el[:, 1] - el_boresight,
            beamwidth_az_deg=_estimate_beamwidth(az[:, 0], az[:, 1]),
            beamwidth_el_deg=_estimate_beamwidth(el[:, 0], el[:, 1]),
        )

    def gain_dbi(
        self, azimuth_deg: FloatOrArray, elevation_deg: FloatOrArray
    ) -> FloatOrArray:
        rel_az = np.interp(azimuth_deg, self.az_angles_deg, self.az_relative_db)
        rel_el = np.interp(elevation_deg, self.el_angles_deg, self.el_relative_db)
        return cast(FloatOrArray, self.boresight_gain_dbi + rel_az + rel_el)


class PatternUVAntenna:
    """Full 2-D gain pattern over (azimuth, elevation), bilinearly interpolated.

    Parameters
    ----------
    azimuth_grid_deg, elevation_grid_deg:
        Strictly increasing 1-D grids.
    gain_grid_dbi:
        ``(len(az), len(el))`` array of gains [dBi].
    """

    def __init__(
        self,
        azimuth_grid_deg: npt.NDArray[np.float64],
        elevation_grid_deg: npt.NDArray[np.float64],
        gain_grid_dbi: npt.NDArray[np.float64],
    ) -> None:
        self._az = np.asarray(azimuth_grid_deg, dtype=float)
        self._el = np.asarray(elevation_grid_deg, dtype=float)
        self._gain = np.asarray(gain_grid_dbi, dtype=float)
        if self._gain.shape != (self._az.size, self._el.size):
            raise ValueError("gain_grid_dbi shape must be (n_az, n_el)")
        self._interp = RegularGridInterpolator(
            (self._az, self._el),
            self._gain,
            method="linear",
            bounds_error=False,
            fill_value=None,  # clamp to nearest edge instead of NaN
        )
        self.boresight_gain_dbi = float(self._gain.max())
        self.beamwidth_az_deg = _estimate_beamwidth(
            self._az, self._gain[:, int(np.argmin(np.abs(self._el)))]
        )
        self.beamwidth_el_deg = _estimate_beamwidth(
            self._el, self._gain[int(np.argmin(np.abs(self._az))), :]
        )

    def gain_dbi(
        self, azimuth_deg: FloatOrArray, elevation_deg: FloatOrArray
    ) -> FloatOrArray:
        az, el = np.broadcast_arrays(
            np.asarray(azimuth_deg, dtype=float),
            np.asarray(elevation_deg, dtype=float),
        )
        points = np.column_stack([az.ravel(), el.ravel()])
        values = np.asarray(self._interp(points), dtype=float).reshape(az.shape)
        return float(values) if values.ndim == 0 else cast(FloatOrArray, values)


@dataclass(frozen=True)
class AntennaPair:
    """A transmit/receive antenna element pair -- the engine's ``antenna``.

    A real module (e.g. a Huber+Suhner SENCITY) ships as one part carrying its
    own transmit and receive elements, so it is natural to keep them together.
    The two members are ordinary :class:`Antenna` objects -- two distinct designs
    combined during a paper study, or (via :meth:`from_element`) the same element
    used for both ports.  Pass the pair straight to the engine::

        radar = Radar(antenna=sencity_this_ii(), ...)
    """

    tx: Antenna
    rx: Antenna
    name: str = ""

    @classmethod
    def from_element(cls, element: Antenna, *, name: str = "") -> "AntennaPair":
        """Pair a single element used for both transmit and receive."""
        return cls(tx=element, rx=element, name=name)


def _estimate_beamwidth(
    angles_deg: npt.NDArray[np.float64], gain_db: npt.NDArray[np.float64]
) -> float:
    """Estimate the 3 dB beamwidth from a cut (peak-relative or absolute dB)."""
    rel = gain_db - gain_db.max()
    above = angles_deg[rel >= -3.0]
    if above.size < 2:
        return float("nan")
    return float(above.max() - above.min())


def _canonical_plane(name: str) -> str:
    """Map a CSV plane label to ``"azimuth"`` or ``"elevation"``."""
    key = name.strip().lower()
    if key in _AZ_PLANES:
        return "azimuth"
    if key in _EL_PLANES:
        return "elevation"
    raise ValueError(f"unrecognised plane {name!r}; expected azimuth or elevation")


def load_pattern_cut_csv(
    source: "str | os.PathLike[str] | IO[str]",
    *,
    gain_column: str = "gain_dbi",
    antenna_name: Optional[str] = None,
    frequency_ghz: Optional[float] = None,
    plane_column: str = "plane",
    angle_column: str = "angle_deg",
) -> PatternCutAntenna:
    """Build a single :class:`PatternCutAntenna` from a CSV table of gain cuts.

    The CSV needs a plane column (values ``azimuth``/``elevation``, or the short
    ``az``/``el``), an angle column [deg] and the named absolute-gain column
    [dBi].  ``antenna_name`` (matched against the ``antenna_name`` or
    ``part_number`` columns) and ``frequency_ghz`` filter files that hold more
    than one antenna or frequency; after filtering, exactly one azimuth and one
    elevation cut must remain.  ``source`` may be a path or an open text file.

    Use :func:`load_antenna_pair_csv` for tables with separate transmit and
    receive gain columns.
    """
    rows = _read_pattern_rows(source, antenna_name, frequency_ghz)
    return _build_pattern_cut(rows, gain_column, plane_column, angle_column)


def load_antenna_pair_csv(
    source: "str | os.PathLike[str] | IO[str]",
    *,
    tx_column: str = "avg_tx_gain_dbi",
    rx_column: str = "avg_rx_gain_dbi",
    name: Optional[str] = None,
    antenna_name: Optional[str] = None,
    frequency_ghz: Optional[float] = None,
    plane_column: str = "plane",
    angle_column: str = "angle_deg",
) -> AntennaPair:
    """Build an :class:`AntennaPair` from a CSV with TX and RX gain columns.

    Loads ``tx_column`` into the pair's transmit element and ``rx_column`` into
    its receive element, so one datasheet table becomes a ready-to-use TX/RX
    pair.  Filtering and the plane/angle columns behave as in
    :func:`load_pattern_cut_csv`.  ``name`` defaults to the file's
    ``antenna_name`` (or ``part_number``).
    """
    rows = _read_pattern_rows(source, antenna_name, frequency_ghz)
    tx = _build_pattern_cut(rows, tx_column, plane_column, angle_column)
    rx = _build_pattern_cut(rows, rx_column, plane_column, angle_column)
    if name is None:
        name = rows[0].get("antenna_name") or rows[0].get("part_number") or ""
    return AntennaPair(tx=tx, rx=rx, name=name)


def _read_pattern_rows(
    source: "str | os.PathLike[str] | IO[str]",
    antenna_name: Optional[str],
    frequency_ghz: Optional[float],
) -> list[dict[str, str]]:
    if isinstance(source, (str, os.PathLike)):
        with open(source, newline="") as handle:
            rows = list(csv.DictReader(handle))
    else:
        rows = list(csv.DictReader(source))
    rows = [r for r in rows if _row_matches(r, antenna_name, frequency_ghz)]
    if not rows:
        raise ValueError("no rows match the requested antenna/frequency")
    _require_unambiguous(rows)
    return rows


def _build_pattern_cut(
    rows: list[dict[str, str]],
    gain_column: str,
    plane_column: str,
    angle_column: str,
) -> PatternCutAntenna:
    missing = {plane_column, angle_column, gain_column} - set(rows[0])
    if missing:
        raise ValueError(f"CSV is missing column(s): {sorted(missing)}")
    by_plane: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for r in rows:
        plane = _canonical_plane(r[plane_column])
        by_plane[plane].append((float(r[angle_column]), float(r[gain_column])))
    if by_plane.keys() != {"azimuth", "elevation"}:
        raise ValueError(
            "CSV must contain exactly one azimuth and one elevation cut; got "
            f"{sorted(by_plane)}"
        )
    return PatternCutAntenna.from_absolute_cuts(
        by_plane["azimuth"], by_plane["elevation"]
    )


def _row_matches(
    row: dict[str, str], antenna_name: Optional[str], frequency_ghz: Optional[float]
) -> bool:
    if antenna_name is not None and antenna_name not in (
        row.get("antenna_name"),
        row.get("part_number"),
    ):
        return False
    if frequency_ghz is not None and row.get("frequency_ghz"):
        return float(row["frequency_ghz"]) == frequency_ghz
    return True


def _require_unambiguous(rows: list[dict[str, str]]) -> None:
    names = {
        name for r in rows if (name := r.get("antenna_name") or r.get("part_number"))
    }
    if len(names) > 1:
        raise ValueError(
            f"CSV holds several antennas {sorted(names)}; pass antenna_name="
        )
    freqs = {r["frequency_ghz"] for r in rows if r.get("frequency_ghz")}
    if len(freqs) > 1:
        raise ValueError(
            f"CSV holds several frequencies {sorted(freqs)}; pass frequency_ghz="
        )


# --- Datasheet presets (digitised pattern cuts; verify before use) -----------


def _load_packaged_pair(filename: str, name: str) -> AntennaPair:
    resource = importlib.resources.files("radarperf").joinpath("data", filename)
    with importlib.resources.as_file(resource) as path:
        return load_antenna_pair_csv(path, name=name)


def sencity_this_ii() -> AntennaPair:
    """Huber+Suhner SENCITY THIS-II radar antenna (art. 1377.99.0701).

    76-81 GHz, 4 TX / 4 RX, horizontal polarisation; MMIC interface for TI
    AWR2544 and similar.  Boresight directivity ~16 dBi.  A broad azimuth fan
    (~140 deg 10-dB beamwidth) paired with a narrow elevation beam (~16 deg
    10-dB beamwidth) and first sidelobes > 20 dB down.

    Returns an :class:`AntennaPair` whose ``tx``/``rx`` elements are the
    datasheet's per-channel ``Avg. TX``/``Avg. RX`` cuts (similar but not
    identical)::

        radar = Radar(antenna=sencity_this_ii(), ...)

    Digitised from the preliminary datasheet's 77 GHz performance charts (see
    ``radarperf/data/sencity_this_ii.csv``); valid for a PCB mount without
    radome.
    """
    return _load_packaged_pair("sencity_this_ii.csv", "SENCITY THIS-II")


def sencity_farad_iv() -> AntennaPair:
    """Huber+Suhner SENCITY FARAD-IV radar antenna (art. 1377.99.0744).

    76-81 GHz, 8 TX / 8 RX, vertical polarisation; MMIC interface for Infineon
    CTRX8191F and similar.  Boresight directivity ~15 dBi.  A medium azimuth beam
    (~94 deg 10-dB beamwidth) and a narrow elevation beam (~30 deg 10-dB
    beamwidth) with first sidelobes ~20 dB down.

    Returns an :class:`AntennaPair` whose ``tx``/``rx`` elements are the
    datasheet's per-channel ``Avg. TX``/``Avg. RX`` cuts (similar but not
    identical).

    Digitised from the preliminary datasheet's 77 GHz performance charts (see
    ``radarperf/data/sencity_farad_iv.csv``); valid for a PCB mount without
    radome.
    """
    return _load_packaged_pair("sencity_farad_iv.csv", "SENCITY FARAD-IV")
