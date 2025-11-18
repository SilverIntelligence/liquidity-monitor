"""Composite liquidity index calculator."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Composite, ComponentType, FormulaVersion, Metal, Score


# Default weights for formula v1
DEFAULT_WEIGHTS = {
    "inventory": 0.25,
    "etf_flow": 0.20,
    "term": 0.20,
    "cot": 0.20,
    "premium": 0.15,
}


async def get_or_create_formula(
    session: AsyncSession,
    description: str = "Default liquidity index formula v1",
    weights: dict[str, float] | None = None,
) -> int:
    """Get or create a formula version.

    Args:
        session: Database session
        description: Formula description
        weights: Component weights dictionary

    Returns:
        Formula ID
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS.copy()

    # Try to find existing formula with same weights
    result = await session.execute(
        select(FormulaVersion).where(FormulaVersion.weights == weights)
    )
    formula = result.scalar_one_or_none()

    if formula is None:
        # Create new formula
        formula = FormulaVersion(description=description, weights=weights)
        session.add(formula)
        await session.commit()
        await session.refresh(formula)

    return formula.formula_id


def map_component_to_weight_key(component: ComponentType) -> str:
    """Map component enum to weight key.

    Args:
        component: Component type enum

    Returns:
        Weight key string
    """
    mapping = {
        ComponentType.INVENTORY: "inventory",
        ComponentType.ETF_FLOW: "etf_flow",
        ComponentType.TERM: "term",
        ComponentType.COT: "cot",
        ComponentType.PREMIUM: "premium",
        ComponentType.FX: "fx",
    }
    return mapping.get(component, component.value)


async def compute_composite_score(
    session: AsyncSession,
    metal_id: int,
    formula_id: int,
    ts: datetime | None = None,
    allow_partial: bool = True,
) -> dict[str, Any] | None:
    """Compute composite liquidity index.

    Args:
        session: Database session
        metal_id: Metal ID
        formula_id: Formula version ID
        ts: Timestamp (defaults to latest available)
        allow_partial: If True, compute with available components and rescale weights

    Returns:
        Dictionary with composite score data or None
    """
    # Get formula
    result = await session.execute(
        select(FormulaVersion).where(FormulaVersion.formula_id == formula_id)
    )
    formula = result.scalar_one_or_none()

    if formula is None:
        raise ValueError(f"Formula {formula_id} not found")

    weights = formula.weights

    # Get component scores
    if ts is None:
        # Get latest scores for each component
        component_scores = {}
        for component in ComponentType:
            result = await session.execute(
                select(Score)
                .where(
                    Score.metal_id == metal_id,
                    Score.component == component,
                    Score.formula_id == formula_id,
                )
                .order_by(Score.ts.desc())
                .limit(1)
            )
            score = result.scalar_one_or_none()
            if score:
                component_scores[component] = {"s": score.s, "ts": score.ts}

        # Use the most recent timestamp among all components
        if component_scores:
            composite_ts = max(s["ts"] for s in component_scores.values())
        else:
            return None
    else:
        # Get scores at specific timestamp
        composite_ts = ts
        component_scores = {}

        for component in ComponentType:
            result = await session.execute(
                select(Score).where(
                    Score.metal_id == metal_id,
                    Score.component == component,
                    Score.formula_id == formula_id,
                    Score.ts <= ts,
                ).order_by(Score.ts.desc()).limit(1)
            )
            score = result.scalar_one_or_none()
            if score:
                component_scores[component] = {"s": score.s, "ts": score.ts}

    if not component_scores:
        return None

    # Compute weighted average
    total_weight = 0.0
    weighted_sum = 0.0
    components_used = {}
    missing_components = []

    for component, score_data in component_scores.items():
        weight_key = map_component_to_weight_key(component)
        weight = weights.get(weight_key, 0.0)

        if weight > 0:
            weighted_sum += score_data["s"] * weight
            total_weight += weight
            components_used[weight_key] = {
                "score": score_data["s"],
                "weight": weight,
                "ts": score_data["ts"].isoformat(),
            }

    # Check for missing components
    for weight_key, weight in weights.items():
        if weight > 0 and weight_key not in components_used:
            missing_components.append(weight_key)

    # Determine if degraded
    degraded = len(missing_components) > 0

    if not allow_partial and degraded:
        return None

    # Rescale if partial data
    if total_weight == 0:
        return None

    composite_score = int(round(weighted_sum / total_weight))

    # Clamp to [0, 100]
    composite_score = max(0, min(100, composite_score))

    return {
        "metal_id": metal_id,
        "ts": composite_ts,
        "s": composite_score,
        "components": components_used,
        "formula_id": formula_id,
        "degraded": degraded,
        "missing_components": missing_components,
    }


async def save_composite_score(session: AsyncSession, composite_data: dict[str, Any]) -> None:
    """Save composite score to database.

    Args:
        session: Database session
        composite_data: Composite score data
    """
    composite = Composite(
        metal_id=composite_data["metal_id"],
        ts=composite_data["ts"],
        s=composite_data["s"],
        components=composite_data["components"],
        formula_id=composite_data["formula_id"],
        degraded=composite_data.get("degraded", False),
    )

    # Upsert using merge
    await session.merge(composite)
    await session.commit()


async def compute_and_save_composite(
    session: AsyncSession,
    metal_id: int,
    formula_id: int,
    ts: datetime | None = None,
) -> int | None:
    """Compute and save composite score.

    Args:
        session: Database session
        metal_id: Metal ID
        formula_id: Formula version ID
        ts: Timestamp (defaults to latest)

    Returns:
        Composite score or None
    """
    composite_data = await compute_composite_score(session, metal_id, formula_id, ts)

    if composite_data is None:
        return None

    await save_composite_score(session, composite_data)
    return composite_data["s"]


async def recompute_historical_scores(
    session: AsyncSession,
    metal_id: int,
    formula_id: int,
    start_date: datetime,
    end_date: datetime | None = None,
) -> dict[str, Any]:
    """Recompute component and composite scores for a date range.

    Used for backfilling and formula version changes.

    Args:
        session: Database session
        metal_id: Metal ID
        formula_id: Formula version ID
        start_date: Start date
        end_date: End date (defaults to now)

    Returns:
        Summary statistics
    """
    from datetime import timedelta
    from scoring.components import score_all_components_and_save

    if end_date is None:
        end_date = datetime.utcnow()

    # Iterate through each day
    current_date = start_date
    composites_computed = 0
    errors = 0

    while current_date <= end_date:
        try:
            # Score all components for this date
            await score_all_components_and_save(session, metal_id, formula_id, current_date)

            # Compute composite
            composite_score = await compute_and_save_composite(
                session, metal_id, formula_id, current_date
            )

            if composite_score is not None:
                composites_computed += 1

        except Exception as e:
            errors += 1
            # Log error but continue

        current_date += timedelta(days=1)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "composites_computed": composites_computed,
        "errors": errors,
    }
