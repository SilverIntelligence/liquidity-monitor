"""Tests for ETF transformers."""

import pytest
from datetime import date
from etl.transformers.transform_etf import transform_gld, transform_slv


class TestGLDTransformer:
    """Test GLD CSV transformer."""

    def test_transform_gld_valid_csv(self) -> None:
        """Test transforming valid GLD CSV data."""
        raw_data = {
            "content": b"Date,Tonnes,Ounces,Value\n2024-11-18,1000.5,32169000.5,60000000\n2024-11-17,1000.0,32153000.0,59000000",
            "source": "GLD",
            "checksum": "abc123",
        }

        records = transform_gld(raw_data)

        assert len(records) == 2
        assert records[0]["ds"] == date(2024, 11, 18)
        assert records[0]["fund"] == "GLD"
        assert records[0]["net_shares"] == 32169000.5
        assert records[1]["net_shares"] == 32153000.0

    def test_transform_gld_empty(self) -> None:
        """Test transforming empty CSV."""
        raw_data = {"content": b"Date,Tonnes,Ounces,Value\n", "source": "GLD"}

        records = transform_gld(raw_data)

        assert len(records) == 0

    def test_transform_gld_malformed_row(self) -> None:
        """Test handling malformed rows."""
        raw_data = {
            "content": b"Date,Tonnes,Ounces,Value\n2024-11-18,1000.5,32169000.5,60000000\ninvalid,row,data\n",
            "source": "GLD",
        }

        records = transform_gld(raw_data)

        # Should skip malformed row
        assert len(records) == 1
        assert records[0]["ds"] == date(2024, 11, 18)


class TestSLVTransformer:
    """Test SLV CSV transformer."""

    def test_transform_slv_with_header(self) -> None:
        """Test transforming SLV data with iShares header format."""
        raw_data = {
            "content": b"Fund Holdings\niShares Silver Trust\n\nFund Name,Ticker,Name,Shares,Market Value\niSHARES SILVER TRUST,SLV,Silver Bars,500000000,15000000000\n",
            "source": "SLV",
        }

        records = transform_slv(raw_data)

        assert len(records) == 1
        assert records[0]["fund"] == "SLV"
        assert records[0]["net_shares"] == 500000000.0
        assert records[0]["aum"] == 15000000000.0

    def test_transform_slv_no_data(self) -> None:
        """Test handling SLV response with no silver data."""
        raw_data = {
            "content": b"Fund Name,Ticker,Name,Shares,Market Value\n",
            "source": "SLV",
        }

        records = transform_slv(raw_data)

        assert len(records) == 0
