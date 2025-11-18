"""COMEX inventory ingestor."""

import io
import re
from datetime import datetime
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ComponentType, FrequencyType, Metal, Series
from ingestion.base import Ingestor


class COMEXInventoryIngestor(Ingestor):
    """COMEX warehouse stocks ingestor."""

    def __init__(self, metal_symbol: str) -> None:
        """Initialize COMEX ingestor.

        Args:
            metal_symbol: Metal symbol ('XAU' for gold, 'XAG' for silver)
        """
        self.metal_symbol = metal_symbol

        # Different URLs for gold and silver
        if metal_symbol == "XAU":
            url = "https://www.cmegroup.com/delivery_reports/Gold_stocks.xls"
            source_name = "COMEX_Gold_Inventory"
        elif metal_symbol == "XAG":
            url = "https://www.cmegroup.com/delivery_reports/Silver_stocks.xls"
            source_name = "COMEX_Silver_Inventory"
        else:
            raise ValueError(f"Unsupported metal: {metal_symbol}")

        super().__init__(source_name=source_name, source_url=url)
        self.series_id_cache: int | None = None

    async def parse(self, content: bytes) -> list[dict[str, Any]]:
        """Parse COMEX inventory XLS/HTML data.

        Args:
            content: Raw XLS/HTML bytes

        Returns:
            List of observations
        """
        observations = []

        try:
            # Try parsing as Excel first
            df = pd.read_excel(io.BytesIO(content), sheet_name=0)

            # Find date column and inventory columns
            for _, row in df.iterrows():
                # Look for date in first column
                date_val = row.iloc[0]
                if pd.notna(date_val):
                    try:
                        ts = pd.to_datetime(date_val).to_pydatetime()

                        # Sum up all inventory columns (registered + eligible)
                        total_oz = 0.0
                        for col in row.index[1:]:
                            if pd.notna(row[col]) and isinstance(row[col], (int, float)):
                                total_oz += float(row[col])

                        if total_oz > 0:
                            observations.append(
                                {
                                    "ts": ts,
                                    "v": total_oz,
                                    "meta": {"registered": 0, "eligible": 0},  # Parse if needed
                                }
                            )
                    except (ValueError, TypeError):
                        continue

        except Exception:
            # Fallback: try parsing as HTML
            soup = BeautifulSoup(content, "html.parser")
            tables = soup.find_all("table")

            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        # Try to extract date and value
                        try:
                            date_text = cells[0].get_text().strip()
                            ts = pd.to_datetime(date_text).to_pydatetime()

                            # Sum numeric values in row
                            total_oz = 0.0
                            for cell in cells[1:]:
                                text = cell.get_text().strip().replace(",", "")
                                if text:
                                    try:
                                        total_oz += float(text)
                                    except ValueError:
                                        pass

                            if total_oz > 0:
                                observations.append({"ts": ts, "v": total_oz, "meta": {}})
                        except (ValueError, TypeError):
                            continue

        return observations

    async def get_series_id(self, session: AsyncSession) -> int:
        """Get or create series ID for COMEX inventory."""
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
                freq=FrequencyType.DAILY,
                source_id=self.source_id,
                description=f"COMEX {self.metal_symbol} warehouse stocks",
            )
            session.add(series)
            await session.commit()
            await session.refresh(series)

        self.series_id_cache = series.series_id
        return self.series_id_cache
