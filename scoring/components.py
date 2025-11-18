"""Component scoring functions."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ComponentType, Metal, Observation, Score, Series, FormulaVersion
from scoring.normalize import (
    compute_rolling_stats,
    z_score_to_percentile_score,
    compute_delta_pct,
)


# Direction flags for each component
# +1 = higher value means tighter liquidity
# -1 = lower value means tighter liquidity (inverted)
COMPONENT_DIRECTIONS = {
    ComponentType.INVENTORY: -1,  # Lower inventory = tighter
    ComponentType.ETF_FLOW: -1,  # Outflows (negative) = tighter
    ComponentType.TERM: 1,  # Backwardation (positive basis) = tighter
    ComponentType.COT: -1,  # Lower spec net long = tighter
    ComponentType.PREMIUM: 1,  # Higher premium = tighter
    ComponentType.FX: -1,  # Lower USD = tighter (for precious metals)
}

# Window sizes for rolling stats (in days)
WINDOW_SIZES = {
    ComponentType.INVENTORY: 252,  # 1 year
    ComponentType.ETF_FLOW: 252,
    ComponentType.TERM: 252,
    ComponentType.COT: 156,  # ~3 years of weekly data
    ComponentType.PREMIUM: 252,
    ComponentType.FX: 252,
}


async def get_series_observations(
    session: AsyncSession,
    metal_id: int,
    component: ComponentType,
    lookback_days: int = 365,
) -> list[tuple[datetime, float]]:
    """Get recent observations for a component.

    Args:
        session: Database session
        metal_id: Metal ID
        component: Component type
        lookback_days: Number of days to look back

    Returns:
        List of (timestamp, value) tuples sorted by time
    """
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    # Get series for this metal and component
    result = await session.execute(
        select(Series).where(Series.metal_id == metal_id, Series.component == component)
    )
    series_list = result.scalars().all()

    if not series_list:
        return []

    # Get observations from all series (there may be multiple sources)
    # Use the most recent value per day if multiple sources
    observations = []
    for series in series_list:
        result = await session.execute(
            select(Observation.ts, Observation.v)
            .where(Observation.series_id == series.series_id, Observation.ts >= cutoff)
            .order_by(Observation.ts)
        )
        observations.extend(result.all())

    # Sort by timestamp
    observations.sort(key=lambda x: x[0])

    return observations


async def score_component(
    session: AsyncSession,
    metal_id: int,
    component: ComponentType,
    formula_id: int,
    ts: datetime | None = None,
) -> dict[str, Any] | None:
    """Score a single component.

    Args:
        session: Database session
        metal_id: Metal ID
        component: Component type
        formula_id: Formula version ID
        ts: Timestamp to score (defaults to latest)

    Returns:
        Dictionary with score data or None if insufficient data
    """
    # Get observations
    observations = await get_series_observations(session, metal_id, component)

    if len(observations) < 30:  # Minimum 30 data points
        return None

    # Get window size for this component
    window_size = WINDOW_SIZES.get(component, 252)

    # Extract values
    timestamps = [obs[0] for obs in observations]
    values = [float(obs[1]) for obs in observations]

    # Get current value (either specified ts or latest)
    if ts is None:
        current_value = values[-1]
        current_ts = timestamps[-1]
    else:
        # Find closest timestamp
        idx = min(range(len(timestamps)), key=lambda i: abs(timestamps[i] - ts))
        current_value = values[idx]
        current_ts = timestamps[idx]

    # Compute rolling stats up to current point
    idx = timestamps.index(current_ts)
    historical_values = values[: idx + 1]

    stats = compute_rolling_stats(historical_values, window_size=window_size)

    # Get direction for this component
    direction = COMPONENT_DIRECTIONS.get(component, 1)

    # Compute score
    score = z_score_to_percentile_score(
        value=current_value, mean=stats["mean"], std=stats["std"], direction=direction
    )

    return {
        "metal_id": metal_id,
        "component": component,
        "ts": current_ts,
        "s": score,
        "v": current_value,
        "window": stats,
        "formula_id": formula_id,
    }


async def compute_all_component_scores(
    session: AsyncSession, metal_id: int, formula_id: int, ts: datetime | None = None
) -> dict[ComponentType, dict[str, Any]]:
    """Compute scores for all components of a metal.

    Args:
        session: Database session
        metal_id: Metal ID
        formula_id: Formula version ID
        ts: Timestamp to score (defaults to latest)

    Returns:
        Dictionary mapping component types to score data
    """
    scores = {}

    # Score each component
    for component in [
        ComponentType.INVENTORY,
        ComponentType.ETF_FLOW,
        ComponentType.TERM,
        ComponentType.COT,
        ComponentType.PREMIUM,
    ]:
        score_data = await score_component(session, metal_id, component, formula_id, ts)
        if score_data:
            scores[component] = score_data

    return scores


async def save_component_score(session: AsyncSession, score_data: dict[str, Any]) -> None:
    """Save component score to database.

    Args:
        session: Database session
        score_data: Score data dictionary
    """
    score = Score(
        metal_id=score_data["metal_id"],
        component=score_data["component"],
        ts=score_data["ts"],
        s=score_data["s"],
        v=score_data["v"],
        window=score_data["window"],
        formula_id=score_data["formula_id"],
    )

    # Upsert using merge
    await session.merge(score)
    await session.commit()


async def score_all_components_and_save(
    session: AsyncSession, metal_id: int, formula_id: int, ts: datetime | None = None
) -> dict[ComponentType, int]:
    """Compute and save all component scores.

    Args:
        session: Database session
        metal_id: Metal ID
        formula_id: Formula version ID
        ts: Timestamp to score (defaults to latest)

    Returns:
        Dictionary mapping components to their scores
    """
    scores_dict = await compute_all_component_scores(session, metal_id, formula_id, ts)

    component_scores = {}

    for component, score_data in scores_dict.items():
        await save_component_score(session, score_data)
        component_scores[component] = score_data["s"]

    return component_scores
