"""radarperf -- range-performance toolbox for 77 GHz FMCW (MIMO) radar.

A small, scriptable toolbox built around the FMCW radar range equation.  Each
ingredient (front-end, antenna, waveform, processing, target, environment) is a
pluggable component; the :class:`Radar` engine composes them and computes SNR /
SINR link budgets, single-scan Pd, range/angle sweeps, coverage and multi-scan
acquisition probability.

Example
-------
>>> from radarperf import (
...     Radar, FmcwWaveform, StandardProcessing, MimoScheme,
...     AntennaPair, GaussianBeamAntenna, frontend, target,
... )
>>> wf = FmcwWaveform(center_frequency_hz=77e9, bandwidth_hz=1e9,
...                   sample_rate_hz=20e6, n_samples=256, n_chirps=128)
>>> radar = Radar(
...     frontend=frontend.awr2243(),
...     waveform=wf,
...     processing=StandardProcessing(mimo=MimoScheme.TDM),
...     antenna=AntennaPair.from_element(GaussianBeamAntenna(12.0, 60.0, 12.0)),
... )
>>> budget = radar.link_budget(target.car(), Geometry(range_m=120.0))
>>> round(budget.snr_db, 1)  # doctest: +SKIP
"""

from __future__ import annotations

from . import antenna, detection, frontend, sweeps, target, units
from .antenna import (
    AntennaPair,
    ConstantGainAntenna,
    GaussianBeamAntenna,
    PatternCutAntenna,
    PatternUVAntenna,
)
from .detection import (
    albersheim_required_snr_db,
    cumulative_pd,
    probability_of_acquisition_mofn,
    probability_of_detection,
    required_snr_db,
    shnidman_required_snr_db,
)
from .engine import Radar
from .environment import Atmosphere, CompositeEnvironment, FreeSpace, Rain
from .frontend import GenericFrontend, cascade
from .geometry import Geometry
from .processing import (
    BeamCombination,
    CombiningStage,
    MimoScheme,
    StagedProcessing,
    StandardProcessing,
    WINDOW_LOSS_BLACKMAN_DB,
    WINDOW_LOSS_BLACKMAN_HARRIS_DB,
    WINDOW_LOSS_FLAT_TOP_DB,
    WINDOW_LOSS_HAMMING_DB,
    WINDOW_LOSS_HANN_DB,
    WINDOW_LOSS_RECTANGULAR_DB,
)
from .protocols import (
    Antenna,
    Environment,
    Frontend,
    Processing,
    ProcessingBudget,
    Target,
    Waveform,
)
from .results import LinkBudget
from .target import (
    AspectRcsTarget,
    ConstantRcsTarget,
    RcsTableTarget,
)
from .waveform import FmcwWaveform

__all__ = [
    "Radar",
    "Geometry",
    "FmcwWaveform",
    "StandardProcessing",
    "StagedProcessing",
    "CombiningStage",
    "MimoScheme",
    "BeamCombination",
    "WINDOW_LOSS_RECTANGULAR_DB",
    "WINDOW_LOSS_HANN_DB",
    "WINDOW_LOSS_HAMMING_DB",
    "WINDOW_LOSS_BLACKMAN_DB",
    "WINDOW_LOSS_BLACKMAN_HARRIS_DB",
    "WINDOW_LOSS_FLAT_TOP_DB",
    "GenericFrontend",
    "cascade",
    "AntennaPair",
    "ConstantGainAntenna",
    "GaussianBeamAntenna",
    "PatternCutAntenna",
    "PatternUVAntenna",
    "ConstantRcsTarget",
    "AspectRcsTarget",
    "RcsTableTarget",
    "FreeSpace",
    "Atmosphere",
    "Rain",
    "CompositeEnvironment",
    "LinkBudget",
    "ProcessingBudget",
    "probability_of_detection",
    "required_snr_db",
    "albersheim_required_snr_db",
    "shnidman_required_snr_db",
    "cumulative_pd",
    "probability_of_acquisition_mofn",
    "Antenna",
    "Environment",
    "Frontend",
    "Processing",
    "Target",
    "Waveform",
    "units",
    "detection",
    "frontend",
    "target",
    "sweeps",
    "antenna",
]
