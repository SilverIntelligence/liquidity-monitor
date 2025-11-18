"""Liquidity index computation with z-score and stale component handling."""

import json
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from scipy import stats
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class LiquidityIndexComputer:
    """Compute hourly liquidity index with degraded mode handling."""

    def __init__(self, session: AsyncSession, window_days: int = 180) -> None:
        """Initialize computer.

        Args:
            session: Database session
            window_days: Rolling window for z-score (default 180 days)
        """
        self.session = session
        self.window_days = window_days
        self.staleness_threshold_hours = 24

    async def compute_index(self, ts: datetime) -> dict[str, Any]:
        """Compute liquidity index at given timestamp.

        Args:
            ts: Timestamp to compute index for

        Returns:
            Index data with components and stale flags
        """
        # Get component values
        components = await self._get_component_values(ts)

        # Check staleness
        stale_components = self._check_staleness(components, ts)

        # Compute z-scores for each component
        z_scores = await self._compute_z_scores(components)

        # Reweight if components missing
        weights = self._reweight_components(z_scores)

        # Compute weighted average
        li_z = sum(z * w for z, w in zip(z_scores.values(), weights.values()) if z is not None)

        # Raw index (0-100 scale from z-score)
        li_raw = self._z_to_raw(li_z)

        return {
            "ts": ts,
            "li_raw": li_raw,
            "li_z": li_z,
            "components_json": {
                "z_scores": {k: float(v) if v is not None else None for k, v in z_scores.items()},
                "weights": {k: float(v) for k, v in weights.items()},
                "values": {k: v["value"] for k, v in components.items() if v},
            },
            "stale_components": stale_components,
            "version": "v0",
        }

    async def _get_component_values(self, ts: datetime) -> dict[str, dict[str, Any]]:
        """Get latest values for all components.

        Args:
            ts: Reference timestamp

        Returns:
            Component values with metadata
        """
        components = {}

        # ETF flows - net change in last 24h
        etf_query = """
            SELECT SUM(net_shares) as total_shares, MAX(ds) as latest_date
            FROM liquidity.etf_flows
            WHERE ds >= :cutoff_date
        """
        result = await self.session.execute(
            text(etf_query), {"cutoff_date": (ts - timedelta(days=1)).date()}
        )
        row = result.first()
        if row and row.total_shares:
            components["etf_flow"] = {
                "value": float(row.total_shares),
                "last_updated": datetime.combine(row.latest_date, datetime.min.time()),
            }

        # Inventory - latest total
        inv_query = """
            SELECT SUM(tonnes_oz) as total_oz, MAX(ds) as latest_date
            FROM liquidity.inventory
            WHERE ds = (SELECT MAX(ds) FROM liquidity.inventory WHERE ds <= :ref_date)
        """
        result = await self.session.execute(text(inv_query), {"ref_date": ts.date()})
        row = result.first()
        if row and row.total_oz:
            components["inventory"] = {
                "value": float(row.total_oz),
                "last_updated": datetime.combine(row.latest_date, datetime.min.time()),
            }

        # Futures - latest OI
        fut_query = """
            SELECT SUM(open_interest) as total_oi, MAX(ds) as latest_date
            FROM liquidity.futures_positioning
            WHERE ds = (SELECT MAX(ds) FROM liquidity.futures_positioning WHERE ds <= :ref_date)
        """
        result = await self.session.execute(text(fut_query), {"ref_date": ts.date()})
        row = result.first()
        if row and row.total_oi:
            components["futures_oi"] = {
                "value": float(row.total_oi),
                "last_updated": datetime.combine(row.latest_date, datetime.min.time()),
            }

        return components

    def _check_staleness(
        self, components: dict[str, dict[str, Any]], ts: datetime
    ) -> dict[str, float]:
        """Check which components are stale.

        Args:
            components: Component data
            ts: Reference timestamp

        Returns:
            Stale components with hours since update
        """
        stale = {}
        threshold = timedelta(hours=self.staleness_threshold_hours)

        for name, data in components.items():
            if data:
                age = ts - data["last_updated"]
                if age > threshold:
                    stale[name] = age.total_seconds() / 3600.0

        return stale

    async def _compute_z_scores(self, components: dict[str, dict[str, Any]]) -> dict[str, float | None]:
        """Compute z-scores for each component.

        Args:
            components: Component values

        Returns:
            Z-scores dict
        """
        z_scores = {}

        for name, data in components.items():
            if not data:
                z_scores[name] = None
                continue

            # Get historical data for window
            historical = await self._get_historical_values(name, self.window_days)

            if len(historical) < 30:  # Minimum data points
                z_scores[name] = 0.0
                continue

            # Compute z-score
            mean = np.mean(historical)
            std = np.std(historical)
            std = max(std, 0.01)  # Prevent division by zero

            z = (data["value"] - mean) / std
            z_scores[name] = float(z)

        return z_scores

    async def _get_historical_values(self, component: str, days: int) -> list[float]:
        """Get historical values for a component.

        Args:
            component: Component name
            days: Number of days to look back

        Returns:
            List of historical values
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        if component == "etf_flow":
            query = """
                SELECT SUM(net_shares) as value
                FROM liquidity.etf_flows
                WHERE ds >= :cutoff
                GROUP BY ds
                ORDER BY ds
            """
        elif component == "inventory":
            query = """
                SELECT SUM(tonnes_oz) as value
                FROM liquidity.inventory
                WHERE ds >= :cutoff
                GROUP BY ds
                ORDER BY ds
            """
        elif component == "futures_oi":
            query = """
                SELECT SUM(open_interest) as value
                FROM liquidity.futures_positioning
                WHERE ds >= :cutoff
                GROUP BY ds
                ORDER BY ds
            """
        else:
            return []

        result = await self.session.execute(text(query), {"cutoff": cutoff.date()})
        return [float(row.value) for row in result if row.value]

    def _reweight_components(self, z_scores: dict[str, float | None]) -> dict[str, float]:
        """Reweight components when some are missing.

        Args:
            z_scores: Z-scores (some may be None)

        Returns:
            Reweighted weights dict
        """
        # Default weights
        default_weights = {"etf_flow": 0.3, "inventory": 0.4, "futures_oi": 0.3}

        # Calculate total weight of available components
        available_weight = sum(w for k, w in default_weights.items() if z_scores.get(k) is not None)

        if available_weight == 0:
            return {k: 0.0 for k in default_weights}

        # Rescale weights
        weights = {
            k: w / available_weight if z_scores.get(k) is not None else 0.0
            for k, w in default_weights.items()
        }

        return weights

    def _z_to_raw(self, z: float) -> float:
        """Convert z-score to 0-100 raw index.

        Args:
            z: Z-score

        Returns:
            Raw index value (0-100)
        """
        # Use CDF to get percentile
        percentile = stats.norm.cdf(z)
        return round(percentile * 100, 2)

    async def save_index(self, index_data: dict[str, Any]) -> None:
        """Save computed index to database.

        Args:
            index_data: Index computation result
        """
        insert_sql = """
            INSERT INTO liquidity.index_hourly (ts, li_raw, li_z, components_json, stale_components, version)
            VALUES (:ts, :li_raw, :li_z, :components_json, :stale_components, :version)
            ON CONFLICT (ts) DO UPDATE SET
                li_raw = EXCLUDED.li_raw,
                li_z = EXCLUDED.li_z,
                components_json = EXCLUDED.components_json,
                stale_components = EXCLUDED.stale_components,
                version = EXCLUDED.version
        """

        await self.session.execute(
            text(insert_sql),
            {
                "ts": index_data["ts"],
                "li_raw": index_data["li_raw"],
                "li_z": index_data["li_z"],
                "components_json": json.dumps(index_data["components_json"]),
                "stale_components": json.dumps(index_data["stale_components"]),
                "version": index_data["version"],
            },
        )
        await self.session.commit()
