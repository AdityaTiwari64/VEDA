"""
IntelliCredit — Run Navya Intern Report through the full pipeline
Ingestor (PageIndex RAG) → Rule Engine
"""

import json
import logging
import sys

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format="  %(name)-25s | %(message)s"
)

from intellicredit.models import BorrowerProfile
from intellicredit.ingestor.pageindex_rag import PageIndexRAG
from intellicredit.rule_engine import RuleEngine

PDF_PATH = r"D:\veda-enigne\InternReport_NavyaV_28052024.pdf"


def main():
    print("╔════════════════════════════════════════════════════════════╗")
    print("║   IntelliCredit — Navya Intern Report Pipeline Run       ║")
    print("╚════════════════════════════════════════════════════════════╝")

    # ── Step 0: Build a starter profile ──────────────────────────────────
    profile = BorrowerProfile(
        company_name="Navya V (Intern Report)",
        sector="unknown",
        loan_amount=0,
        annual_turnover=0,
        credit_score=750,       # Default assumption
        debt_to_equity=0,
        current_ratio=0,
    )

    # ── Step 1: Ingestor — PageIndex RAG ─────────────────────────────────
    print("\n══════════════════════════════════════════════════════════")
    print("  STAGE 1 / 2  —  Document Ingestion (PageIndex RAG)")
    print("══════════════════════════════════════════════════════════")

    try:
        rag = PageIndexRAG()
        profile = rag.analyze_document(PDF_PATH, profile, doc_type="ANNUAL_REPORT")

        print(f"\n  ✅ Document analyzed successfully")
        print(f"  📄 Document analysis entries: {len(profile.document_analysis)}")
        print(f"  🔍 Ingestor risk signals found: {len(profile.ingestor_risk_signals)}")
        print(f"  📊 Score after ingestion: {profile.final_score:.1f}")

        if profile.ingestor_risk_signals:
            print("\n  ── Risk Signals from Document ──")
            for i, sig in enumerate(profile.ingestor_risk_signals, 1):
                print(f"    {i}. [{sig.severity}] {sig.category}/{sig.subcategory}")
                print(f"       {sig.description}")
                print(f"       Impact: {sig.score_impact} | Evidence: {sig.evidence_snippet[:100]}...")
                print()

        if profile.document_analysis:
            print("  ── Document Index ──")
            for doc_name, analysis in profile.document_analysis.items():
                print(f"    📁 {doc_name}")
                print(f"       Type: {analysis.get('doc_type')}")
                idx = analysis.get('index', {})
                print(f"       Title: {idx.get('document_title', 'N/A')}")
                print(f"       Pages: {idx.get('total_pages', 'N/A')}")
                nodes = idx.get('nodes', [])
                print(f"       Sections: {len(nodes)}")
                for node in nodes[:5]:
                    print(f"         • {node.get('title', 'N/A')} (pages {node.get('start_index')}-{node.get('end_index')})")
                if analysis.get('financial_data'):
                    print(f"       Financial data extracted: {list(analysis['financial_data'].keys())}")
                print()

    except ConnectionError as e:
        print(f"\n  ⚠️  LLM not available: {e}")
        print("  ℹ️  To use PageIndex RAG, either:")
        print("       1. Start Ollama locally:  ollama serve")
        print("       2. Set OPENROUTER_API_KEY in .env")
        print("\n  Continuing with Rule Engine only...\n")
    except Exception as e:
        print(f"\n  ❌ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        print("\n  Continuing with Rule Engine only...\n")

    # ── Step 2: Rule Engine ──────────────────────────────────────────────
    print("\n══════════════════════════════════════════════════════════")
    print("  STAGE 2 / 2  —  Rule Engine Evaluation")
    print("══════════════════════════════════════════════════════════")

    engine = RuleEngine()
    profile = engine.evaluate(profile)
    engine.print_report(profile)

    # ── Final Summary ────────────────────────────────────────────────────
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║                    FINAL SUMMARY                         ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"  Company        : {profile.company_name}")
    print(f"  Final Score    : {profile.final_score:.1f} / 100")
    print(f"  Decision       : {profile.final_decision}")
    print(f"  Risk Signals   : {len(profile.risk_signals)} total ({len(profile.ingestor_risk_signals)} from ingestor)")
    print(f"  Rules Evaluated: {len(profile.rule_results)}")
    print(f"  Errors         : {len(profile.processing_errors)}")

    if profile.processing_errors:
        print("\n  ── Processing Errors ──")
        for err in profile.processing_errors:
            print(f"    ⚠️ {err}")

    print("\n  ── Full JSON Output ──")
    print(json.dumps(profile.summary_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
