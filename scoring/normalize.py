"""Normalization utilities for scoring engine."""

from typing import Any

import numpy as np
from scipy import stats


def percentile_from_z(z: float) -> float:
    """Convert z-score to percentile using standard normal distribution.

    Args:
        z: Z-score value

    Returns:
        Percentile value between 0 and 1
    """
    return float(stats.norm.cdf(z))


def clamp_sigma(sigma: float, min_sigma: float = 0.01) -> float:
    """Clamp standard deviation to minimum value to avoid division by zero.

    Args:
        sigma: Standard deviation
        min_sigma: Minimum allowed sigma

    Returns:
        Clamped sigma value
    """
    return max(sigma, min_sigma)


def compute_rolling_stats(
    values: list[float], window_size: int = 252
) -> dict[str, float]:
    """Compute rolling window statistics.

    Args:
        values: List of values (newest last)
        window_size: Rolling window size (default 252 trading days)

    Returns:
        Dictionary with mean, std, min, max
    """
    if not values:
        return {"mean": 0.0, "std": 1.0, "min": 0.0, "max": 0.0, "count": 0}

    arr = np.array(values[-window_size:])

    return {
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "count": len(arr),
    }


def z_score_to_percentile_score(
    value: float, mean: float, std: float, direction: int = 1
) -> int:
    """Convert a value to 0-100 score using z-score and percentile.

    Args:
        value: Current value
        mean: Rolling window mean
        std: Rolling window standard deviation
        direction: +1 if higher value means tighter liquidity,
                  -1 if lower value means tighter liquidity

    Returns:
        Score between 0 and 100
    """
    # Clamp sigma to avoid division by zero
    std = clamp_sigma(std)

    # Compute z-score
    z = (value - mean) / std

    # Apply direction
    if direction < 0:
        z = -z

    # Convert to percentile
    percentile = percentile_from_z(z)

    # Scale to 0-100 and round
    score = int(round(percentile * 100))

    # Clamp to [0, 100]
    return max(0, min(100, score))


def compute_delta_pct(current: float, previous: float) -> float:
    """Compute percentage change.

    Args:
        current: Current value
        previous: Previous value

    Returns:
        Percentage change
    """
    if previous == 0:
        return 0.0

    return ((current - previous) / abs(previous)) * 100


def exponential_moving_average(
    values: list[float], alpha: float = 0.1
) -> float:
    """Compute exponential moving average.

    Args:
        values: List of values (newest last)
        alpha: Smoothing factor (0 to 1)

    Returns:
        EMA value
    """
    if not values:
        return 0.0

    ema = values[0]
    for value in values[1:]:
        ema = alpha * value + (1 - alpha) * ema

    return ema
