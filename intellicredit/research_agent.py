"""
IntelliCredit — Research Agent
Orchestrates query generation → web search → signal extraction → profile update.
"""

from __future__ import annotations

from .models import BorrowerProfile, Severity
from .query_generator import generate_queries
from .signal_extractor import DEFAULT_MODEL, extract_signals_from_results
from .web_searcher import SearchResult, batch_search


class ResearchAgent:
    """Runs the full research pipeline against a BorrowerProfile."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_results_per_query: int = 5,
        delay_between_queries: float = 1.5,
        max_queries: int = 20,
    ):
        self.model = model
        self.max_results_per_query = max_results_per_query
        self.delay_between_queries = delay_between_queries
        self.max_queries = max_queries

    def run(self, profile: BorrowerProfile) -> BorrowerProfile:
        """Execute the 4-stage research pipeline and return the updated profile."""

        # ── Stage 1: Generate queries ────────────────────────────────────
        print("\n══════════════════════════════════════════════════════════")
        print("  STAGE 1 / 4  —  Generating search queries")
        print("══════════════════════════════════════════════════════════")
        queries = generate_queries(profile)
        queries = queries[: self.max_queries]
        print(f"  ✅ Generated {len(queries)} queries (cap: {self.max_queries})")

        # ── Stage 2: Web search ──────────────────────────────────────────
        print("\n══════════════════════════════════════════════════════════")
        print("  STAGE 2 / 4  —  Searching the web")
        print("══════════════════════════════════════════════════════════")
        search_results = batch_search(
            queries,
            max_results_per_query=self.max_results_per_query,
            delay_between_queries=self.delay_between_queries,
        )

        # Flatten all results
        all_results: list[SearchResult] = []
        for res_list in search_results.values():
            all_results.extend(res_list)
        print(f"  ✅ Collected {len(all_results)} search results")

        # ── Stage 3: Signal extraction ───────────────────────────────────
        print("\n══════════════════════════════════════════════════════════")
        print("  STAGE 3 / 4  —  Extracting risk signals (LLM)")
        print("══════════════════════════════════════════════════════════")
        signals = extract_signals_from_results(
            all_results, model=self.model, dedupe=True
        )
        print(f"  ✅ Extracted {len(signals)} unique signals")

        # ── Stage 4: Attach to profile ───────────────────────────────────
        print("\n══════════════════════════════════════════════════════════")
        print("  STAGE 4 / 4  —  Attaching signals to profile")
        print("══════════════════════════════════════════════════════════")
        for signal in signals:
            profile.attach_signal(signal)
        print(f"  ✅ Profile updated — score: {profile.final_score:.1f}")

        return profile

    # ── Reporting ────────────────────────────────────────────────────────

    @staticmethod
    def print_report(profile: BorrowerProfile) -> None:
        """Pretty-print the research findings."""
        print("\n╔══════════════════════════════════════════════════════════╗")
        print("║            RESEARCH AGENT — SIGNAL REPORT              ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print(f"  Company : {profile.company_name}")
        print(f"  Signals : {len(profile.risk_signals)}")
        print(f"  Score   : {profile.final_score:.1f} / 100")
        print()

        if not profile.risk_signals:
            print("  ✅ No risk signals detected.\n")
            return

        severity_icon = {
            Severity.HIGH: "🔴",
            Severity.MEDIUM: "🟡",
            Severity.LOW: "🟢",
            Severity.POSITIVE: "⚪",
        }

        for idx, sig in enumerate(profile.risk_signals, 1):
            icon = severity_icon.get(sig.severity, "⚪")
            print(f"  {icon} [{idx}] {sig.severity.value} | {sig.signal_type.value}")
            print(f"       {sig.summary}")
            print(f"       Penalty: -{sig.score_penalty}  |  URL: {sig.source_url}")
            print()
