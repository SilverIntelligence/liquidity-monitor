"""CFTC Commitments of Traders (CoT) ingestor."""

import io
import zipfile
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ComponentType, FrequencyType, Metal, Series
from ingestion.base import Ingestor


class CFTCCoTIngestor(Ingestor):
    """CFTC Commitments of Traders ingestor."""

    def __init__(self, metal_symbol: str) -> None:
        """Initialize CFTC CoT ingestor.

        Args:
            metal_symbol: Metal symbol ('XAU' for gold, 'XAG' for silver)
        """
        self.metal_symbol = metal_symbol

        # CFTC publishes weekly CoT reports
        # Using the disaggregated futures-only report
        url = "https://www.cftc.gov/files/dea/history/fut_disagg_txt_hist_2006.zip"
        source_name = f"CFTC_CoT_{metal_symbol}"

        super().__init__(source_name=source_name, source_url=url)
        self.series_id_cache: int | None = None

        # CFTC commodity codes
        # Gold: 088691 (Commodity Exchange Inc.)
        # Silver: 084691 (Commodity Exchange Inc.)
        self.cftc_code = "088691" if metal_symbol == "XAU" else "084691"

    async def parse(self, content: bytes) -> list[dict[str, Any]]:
        """Parse CFTC CoT data.

        The data comes as a ZIP file containing a TXT/CSV file.

        Args:
            content: Raw ZIP bytes

        Returns:
            List of observations with net managed money positioning
        """
        observations = []

        try:
            # Extract ZIP file
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                # Get the first TXT file
                txt_files = [f for f in zf.namelist() if f.endswith(".txt")]
                if not txt_files:
                    return []

                with zf.open(txt_files[0]) as f:
                    df = pd.read_csv(f, low_memory=False)

            # Filter for our commodity
            df = df[df["CFTC_Commodity_Code"] == self.cftc_code]

            # Parse each week's report
            for _, row in df.iterrows():
                try:
                    # Report date
                    date_str = str(row["Report_Date_as_YYYY-MM-DD"])
                    ts = pd.to_datetime(date_str).to_pydatetime()

                    # Calculate net managed money (Money Manager) positioning
                    # Net = Long - Short
                    mm_long = float(row.get("M_Money_Positions_Long_All", 0))
                    mm_short = float(row.get("M_Money_Positions_Short_All", 0))
                    net_mm = mm_long - mm_short

                    # Also get dealer (Dealer/Intermediary) positioning
                    dealer_long = float(row.get("Dealer_Positions_Long_All", 0))
                    dealer_short = float(row.get("Dealer_Positions_Short_All", 0))
                    net_dealer = dealer_long - dealer_short

                    observations.append(
                        {
                            "ts": ts,
                            "v": net_mm,  # Use net managed money as primary value
                            "meta": {
                                "mm_long": mm_long,
                                "mm_short": mm_short,
                                "dealer_long": dealer_long,
                                "dealer_short": dealer_short,
                                "net_dealer": net_dealer,
                                "open_interest": float(row.get("Open_Interest_All", 0)),
                            },
                        }
                    )

                except (ValueError, KeyError) as e:
                    continue

        except Exception as e:
            # Return empty list on error - will be logged by ETL run
            return []

        return observations

    async def get_series_id(self, session: AsyncSession) -> int:
        """Get or create series ID for CFTC CoT."""
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
                Series.component == ComponentType.COT,
                Series.source_id == self.source_id,
            )
        )
        series = result.scalar_one_or_none()

        if series is None:
            series = Series(
                metal_id=metal.metal_id,
                component=ComponentType.COT,
                unit="contracts",
                freq=FrequencyType.WEEKLY,
                source_id=self.source_id,
                description=f"CFTC {self.metal_symbol} net managed money positioning",
            )
            session.add(series)
            await session.commit()
            await session.refresh(series)

        self.series_id_cache = series.series_id
        return self.series_id_cache
