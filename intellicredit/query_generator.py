"""
IntelliCredit — Query Generator
Builds deduplicated search queries from a BorrowerProfile.
"""

from __future__ import annotations

from typing import List

from .models import BorrowerProfile


def generate_queries(profile: BorrowerProfile) -> List[str]:
    """Generate deduplicated search queries for the given borrower profile."""

    company = profile.company_name
    sector = profile.sector
    queries: list[str] = []

    # ── Fraud queries ────────────────────────────────────────────────────
    queries += [
        f"{company} fraud scam cheating case",
        f"{company} money laundering ED CBI",
        f"{company} SEBI penalty action",
        f"{company} RBI action penalty",
        f"{company} NPA defaulter wilful",
    ]

    # ── Litigation queries ───────────────────────────────────────────────
    queries += [
        f"{company} court case lawsuit",
        f"{company} High Court Supreme Court judgment",
        f"{company} NCLT insolvency petition",
        f"{company} arbitration dispute",
    ]

    # ── Insolvency queries ───────────────────────────────────────────────
    queries += [
        f"{company} insolvency resolution IBC",
        f"{company} NCLT IRP liquidation",
        f"{company} CIRP corporate insolvency",
    ]

    # ── Sector queries ───────────────────────────────────────────────────
    if sector:
        queries += [
            f"{company} {sector} regulatory issue",
            f"{company} {sector} scam scandal",
        ]

    # ── Promoter queries ─────────────────────────────────────────────────
    for promoter in profile.promoter_names:
        queries += [
            f"{promoter} fraud case arrested",
            f"{promoter} court case litigation",
            f"{promoter} SEBI RBI ED action",
            f"{promoter} defaulter NPA",
        ]

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        key = q.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)

    return unique
