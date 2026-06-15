"""Shared typing helpers for the radar range package."""

from __future__ import annotations

from typing import Sequence, TypeAlias, cast

import numpy as np
from numpy.typing import NDArray

FloatArray: TypeAlias = NDArray[np.float64]
ArrayLikeFloat: TypeAlias = float | Sequence[float] | FloatArray


def as_float_array(value: ArrayLikeFloat) -> FloatArray:
    """Return *value* as a NumPy float array without modifying existing arrays."""

    return cast(FloatArray, np.asarray(value, dtype=float))
