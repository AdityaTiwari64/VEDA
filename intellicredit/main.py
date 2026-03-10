"""
IntelliCredit — CLI Entry Point
Run credit risk assessment: research agent + rule engine.
"""

from __future__ import annotations

import argparse
import json
import sys

from .models import BorrowerProfile
from .research_agent import ResearchAgent
from .rule_engine import RuleEngine


def build_demo_profile() -> BorrowerProfile:
    """Return the sample borrower profile used for demonstration."""
    return BorrowerProfile(
        company_name="Acme Exports Private Limited",
        promoter_names=["Ramesh Kumar", "Sunita Mehta"],
        sector="textile",
        cin="U74999MH2010PTC123456",
        loan_amount=5_000_000,
        annual_turnover=12_000_000,
        net_profit=800_000,
        debt_to_equity=2.8,
        current_ratio=1.3,
        credit_score=720,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IntelliCredit — Credit Risk Assessment CLI",
    )
    parser.add_argument(
        "--rules-only",
        action="store_true",
        help="Skip research, run Rule Engine on financials only",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="mistralai/mistral-7b-instruct",
        help="OpenRouter model string (default: mistralai/mistral-7b-instruct)",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=15,
        help="Maximum number of search queries (default: 15)",
    )
    args = parser.parse_args()

    # ── Build profile ────────────────────────────────────────────────────
    profile = build_demo_profile()

    print("╔══════════════════════════════════════════════════════════╗")
    print("║          IntelliCredit — Credit Risk Assessment         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Company : {profile.company_name}")
    print(f"  Sector  : {profile.sector}")
    print(f"  CIN     : {profile.cin}")
    print(f"  Loan    : ₹{profile.loan_amount:,.0f}")
    print(f"  Mode    : {'RULES ONLY' if args.rules_only else 'FULL PIPELINE'}")
    print()

    # ── Stage 1: Research (optional) ─────────────────────────────────────
    if not args.rules_only:
        agent = ResearchAgent(
            model=args.model,
            max_queries=args.max_queries,
        )
        profile = agent.run(profile)
        ResearchAgent.print_report(profile)
    else:
        print("  ⏭  Skipping research stage (--rules-only)\n")

    # ── Stage 2: Rule Engine ─────────────────────────────────────────────
    engine = RuleEngine()
    profile = engine.evaluate(profile)
    engine.print_report(profile)

    # ── Summary JSON ─────────────────────────────────────────────────────
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║                  SUMMARY (JSON)                        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(json.dumps(profile.summary_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
