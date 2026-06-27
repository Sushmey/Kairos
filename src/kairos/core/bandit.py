"""Thompson sampling helpers."""

from __future__ import annotations

import numpy as np


def thompson_sample(alpha: float, beta: float) -> float:
    """Sample engagement weight from Beta(α, β)."""
    return float(np.random.beta(max(alpha, 1e-6), max(beta, 1e-6)))
