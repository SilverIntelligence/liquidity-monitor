"""Liquidity index API endpoints."""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import csv
import io

from db.models import Composite, ComponentType, Metal, Score, ETLRun
from db.session import get_db

router = APIRouter()


@router.get("/status")
async def get_status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Get overall system status.

    Args:
        db: Database session

    Returns:
        System status with last update times
    """
    # Get latest composite for each metal
    metals_status = {}

    metals_result = await db.execute(select(Metal))
    metals = metals_result.scalars().all()

    for metal in metals:
        # Get latest composite
        composite_result = await db.execute(
            select(Composite)
            .where(Composite.metal_id == metal.metal_id)
            .order_by(Composite.ts.desc())
            .limit(1)
        )
        latest_composite = composite_result.scalar_one_or_none()

        # Get latest ETL runs
        etl_result = await db.execute(
            select(ETLRun).order_by(ETLRun.finished_at.desc()).limit(5)
        )
        recent_etls = etl_result.scalars().all()

        metals_status[metal.symbol] = {
            "name": metal.name,
            "last_update": latest_composite.ts.isoformat() if latest_composite else None,
            "score": latest_composite.s if latest_composite else None,
            "degraded": latest_composite.degraded if latest_composite else False,
        }

    return {
        "ok": True,
        "timestamp": datetime.utcnow().isoformat(),
        "metals": metals_status,
    }


@router.get("/metal/{symbol}/index/latest")
async def get_latest_index(
    symbol: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get latest liquidity index for a metal.

    Args:
        symbol: Metal symbol (e.g., 'XAU', 'XAG')
        db: Database session

    Returns:
        Latest index data with components
    """
    # Get metal
    metal_result = await db.execute(select(Metal).where(Metal.symbol == symbol.upper()))
    metal = metal_result.scalar_one_or_none()

    if metal is None:
        raise HTTPException(status_code=404, detail=f"Metal {symbol} not found")

    # Get latest composite
    composite_result = await db.execute(
        select(Composite)
        .where(Composite.metal_id == metal.metal_id)
        .order_by(Composite.ts.desc())
        .limit(1)
    )
    composite = composite_result.scalar_one_or_none()

    if composite is None:
        raise HTTPException(status_code=404, detail=f"No data available for {symbol}")

    # Get component scores at the same timestamp
    scores_result = await db.execute(
        select(Score).where(
            Score.metal_id == metal.metal_id,
            Score.ts <= composite.ts,
        ).order_by(Score.component, Score.ts.desc())
    )

    # Get latest score for each component
    component_scores = {}
    seen_components = set()

    for score in scores_result.scalars():
        if score.component not in seen_components:
            component_scores[score.component.value] = {
                "score": score.s,
                "value": float(score.v),
                "timestamp": score.ts.isoformat(),
            }
            seen_components.add(score.component)

    return {
        "metal": symbol.upper(),
        "timestamp": composite.ts.isoformat(),
        "liquidity_index": composite.s,
        "components": composite.components,
        "component_details": component_scores,
        "formula_id": composite.formula_id,
        "degraded": composite.degraded,
    }


@router.get("/metal/{symbol}/index/history")
async def get_index_history(
    symbol: str,
    start: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    interval: str = Query("d", description="Interval: h (hour), d (day), w (week)"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get historical liquidity index data.

    Args:
        symbol: Metal symbol
        start: Start date
        end: End date
        interval: Data interval
        db: Database session

    Returns:
        Historical index data
    """
    # Get metal
    metal_result = await db.execute(select(Metal).where(Metal.symbol == symbol.upper()))
    metal = metal_result.scalar_one_or_none()

    if metal is None:
        raise HTTPException(status_code=404, detail=f"Metal {symbol} not found")

    # Parse dates
    end_date = datetime.fromisoformat(end) if end else datetime.utcnow()
    start_date = (
        datetime.fromisoformat(start) if start else end_date - timedelta(days=30)
    )

    # Get composites
    composites_result = await db.execute(
        select(Composite)
        .where(
            Composite.metal_id == metal.metal_id,
            Composite.ts >= start_date,
            Composite.ts <= end_date,
        )
        .order_by(Composite.ts)
    )
    composites = composites_result.scalars().all()

    # Format data
    history = [
        {
            "timestamp": c.ts.isoformat(),
            "liquidity_index": c.s,
            "degraded": c.degraded,
        }
        for c in composites
    ]

    return {
        "metal": symbol.upper(),
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "interval": interval,
        "count": len(history),
        "data": history,
    }


@router.get("/metal/{symbol}/components/{component}/history")
async def get_component_history(
    symbol: str,
    component: str,
    start: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get historical component score data.

    Args:
        symbol: Metal symbol
        component: Component name (inventory, etf_flow, term, cot, premium)
        start: Start date
        end: End date
        db: Database session

    Returns:
        Historical component data
    """
    # Get metal
    metal_result = await db.execute(select(Metal).where(Metal.symbol == symbol.upper()))
    metal = metal_result.scalar_one_or_none()

    if metal is None:
        raise HTTPException(status_code=404, detail=f"Metal {symbol} not found")

    # Parse component
    try:
        component_enum = ComponentType[component.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid component: {component}")

    # Parse dates
    end_date = datetime.fromisoformat(end) if end else datetime.utcnow()
    start_date = (
        datetime.fromisoformat(start) if start else end_date - timedelta(days=30)
    )

    # Get scores
    scores_result = await db.execute(
        select(Score)
        .where(
            Score.metal_id == metal.metal_id,
            Score.component == component_enum,
            Score.ts >= start_date,
            Score.ts <= end_date,
        )
        .order_by(Score.ts)
    )
    scores = scores_result.scalars().all()

    # Format data
    history = [
        {
            "timestamp": s.ts.isoformat(),
            "score": s.s,
            "value": float(s.v),
        }
        for s in scores
    ]

    return {
        "metal": symbol.upper(),
        "component": component,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "count": len(history),
        "data": history,
    }


@router.get("/download/{symbol}/composite.csv")
async def download_composite_csv(
    symbol: str,
    start: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Download composite index data as CSV.

    Args:
        symbol: Metal symbol
        start: Start date
        end: End date
        db: Database session

    Returns:
        CSV file stream
    """
    # Get metal
    metal_result = await db.execute(select(Metal).where(Metal.symbol == symbol.upper()))
    metal = metal_result.scalar_one_or_none()

    if metal is None:
        raise HTTPException(status_code=404, detail=f"Metal {symbol} not found")

    # Parse dates
    end_date = datetime.fromisoformat(end) if end else datetime.utcnow()
    start_date = (
        datetime.fromisoformat(start) if start else end_date - timedelta(days=365)
    )

    # Get composites
    composites_result = await db.execute(
        select(Composite)
        .where(
            Composite.metal_id == metal.metal_id,
            Composite.ts >= start_date,
            Composite.ts <= end_date,
        )
        .order_by(Composite.ts)
    )
    composites = composites_result.scalars().all()

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "liquidity_index", "degraded", "formula_id"])

    for c in composites:
        writer.writerow([c.ts.isoformat(), c.s, c.degraded, c.formula_id])

    # Create streaming response
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={symbol}_composite_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
        },
    )
