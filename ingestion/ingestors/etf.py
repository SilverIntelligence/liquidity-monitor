"""ETF holdings ingestors."""

import csv
import io
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup
import pandas as pd

from ingestion.base import BaseETFIngestor


class GLDIngestor(BaseETFIngestor):
    """SPDR Gold Shares (GLD) holdings ingestor."""

    def __init__(self) -> None:
        """Initialize GLD ingestor."""
        super().__init__(
            etf_symbol="GLD",
            metal_symbol="XAU",
            source_url="https://www.spdrgoldshares.com/assets/dynamic/GLD/GLD_US_archive_EN.csv",
        )

    async def parse(self, content: bytes) -> list[dict[str, Any]]:
        """Parse GLD CSV data.

        Expected format: Date, Tonnes, Ounces, Value

        Args:
            content: Raw CSV bytes

        Returns:
            List of observations
        """
        text = content.decode("utf-8")
        df = pd.read_csv(io.StringIO(text))

        observations = []
        for _, row in df.iterrows():
            try:
                # Parse date (format may vary, try common formats)
                date_str = str(row["Date"]).strip()
                ts = pd.to_datetime(date_str).to_pydatetime()

                # Get ounces value
                ounces = float(row["Ounces"])

                observations.append(
                    {
                        "ts": ts,
                        "v": ounces,
                        "meta": {
                            "tonnes": float(row.get("Tonnes", 0)),
                            "value": float(row.get("Value", 0)) if "Value" in row else None,
                        },
                    }
                )
            except (ValueError, KeyError) as e:
                # Skip malformed rows
                continue

        return observations


class IAUIngestor(BaseETFIngestor):
    """iShares Gold Trust (IAU) holdings ingestor."""

    def __init__(self) -> None:
        """Initialize IAU ingestor."""
        super().__init__(
            etf_symbol="IAU",
            metal_symbol="XAU",
            source_url="https://www.ishares.com/us/products/239561/fund/1467271812596.ajax?fileType=csv&fileName=IAU_holdings&dataType=fund",
        )

    async def parse(self, content: bytes) -> list[dict[str, Any]]:
        """Parse IAU CSV data.

        Args:
            content: Raw CSV bytes

        Returns:
            List of observations
        """
        text = content.decode("utf-8")
        lines = text.split("\n")

        # IAU CSV has metadata at the top, find where actual data starts
        data_start = 0
        for i, line in enumerate(lines):
            if "as of" in line.lower() or "holdings" in line.lower():
                # Try to extract date from this line
                continue
            if line.strip().startswith("Fund Name") or "ticker" in line.lower():
                data_start = i
                break

        # Parse the data section
        if data_start > 0:
            csv_data = "\n".join(lines[data_start:])
            df = pd.read_csv(io.StringIO(csv_data))

            # Look for gold holdings row
            observations = []
            for _, row in df.iterrows():
                if "gold" in str(row.get("Name", "")).lower():
                    # Extract ounces from the holdings
                    # Note: IAU structure may vary, this is a template
                    ts = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                    ounces = float(row.get("Market Value", 0)) / 2000.0  # Approximate

                    observations.append({"ts": ts, "v": ounces, "meta": {"source": "IAU"}})
                    break

            return observations

        return []


class SLVIngestor(BaseETFIngestor):
    """iShares Silver Trust (SLV) holdings ingestor."""

    def __init__(self) -> None:
        """Initialize SLV ingestor."""
        super().__init__(
            etf_symbol="SLV",
            metal_symbol="XAG",
            source_url="https://www.ishares.com/us/products/239855/fund/1467271812596.ajax?fileType=csv&fileName=SLV_holdings&dataType=fund",
        )

    async def parse(self, content: bytes) -> list[dict[str, Any]]:
        """Parse SLV CSV data.

        Args:
            content: Raw CSV bytes

        Returns:
            List of observations
        """
        text = content.decode("utf-8")
        lines = text.split("\n")

        # Similar to IAU, find data start
        data_start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("Fund Name") or "ticker" in line.lower():
                data_start = i
                break

        if data_start > 0:
            csv_data = "\n".join(lines[data_start:])
            df = pd.read_csv(io.StringIO(csv_data))

            observations = []
            for _, row in df.iterrows():
                if "silver" in str(row.get("Name", "")).lower():
                    ts = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                    ounces = float(row.get("Market Value", 0)) / 25.0  # Approximate

                    observations.append({"ts": ts, "v": ounces, "meta": {"source": "SLV"}})
                    break

            return observations

        return []


class SIVRIngestor(BaseETFIngestor):
    """Aberdeen Standard Physical Silver Shares ETF (SIVR) holdings ingestor."""

    def __init__(self) -> None:
        """Initialize SIVR ingestor."""
        super().__init__(
            etf_symbol="SIVR",
            metal_symbol="XAG",
            source_url="https://www.abrdn.com/en-us/investor/funds-and-prices/etf/sivr",
        )

    async def parse(self, content: bytes) -> list[dict[str, Any]]:
        """Parse SIVR web page data.

        Args:
            content: Raw HTML bytes

        Returns:
            List of observations
        """
        soup = BeautifulSoup(content, "html.parser")

        # Look for holdings data in the page
        # This is a template - actual implementation depends on page structure
        observations = []

        # Find elements containing ounces data
        # Example: look for specific div or table with holdings
        text = soup.get_text()
        lines = text.split("\n")

        for line in lines:
            if "ounces" in line.lower() or "oz" in line.lower():
                # Try to extract numeric value
                import re

                numbers = re.findall(r"[\d,]+\.?\d*", line)
                if numbers:
                    try:
                        ounces = float(numbers[0].replace(",", ""))
                        ts = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

                        observations.append({"ts": ts, "v": ounces, "meta": {"source": "SIVR"}})
                        break
                    except ValueError:
                        continue

        return observations
