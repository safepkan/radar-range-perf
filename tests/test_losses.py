"""Tests for the named system losses and their effect on the link budget."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from radarperf import (
    AntennaPair,
    FmcwWaveform,
    GaussianBeamAntenna,
    Geometry,
    Radar,
    Rain,
    StandardProcessing,
    SystemLosses,
    frontend,
    sweeps,
    target,
)
from radarperf.units import REFERENCE_TEMPERATURE, SPEED_OF_LIGHT, db_to_linear

GEOM = Geometry(range_m=150.0)


def make_radar(losses: SystemLosses = SystemLosses()) -> Radar:
    wf = FmcwWaveform(
        center_frequency_hz=77e9,
        bandwidth_hz=1e9,
        sample_rate_hz=20e6,
        n_samples=256,
        n_chirps=128,
    )
    ant = GaussianBeamAntenna(
        boresight_gain_dbi=12.0, beamwidth_az_deg=60.0, beamwidth_el_deg=12.0
    )
    return Radar(
        frontend=frontend.awr2243(),
        waveform=wf,
        processing=StandardProcessing(),
        antenna=AntennaPair.from_element(ant),
        losses=losses,
    )


@pytest.mark.parametrize(
    "field",
    [
        "tx_power_derating_db",
        "tx_feed_loss_db",
        "tx_antenna_loss_db",
        "rx_antenna_loss_db",
        "rx_feed_loss_db",
        "noise_figure_derating_db",
    ],
)
def test_each_term_lowers_snr_db_for_db_at_t0(field: str) -> None:
    base = make_radar().link_budget(target.car(), GEOM)
    lossy = make_radar(SystemLosses(**{field: 1.5})).link_budget(target.car(), GEOM)
    assert np.isclose(base.snr_db - lossy.snr_db, 1.5, atol=1e-9)


def test_signal_terms_leave_noise_unchanged_at_t0() -> None:
    losses = SystemLosses(tx_feed_loss_db=1.0, rx_feed_loss_db=2.0)
    base = make_radar().link_budget(target.car(), GEOM)
    lossy = make_radar(losses).link_budget(target.car(), GEOM)
    assert np.isclose(lossy.noise_power_dbm, base.noise_power_dbm, atol=1e-9)
    assert np.isclose(base.signal_power_dbm - lossy.signal_power_dbm, 3.0, atol=1e-9)
    assert np.isclose(lossy.system_loss_db, 3.0, atol=1e-12)


def test_radome_counts_on_both_passes() -> None:
    base = make_radar().link_budget(target.car(), GEOM)
    lossy = make_radar(SystemLosses(radome_one_way_loss_db=0.7)).link_budget(
        target.car(), GEOM
    )
    assert np.isclose(base.snr_db - lossy.snr_db, 1.4, atol=1e-9)
    assert lossy.system_losses_db["radome_two_way"] == pytest.approx(1.4)


def test_tx_derating_matches_lower_tx_power() -> None:
    derated = make_radar(SystemLosses(tx_power_derating_db=1.5))
    weaker = replace(
        make_radar(),
        frontend=frontend.awr2243(tx_power_w=frontend.awr2243().tx_power_w / 10**0.15),
    )
    a = derated.link_budget(target.car(), GEOM).snr_db
    b = weaker.link_budget(target.car(), GEOM).snr_db
    assert np.isclose(a, b, atol=1e-9)


def test_nf_derating_matches_higher_noise_figure() -> None:
    derated = make_radar(SystemLosses(noise_figure_derating_db=2.0))
    noisier = replace(make_radar(), frontend=frontend.awr2243(noise_figure_db=14.0))
    a = derated.link_budget(target.car(), GEOM)
    b = noisier.link_budget(target.car(), GEOM)
    assert np.isclose(a.snr_db, b.snr_db, atol=1e-9)
    assert np.isclose(a.noise_power_dbm, b.noise_power_dbm, atol=1e-9)


def test_receive_loss_adds_passive_noise_for_cold_scene() -> None:
    # Referred to the antenna, T_sys = T_ant + (L - 1) T0 + L (F - 1) T0.
    t_ant = 50.0
    loss_db = 2.0
    cold = replace(make_radar(), antenna_noise_temperature_k=t_ant)
    lossy = replace(cold, losses=SystemLosses(rx_feed_loss_db=loss_db))
    f = db_to_linear(frontend.awr2243().noise_figure_db)
    l_rx = db_to_linear(loss_db)
    t0 = REFERENCE_TEMPERATURE
    expected = 10 * math.log10(
        (t_ant + (l_rx - 1) * t0 + l_rx * (f - 1) * t0) / (t_ant + (f - 1) * t0)
    )
    a = cold.link_budget(target.car(), GEOM).snr_db
    b = lossy.link_budget(target.car(), GEOM).snr_db
    assert np.isclose(a - b, expected, atol=1e-9)
    assert a - b > loss_db  # a cold scene makes a passive loss cost extra


def test_coherence_loss_follows_phase_error_formula() -> None:
    losses = SystemLosses(chirp_frequency_error_rms_hz=3.5e3)
    sigma = 2 * math.pi * 3.5e3 * 2 * 1000.0 / SPEED_OF_LIGHT
    expected = 10 * math.log10(math.e) * sigma**2
    assert float(losses.coherence_loss_db(1000.0)) == pytest.approx(expected)
    assert expected == pytest.approx(0.094, abs=1e-3)
    # Quadratic in range.
    assert float(losses.coherence_loss_db(500.0)) == pytest.approx(expected / 4)


def test_coherence_loss_is_range_dependent_in_sweeps() -> None:
    losses = SystemLosses(chirp_frequency_error_rms_hz=25e3)
    ranges = np.array([100.0, 300.0, 1000.0])
    base = sweeps.range_sweep(make_radar(), target.car(), ranges)
    lossy = sweeps.range_sweep(make_radar(losses), target.car(), ranges)
    expected = np.asarray(losses.coherence_loss_db(ranges), dtype=float)
    assert np.allclose(base.snr_db - lossy.snr_db, expected, atol=1e-9)
    single = make_radar(losses).link_budget(target.car(), Geometry(range_m=300.0))
    assert np.isclose(single.snr_db, lossy.snr_db[1], atol=1e-9)


def test_system_losses_leave_scr_unchanged() -> None:
    rain = Rain(rain_rate_mm_per_hr=25.0)
    geom = Geometry(range_m=40.0)
    losses = SystemLosses(
        tx_feed_loss_db=1.0,
        radome_one_way_loss_db=0.5,
        chirp_frequency_error_rms_hz=20e3,
    )
    a = make_radar().link_budget(target.car(), geom, rain)
    b = make_radar(losses).link_budget(target.car(), geom, rain)
    assert np.isclose(a.scr_db, b.scr_db, atol=1e-9)
    assert b.snr_db < a.snr_db


def test_default_losses_are_all_explicit_zeros() -> None:
    b = make_radar().link_budget(target.car(), GEOM)
    assert b.system_loss_db == 0.0
    assert set(b.system_losses_db) == {
        "tx_power_derating",
        "tx_feed",
        "tx_antenna",
        "radome_two_way",
        "rx_antenna",
        "rx_feed",
        "chirp_coherence",
        "noise_figure_derating",
    }
    assert all(value == 0.0 for value in b.system_losses_db.values())
    # Zero-valued processing losses are listed too.
    assert b.processing_losses_db["mimo"] == 0.0
    text = str(b)
    assert "radome (two-way)" in text and "NF derating" in text


def test_itemised_signal_terms_sum_to_system_loss() -> None:
    losses = SystemLosses(
        tx_power_derating_db=1.0,
        noise_figure_derating_db=1.5,
        tx_feed_loss_db=0.4,
        rx_feed_loss_db=0.6,
        tx_antenna_loss_db=0.5,
        rx_antenna_loss_db=0.5,
        radome_one_way_loss_db=0.8,
        chirp_frequency_error_rms_hz=5e3,
    )
    b = make_radar(losses).link_budget(target.car(), GEOM)
    items = dict(b.system_losses_db)
    assert items.pop("noise_figure_derating") == 1.5
    assert np.isclose(sum(items.values()), b.system_loss_db, atol=1e-12)


@pytest.mark.parametrize("value", [-0.1, math.nan, math.inf])
def test_invalid_losses_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        SystemLosses(rx_feed_loss_db=value)
    with pytest.raises(ValueError):
        SystemLosses(chirp_frequency_error_rms_hz=value)
