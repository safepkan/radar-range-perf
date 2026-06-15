from __future__ import annotations

import numpy as np

from radar_range.units import db_to_linear, dbm_to_w, linear_to_db, w_to_dbm


def test_db_roundtrip() -> None:
    values_db = np.asarray([-10.0, 0.0, 3.0, 20.0])
    np.testing.assert_allclose(linear_to_db(db_to_linear(values_db)), values_db)


def test_dbm_roundtrip() -> None:
    values_dbm = np.asarray([-30.0, 0.0, 13.0])
    np.testing.assert_allclose(w_to_dbm(dbm_to_w(values_dbm)), values_dbm)
