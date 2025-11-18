"""ETF data transformers - enforce oz/USD and consistent naming."""

import io
from datetime import date, datetime
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup


def transform_gld(raw_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Transform GLD CSV to standardized format.

    Args:
        raw_data: Raw extraction output

    Returns:
        List of standardized records
    """
    content = raw_data["content"]
    text = content.decode("utf-8")

    df = pd.read_csv(io.StringIO(text))

    records = []
    for _, row in df.iterrows():
        try:
            ds = pd.to_datetime(row["Date"]).date()
            ounces = float(row["Ounces"])
            tonnes = float(row.get("Tonnes", 0))

            records.append(
                {
                    "ds": ds,
                    "fund": "GLD",
                    "nav": None,  # Not in this dataset
                    "aum": None,
                    "shares_in": None,
                    "shares_out": None,
                    "net_shares": ounces,  # Total holdings
                    "price": None,
                }
            )
        except (ValueError, KeyError):
            continue

    return records


def transform_slv(raw_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Transform SLV CSV to standardized format.

    Args:
        raw_data: Raw extraction output

    Returns:
        List of standardized records
    """
    content = raw_data["content"]
    text = content.decode("utf-8")
    lines = text.split("\n")

    # Find data section
    data_start = 0
    for i, line in enumerate(lines):
        if "Fund Name" in line or "ticker" in line.lower():
            data_start = i
            break

    if data_start > 0:
        csv_data = "\n".join(lines[data_start:])
        df = pd.read_csv(io.StringIO(csv_data))

        # Extract total silver holdings
        for _, row in df.iterrows():
            if "silver" in str(row.get("Name", "")).lower():
                return [
                    {
                        "ds": date.today(),
                        "fund": "SLV",
                        "nav": None,
                        "aum": float(row.get("Market Value", 0)),
                        "shares_in": None,
                        "shares_out": None,
                        "net_shares": float(row.get("Shares", 0)),
                        "price": None,
                    }
                ]

    return []


def transform_pslv(raw_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Transform PSLV HTML to standardized format.

    Args:
        raw_data: Raw extraction output

    Returns:
        List of standardized records
    """
    content = raw_data["content"]
    soup = BeautifulSoup(content, "html.parser")

    # Look for ounces in page text
    text = soup.get_text()

    import re

    ounces_match = re.search(r"([\d,]+\.?\d*)\s*(?:million\s+)?(?:troy\s+)?ounces", text, re.IGNORECASE)

    if ounces_match:
        ounces_str = ounces_match.group(1).replace(",", "")
        try:
            ounces = float(ounces_str)

            # If value is in millions
            if "million" in text[max(0, ounces_match.start() - 50) : ounces_match.end() + 20].lower():
                ounces *= 1_000_000

            return [
                {
                    "ds": date.today(),
                    "fund": "PSLV",
                    "nav": None,
                    "aum": None,
                    "shares_in": None,
                    "shares_out": None,
                    "net_shares": ounces,
                    "price": None,
                }
            ]
        except ValueError:
            pass

    return []
