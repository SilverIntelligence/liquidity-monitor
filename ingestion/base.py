"""Base ingestor class for data collection."""

import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import aiohttp
import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from db.models import ETLRun, ETLStatus, Observation, Series, Source
from db.session import AsyncSessionLocal


class Ingestor(ABC):
    """Base class for all data ingestors."""

    def __init__(self, source_name: str, source_url: str, user_agent: str | None = None) -> None:
        """Initialize the ingestor.

        Args:
            source_name: Name of the data source
            source_url: URL of the data source
            user_agent: Optional user agent string
        """
        self.source_name = source_name
        self.source_url = source_url
        self.user_agent = user_agent or "WallStreetSilver-Liquidity-Monitor/0.1"
        self.source_id: int | None = None

    async def ensure_source(self, session: AsyncSession) -> int:
        """Ensure source exists in database and return its ID.

        Args:
            session: Database session

        Returns:
            Source ID
        """
        if self.source_id is not None:
            return self.source_id

        # Try to get existing source
        result = await session.execute(select(Source).where(Source.name == self.source_name))
        source = result.scalar_one_or_none()

        if source is None:
            # Create new source
            source = Source(name=self.source_name, url=self.source_url)
            session.add(source)
            await session.commit()
            await session.refresh(source)

        self.source_id = source.source_id
        return self.source_id

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True
    )
    async def fetch(self, url: str | None = None) -> tuple[bytes, int]:
        """Fetch data from the source URL with retries.

        Args:
            url: Optional URL to fetch, defaults to source_url

        Returns:
            Tuple of (raw content bytes, HTTP status code)
        """
        fetch_url = url or self.source_url
        headers = {"User-Agent": self.user_agent}

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(fetch_url, headers=headers)
            response.raise_for_status()
            return response.content, response.status_code

    @abstractmethod
    async def parse(self, content: bytes) -> list[dict[str, Any]]:
        """Parse raw content into observations.

        Args:
            content: Raw content bytes from fetch()

        Returns:
            List of observation dictionaries with keys:
            - series_id: int
            - ts: datetime
            - v: float
            - meta: dict (optional)
        """
        pass

    async def upsert(
        self, session: AsyncSession, series_id: int, observations: list[dict[str, Any]]
    ) -> int:
        """Upsert observations into database idempotently.

        Args:
            session: Database session
            series_id: Series ID
            observations: List of observation dictionaries

        Returns:
            Number of rows upserted
        """
        if not observations:
            return 0

        # Prepare data for upsert
        data = [
            {
                "series_id": series_id,
                "ts": obs["ts"],
                "v": obs["v"],
                "meta": obs.get("meta"),
                "source_revision_ts": obs.get("source_revision_ts"),
                "created_at": datetime.utcnow(),
            }
            for obs in observations
        ]

        # Upsert using PostgreSQL ON CONFLICT
        stmt = insert(Observation).values(data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["series_id", "ts"],
            set_={
                "v": stmt.excluded.v,
                "meta": stmt.excluded.meta,
                "source_revision_ts": stmt.excluded.source_revision_ts,
            },
        )

        await session.execute(stmt)
        await session.commit()
        return len(data)

    async def run(self) -> dict[str, Any]:
        """Execute the full ingestion pipeline.

        Returns:
            Dictionary with execution results
        """
        async with AsyncSessionLocal() as session:
            # Ensure source exists
            source_id = await self.ensure_source(session)

            # Create ETL run record
            etl_run = ETLRun(
                source_id=source_id, started_at=datetime.utcnow(), status=ETLStatus.RUNNING
            )
            session.add(etl_run)
            await session.commit()
            await session.refresh(etl_run)

            try:
                # Fetch data
                content, http_status = await self.fetch()

                # Compute checksum
                checksum = hashlib.sha256(content).hexdigest()

                # Parse data
                observations = await self.parse(content)

                # Get series_id (subclasses should implement this)
                series_id = await self.get_series_id(session)

                # Upsert observations
                rows = await self.upsert(session, series_id, observations)

                # Update ETL run
                etl_run.finished_at = datetime.utcnow()
                etl_run.status = ETLStatus.SUCCESS
                etl_run.rows = rows
                etl_run.http_status = http_status
                etl_run.checksum = checksum
                await session.commit()

                return {
                    "status": "success",
                    "source": self.source_name,
                    "rows": rows,
                    "checksum": checksum,
                    "etl_id": etl_run.etl_id,
                }

            except Exception as e:
                # Update ETL run with error
                etl_run.finished_at = datetime.utcnow()
                etl_run.status = ETLStatus.FAILED
                etl_run.error = str(e)
                await session.commit()

                return {
                    "status": "failed",
                    "source": self.source_name,
                    "error": str(e),
                    "etl_id": etl_run.etl_id,
                }

    @abstractmethod
    async def get_series_id(self, session: AsyncSession) -> int:
        """Get or create the series ID for this ingestor.

        Args:
            session: Database session

        Returns:
            Series ID
        """
        pass


class BaseETFIngestor(Ingestor):
    """Base class for ETF holdings ingestors."""

    def __init__(
        self,
        etf_symbol: str,
        metal_symbol: str,
        source_url: str,
        user_agent: str | None = None,
    ) -> None:
        """Initialize ETF ingestor.

        Args:
            etf_symbol: ETF symbol (e.g., 'GLD', 'SLV')
            metal_symbol: Metal symbol (e.g., 'XAU', 'XAG')
            source_url: URL to ETF holdings data
            user_agent: Optional user agent
        """
        super().__init__(
            source_name=f"{etf_symbol}_Holdings", source_url=source_url, user_agent=user_agent
        )
        self.etf_symbol = etf_symbol
        self.metal_symbol = metal_symbol
        self.series_id_cache: int | None = None

    async def get_series_id(self, session: AsyncSession) -> int:
        """Get or create series ID for this ETF."""
        if self.series_id_cache is not None:
            return self.series_id_cache

        from db.models import ComponentType, FrequencyType, Metal

        # Get metal_id
        result = await session.execute(select(Metal).where(Metal.symbol == self.metal_symbol))
        metal = result.scalar_one_or_none()

        if metal is None:
            raise ValueError(f"Metal {self.metal_symbol} not found in database")

        # Get or create series
        result = await session.execute(
            select(Series).where(
                Series.metal_id == metal.metal_id,
                Series.component == ComponentType.ETF_FLOW,
                Series.source_id == self.source_id,
            )
        )
        series = result.scalar_one_or_none()

        if series is None:
            series = Series(
                metal_id=metal.metal_id,
                component=ComponentType.ETF_FLOW,
                unit="ounces",
                freq=FrequencyType.DAILY,
                source_id=self.source_id,
                description=f"{self.etf_symbol} holdings in troy ounces",
            )
            session.add(series)
            await session.commit()
            await session.refresh(series)

        self.series_id_cache = series.series_id
        return self.series_id_cache
