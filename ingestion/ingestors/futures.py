"""Futures settlement prices ingestor."""

import io
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ComponentType, FrequencyType, Metal, Series
from ingestion.base import Ingestor


class FuturesSettlementIngestor(Ingestor):
    """Futures settlement prices and term structure ingestor."""

    def __init__(self, metal_symbol: str) -> None:
        """Initialize futures settlement ingestor.

        Args:
            metal_symbol: Metal symbol ('XAU' for gold, 'XAG' for silver)
        """
        self.metal_symbol = metal_symbol

        # CME provides settlement data
        # This is a template - actual source may require authentication or paid API
        if metal_symbol == "XAU":
            url = "https://www.cmegroup.com/CmeWS/mvc/Settlements/Futures/Settlements/190/FUT?tradeDate="
            source_name = "CME_Gold_Futures"
            self.contract_code = "GC"  # Gold futures
        elif metal_symbol == "XAG":
            url = "https://www.cmegroup.com/CmeWS/mvc/Settlements/Futures/Settlements/191/FUT?tradeDate="
            source_name = "CME_Silver_Futures"
            self.contract_code = "SI"  # Silver futures
        else:
            raise ValueError(f"Unsupported metal: {metal_symbol}")

        super().__init__(source_name=source_name, source_url=url)
        self.series_id_cache: int | None = None

    async def fetch(self, url: str | None = None) -> tuple[bytes, int]:
        """Fetch futures data for today's date.

        Args:
            url: Optional URL override

        Returns:
            Tuple of (content, status_code)
        """
        # Append today's date to URL
        today = datetime.utcnow().strftime("%Y%m%d")
        fetch_url = (url or self.source_url) + today

        return await super().fetch(fetch_url)

    async def parse(self, content: bytes) -> list[dict[str, Any]]:
        """Parse futures settlement data.

        Calculate term structure: basis = front month - spot proxy.

        Args:
            content: Raw JSON/CSV bytes

        Returns:
            List of observations with term structure metrics
        """
        observations = []

        try:
            # Try parsing as JSON (CME format)
            import json

            data = json.loads(content.decode("utf-8"))

            # Extract settlement prices for front 3 contracts
            settlements = data.get("settlements", [])
            if not settlements:
                return []

            # Get front month settlement
            front_month = settlements[0] if settlements else None
            second_month = settlements[1] if len(settlements) > 1 else None
            third_month = settlements[2] if len(settlements) > 2 else None

            if front_month:
                ts = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                settle_price = float(front_month.get("settle", 0))

                # Calculate term structure metrics
                # Basis = front month - second month (positive = backwardation, negative = contango)
                basis = 0.0
                if second_month:
                    second_settle = float(second_month.get("settle", 0))
                    basis = settle_price - second_settle

                observations.append(
                    {
                        "ts": ts,
                        "v": basis,  # Use basis as primary value
                        "meta": {
                            "front_settle": settle_price,
                            "second_settle": float(second_month.get("settle", 0))
                            if second_month
                            else None,
                            "third_settle": float(third_month.get("settle", 0))
                            if third_month
                            else None,
                            "front_volume": front_month.get("volume", 0),
                            "open_interest": front_month.get("openInterest", 0),
                        },
                    }
                )

        except json.JSONDecodeError:
            # Fallback: try CSV format
            try:
                text = content.decode("utf-8")
                df = pd.read_csv(io.StringIO(text))

                # Find front month contract and calculate basis
                # Implementation depends on CSV structure
                pass

            except Exception:
                pass

        return observations

    async def get_series_id(self, session: AsyncSession) -> int:
        """Get or create series ID for futures term structure."""
        if self.series_id_cache is not None:
            return self.series_id_cache

        # Get metal_id
        result = await session.execute(select(Metal).where(Metal.symbol == self.metal_symbol))
        metal = result.scalar_one_or_none()

        if metal is None:
            raise ValueError(f"Metal {self.metal_symbol} not found in database")

        # Get or create series
        result = await session.execute(
            select(Series).where(
                Series.metal_id == metal.metal_id,
                Series.component == ComponentType.TERM,
                Series.source_id == self.source_id,
            )
        )
        series = result.scalar_one_or_none()

        if series is None:
            series = Series(
                metal_id=metal.metal_id,
                component=ComponentType.TERM,
                unit="usd",
                freq=FrequencyType.DAILY,
                source_id=self.source_id,
                description=f"CME {self.metal_symbol} futures term structure (basis)",
            )
            session.add(series)
            await session.commit()
            await session.refresh(series)

        self.series_id_cache = series.series_id
        return self.series_id_cache
