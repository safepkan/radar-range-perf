"""Radar range/SNR/Pd tools for FMCW radar trade studies."""

from radar_range.antennas import (
    AntennaModel,
    ConstantGainAntenna,
    SeparablePatternAntenna,
    UvGridPatternAntenna,
)
from radar_range.coverage import (
    RangeSweepResult,
    coverage_boundary_range,
    range_azimuth_grid,
    range_sweep,
)
from radar_range.detection import (
    pd_from_snr,
    pd_nonfluctuating,
    pd_swerling1,
    pd_swerling2,
    probability_m_of_n,
    square_law_threshold_chi2,
)
from radar_range.environment import (
    ConstantClutterPower,
    EnvironmentModel,
    NoClutter,
    RainPowerLawAttenuation,
)
from radar_range.equation import (
    RadarScenario,
    SnrResult,
    calculate_snr,
    received_power_w,
    thermal_noise_power_w,
)
from radar_range.hardware import RadarHardware
from radar_range.processing import CombiningMode, CombiningStage, ProcessingModel
from radar_range.target import (
    AzimuthRcsTable,
    PointTarget,
    nominal_car_target,
    nominal_pedestrian_target,
)
from radar_range.units import (
    db_to_linear,
    dbm_to_w,
    dbsm_to_square_meters,
    linear_to_db,
    square_meters_to_dbsm,
    w_to_dbm,
)
from radar_range.waveform import FmcwWaveform

__all__ = [
    "AntennaModel",
    "AzimuthRcsTable",
    "ConstantClutterPower",
    "CombiningMode",
    "CombiningStage",
    "ConstantGainAntenna",
    "EnvironmentModel",
    "FmcwWaveform",
    "NoClutter",
    "PointTarget",
    "ProcessingModel",
    "RadarHardware",
    "RadarScenario",
    "RainPowerLawAttenuation",
    "RangeSweepResult",
    "SeparablePatternAntenna",
    "SnrResult",
    "UvGridPatternAntenna",
    "calculate_snr",
    "coverage_boundary_range",
    "db_to_linear",
    "dbm_to_w",
    "dbsm_to_square_meters",
    "linear_to_db",
    "nominal_car_target",
    "nominal_pedestrian_target",
    "pd_from_snr",
    "pd_nonfluctuating",
    "pd_swerling1",
    "pd_swerling2",
    "probability_m_of_n",
    "range_azimuth_grid",
    "range_sweep",
    "received_power_w",
    "square_law_threshold_chi2",
    "square_meters_to_dbsm",
    "thermal_noise_power_w",
    "w_to_dbm",
]
