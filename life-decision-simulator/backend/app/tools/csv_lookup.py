from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"

# ── Loaders (each call reads from disk; fine for MVP, add caching if slow) ────

def _salaries() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "salaries.csv")

def _education_costs() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "education_costs.csv")

def _cost_of_living() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "cost_of_living.csv")


# ── Synchronous lookup functions ──────────────────────────────────────────────

def lookup_salary(
    role: str,
    region: str,
    level: str,
) -> Optional[dict]:
    """Return p25/p50/p75 annual USD salary + metadata, or None if no match."""
    df = _salaries()

    def _match(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        mask = pd.Series([True] * len(df), index=df.index)
        for col, val in kwargs.items():
            mask &= df[col].str.lower() == val.lower()
        return df[mask]

    rows = _match(df, role=role, region=region, level=level)
    if rows.empty:
        # Relax region constraint
        rows = _match(df, role=role, level=level)
    if rows.empty:
        return None

    row = rows.iloc[0]
    return {
        "p25": float(row["p25"]),
        "p50": float(row["p50"]),
        "p75": float(row["p75"]),
        "source": str(row["source"]),
        "year": str(row["year"]),
        "row_id": f"{row['role']}|{row['region']}|{row['level']}",
    }


def lookup_education_cost(
    program_type: str,
    country: str,
) -> Optional[dict]:
    df = _education_costs()
    mask = (
        (df["program_type"].str.lower() == program_type.lower())
        & (df["country"].str.lower() == country.lower())
    )
    rows = df[mask]
    if rows.empty:
        return None
    row = rows.iloc[0]
    return {
        "tuition_usd_yr": float(row["tuition_usd_yr"]),
        "living_usd_yr": float(row["living_usd_yr"]),
        "source": str(row["source"]),
        "row_id": f"{row['program_type']}|{row['country']}",
    }


def lookup_cost_of_living(
    city: str,
    country: str,
) -> Optional[dict]:
    df = _cost_of_living()
    mask = (
        (df["city"].str.lower() == city.lower())
        & (df["country"].str.lower() == country.lower())
    )
    rows = df[mask]
    if rows.empty:
        # Fallback: match country only, take median
        rows = df[df["country"].str.lower() == country.lower()]
    if rows.empty:
        return None
    row = rows.iloc[0]
    return {
        "monthly_usd": float(row["monthly_usd"]),
        "source": str(row["source"]),
        "row_id": f"{row['city']}|{row['country']}",
    }


# ── Async wrappers (call from FastAPI / agents) ───────────────────────────────

async def async_lookup_salary(role: str, region: str, level: str) -> Optional[dict]:
    return await asyncio.to_thread(lookup_salary, role, region, level)

async def async_lookup_education_cost(program_type: str, country: str) -> Optional[dict]:
    return await asyncio.to_thread(lookup_education_cost, program_type, country)

async def async_lookup_cost_of_living(city: str, country: str) -> Optional[dict]:
    return await asyncio.to_thread(lookup_cost_of_living, city, country)
