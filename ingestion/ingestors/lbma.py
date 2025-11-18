"""LBMA vault inventory ingestor."""

import io
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ComponentType, FrequencyType, Metal, Series
from ingestion.base import Ingestor


class LBMAInventoryIngestor(Ingestor):
    """LBMA vault holdings ingestor."""

    def __init__(self, metal_symbol: str) -> None:
        """Initialize LBMA ingestor.

        Args:
            metal_symbol: Metal symbol ('XAU' for gold, 'XAG' for silver)
        """
        self.metal_symbol = metal_symbol

        # LBMA publishes monthly/quarterly vault data
        if metal_symbol == "XAU":
            url = "https://www.lbma.org.uk/gold-holdings"
            source_name = "LBMA_Gold_Vaults"
        elif metal_symbol == "XAG":
            url = "https://www.lbma.org.uk/silver-holdings"
            source_name = "LBMA_Silver_Vaults"
        else:
            raise ValueError(f"Unsupported metal: {metal_symbol}")

        super().__init__(source_name=source_name, source_url=url)
        self.series_id_cache: int | None = None

    async def parse(self, content: bytes) -> list[dict[str, Any]]:
        """Parse LBMA vault data.

        LBMA publishes data in various formats (CSV, Excel, HTML tables).
        This is a template implementation.

        Args:
            content: Raw content bytes

        Returns:
            List of observations
        """
        observations = []

        try:
            # Try parsing as CSV first
            text = content.decode("utf-8")
            df = pd.read_csv(io.StringIO(text))

            for _, row in df.iterrows():
                try:
                    # Common LBMA format: Date, Total (tonnes or oz)
                    date_col = next(
                        (col for col in df.columns if "date" in col.lower()), df.columns[0]
                    )
                    value_col = next(
                        (
                            col
                            for col in df.columns
                            if "total" in col.lower() or "oz" in col.lower()
                        ),
                        df.columns[1],
                    )

                    ts = pd.to_datetime(row[date_col]).to_pydatetime()
                    value = float(str(row[value_col]).replace(",", ""))

                    # Convert tonnes to ounces if needed
                    if "tonne" in value_col.lower():
                        value = value * 32150.746  # 1 tonne = 32,150.746 troy oz

                    observations.append({"ts": ts, "v": value, "meta": {"source": "LBMA"}})

                except (ValueError, KeyError, StopIteration):
                    continue

        except Exception:
            # Fallback: manual parsing or return empty
            # In production, would implement HTML scraping
            pass

        return observations

    async def get_series_id(self, session: AsyncSession) -> int:
        """Get or create series ID for LBMA inventory."""
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
                Series.component == ComponentType.INVENTORY,
                Series.source_id == self.source_id,
            )
        )
        series = result.scalar_one_or_none()

        if series is None:
            series = Series(
                metal_id=metal.metal_id,
                component=ComponentType.INVENTORY,
                unit="ounces",
                freq=FrequencyType.MONTHLY,
                source_id=self.source_id,
                description=f"LBMA {self.metal_symbol} vault holdings",
            )
            session.add(series)
            await session.commit()
            await session.refresh(series)

        self.series_id_cache = series.series_id
        return self.series_id_cache
