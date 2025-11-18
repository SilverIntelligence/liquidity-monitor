"""ETF data extractor with retries and raw caching."""

import hashlib
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


class ETFExtractor:
    """Extract ETF holdings data from various sources."""

    def __init__(self, user_agent: str = "WallStreetSilver-LiquidityMonitor/0.1") -> None:
        """Initialize extractor.

        Args:
            user_agent: HTTP User-Agent string
        """
        self.user_agent = user_agent
        self.session: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ETFExtractor":
        """Async context manager entry."""
        self.session = httpx.AsyncClient(
            timeout=30.0, follow_redirects=True, headers={"User-Agent": self.user_agent}
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        if self.session:
            await self.session.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10), reraise=True)
    async def extract_gld(self) -> dict[str, Any]:
        """Extract GLD holdings.

        Returns:
            Raw response with metadata
        """
        url = "https://www.spdrgoldshares.com/assets/dynamic/GLD/GLD_US_archive_EN.csv"

        if not self.session:
            raise RuntimeError("Extractor not initialized - use async context manager")

        response = await self.session.get(url)
        response.raise_for_status()

        content = response.content
        checksum = hashlib.sha256(content).hexdigest()

        return {
            "source": "GLD",
            "url": url,
            "content": content,
            "checksum": checksum,
            "extracted_at": datetime.utcnow(),
            "http_status": response.status_code,
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10), reraise=True)
    async def extract_slv(self) -> dict[str, Any]:
        """Extract SLV holdings.

        Returns:
            Raw response with metadata
        """
        url = "https://www.ishares.com/us/products/239855/fund/1467271812596.ajax?fileType=csv&fileName=SLV_holdings&dataType=fund"

        if not self.session:
            raise RuntimeError("Extractor not initialized")

        response = await self.session.get(url)
        response.raise_for_status()

        content = response.content
        checksum = hashlib.sha256(content).hexdigest()

        return {
            "source": "SLV",
            "url": url,
            "content": content,
            "checksum": checksum,
            "extracted_at": datetime.utcnow(),
            "http_status": response.status_code,
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10), reraise=True)
    async def extract_pslv(self) -> dict[str, Any]:
        """Extract PSLV holdings (Sprott Physical Silver Trust).

        Returns:
            Raw response with metadata
        """
        url = "https://sprott.com/investment-strategies/physical-bullion-trusts/silver/"

        if not self.session:
            raise RuntimeError("Extractor not initialized")

        response = await self.session.get(url)
        response.raise_for_status()

        content = response.content
        checksum = hashlib.sha256(content).hexdigest()

        return {
            "source": "PSLV",
            "url": url,
            "content": content,
            "checksum": checksum,
            "extracted_at": datetime.utcnow(),
            "http_status": response.status_code,
        }
