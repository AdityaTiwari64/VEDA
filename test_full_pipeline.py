"""
IntelliCredit — Full Pipeline Test
Tests both the Ingestor (GST, Bank, Reconciler) and the Rule Engine end-to-end.

Run:   python test_full_pipeline.py
"""

import json
import os
import sys
import tempfile
import csv
from datetime import datetime

# ── Helpers ──────────────────────────────────────────────────────────────────

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def check(label, condition):
    icon = "✅" if condition else "❌"
    print(f"  {icon} {label}")
    return condition

# ══════════════════════════════════════════════════════════════════════════════
#  TEST 1: Config Module
# ══════════════════════════════════════════════════════════════════════════════

def test_config():
    section("TEST 1: Config Module")
    from intellicredit.config import (
        Confidence, RiskSeverity, ReconciliationThresholds,
        ScoringWeights, RatioNorms, BANK_FORMAT_REGISTRY,
        GRADE_MAP, RED_FLAG_PATTERNS,
    )

    results = []
    results.append(check("Confidence enum has HIGH/MEDIUM/LOW",
        Confidence.HIGH.value == "HIGH" and Confidence.LOW.value == "LOW"))
    results.append(check("RiskSeverity enum has GREEN/AMBER/RED",
        RiskSeverity.GREEN.value == 1 and RiskSeverity.RED.value == 3))
    results.append(check("BANK_FORMAT_REGISTRY has 4 banks",
        len(BANK_FORMAT_REGISTRY) == 4 and "HDFC" in BANK_FORMAT_REGISTRY))
    results.append(check("GRADE_MAP has 6 grades",
        len(GRADE_MAP) == 6))
    results.append(check("RED_FLAG_PATTERNS is non-empty",
        len(RED_FLAG_PATTERNS) > 0))
    results.append(check("ScoringWeights sum to 100",
        ScoringWeights.CHARACTER + ScoringWeights.CAPACITY +
        ScoringWeights.CAPITAL + ScoringWeights.COLLATERAL +
        ScoringWeights.CONDITIONS == 100))
    return all(results)


# ══════════════════════════════════════════════════════════════════════════════
#  TEST 2: Models (new data classes)
# ══════════════════════════════════════════════════════════════════════════════

def test_models():
    section("TEST 2: Models (new data classes)")
    from intellicredit.models import (
        ProvenanceField, IngestorRiskSignal, GSTProfile,
        BankStatement, FinancialStatements, BorrowerProfile,
        RiskSignal, SignalType, Severity,
    )

    results = []

    # ProvenanceField
    pf = ProvenanceField(value=42.5, source_file="test.json", extraction_method="structured_parse")
    results.append(check("ProvenanceField stores value + source",
        pf.value == 42.5 and pf.source_file == "test.json"))

    # IngestorRiskSignal
    sig = IngestorRiskSignal(
        category="FINANCIAL", subcategory="REVENUE_INFLATION",
        description="Test risk", severity="RED",
        source="test", score_impact=-15.0
    )
    results.append(check("IngestorRiskSignal created",
        sig.category == "FINANCIAL" and sig.score_impact == -15.0))

    # BorrowerProfile with ingestor fields
    bp = BorrowerProfile(company_name="Test Corp")
    results.append(check("BorrowerProfile has ingestor fields",
        hasattr(bp, 'gst_profiles') and hasattr(bp, 'bank_statements') and
        hasattr(bp, 'document_analysis') and hasattr(bp, 'ingestor_risk_signals')))

    # Bridge method
    bp.add_risk_signal_from_ingestor(sig)
    results.append(check("Bridge: ingestor signal → existing RiskSignal",
        len(bp.risk_signals) == 1 and len(bp.ingestor_risk_signals) == 1))
    results.append(check("Bridge: score deducted (100 → 85)",
        bp.final_score == 85.0))
    results.append(check("Bridge: mapped to SignalType.FRAUD (FINANCIAL→FRAUD)",
        bp.risk_signals[0].signal_type == SignalType.FRAUD))

    # Existing RiskSignal still works
    old_sig = RiskSignal(
        signal_type=SignalType.LITIGATION, severity=Severity.MEDIUM,
        summary="Old-style signal", source_url="http://test.com",
        source_query="test query", score_penalty=12.0
    )
    bp.attach_signal(old_sig)
    results.append(check("Existing RiskSignal attach still works",
        len(bp.risk_signals) == 2 and bp.final_score == 73.0))

    return all(results)


# ══════════════════════════════════════════════════════════════════════════════
#  TEST 3: GST Parser
# ══════════════════════════════════════════════════════════════════════════════

def test_gst_parser():
    section("TEST 3: GST Parser (GSTR-3B + GSTR-2A)")
    from intellicredit.ingestor.gst_parser import GSTParser

    results = []

    # Create sample GSTR-3B JSON
    gstr3b_data = {
        "gstin": "27AABCU9603R1ZM",
        "legal_name": "Acme Exports Pvt Ltd",
        "filing_type": "GSTR3B",
        "period": "032024",
        "data": {
            "taxable_turnover": 50000000,   # ₹5 Crore = 500 Lakhs
            "itc_claimed": 3000000           # ₹30 Lakhs
        }
    }

    gstr2a_data = {
        "gstin": "27AABCU9603R1ZM",
        "filing_type": "GSTR2A",
        "period": "032024",
        "data": {
            "itc_available": 2800000  # ₹28 Lakhs
        }
    }

    # Write temp files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(gstr3b_data, f)
        gstr3b_path = f.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(gstr2a_data, f)
        gstr2a_path = f.name

    try:
        parser = GSTParser()

        # Parse GSTR-3B
        parsed_3b = parser.parse(gstr3b_path)
        results.append(check("GSTR-3B parsed successfully",
            parsed_3b['gstin'] == "27AABCU9603R1ZM"))
        results.append(check("GSTR-3B turnover = 500 Lakhs",
            abs(parsed_3b['turnover_lakhs'].value - 500.0) < 0.01))
        results.append(check("GSTR-3B ITC claimed = 30 Lakhs",
            abs(parsed_3b['itc_claimed_lakhs'].value - 30.0) < 0.01))

        # Parse GSTR-2A
        parsed_2a = parser.parse(gstr2a_path)
        results.append(check("GSTR-2A parsed successfully",
            parsed_2a['filing_type'] == "GSTR2A"))
        results.append(check("GSTR-2A ITC available = 28 Lakhs",
            abs(parsed_2a['itc_available_lakhs'].value - 28.0) < 0.01))

        # Validation
        results.append(check("GSTR-3B validates",
            parser.validate(parsed_3b)))

        # Create GSTProfile
        profile = parser.create_gst_profile(parsed_3b, parsed_2a)
        results.append(check("GSTProfile created with state code '27'",
            profile.state == "27" and profile.gstin == "27AABCU9603R1ZM"))
    finally:
        os.unlink(gstr3b_path)
        os.unlink(gstr2a_path)

    return all(results)


# ══════════════════════════════════════════════════════════════════════════════
#  TEST 4: Bank Statement Parser
# ══════════════════════════════════════════════════════════════════════════════

def test_bank_parser():
    section("TEST 4: Bank Statement Parser (HDFC format)")
    from intellicredit.ingestor.bank_parser import BankStatementParser

    results = []

    # Create sample HDFC bank statement CSV
    rows = [
        ["Date", "Narration", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"],
        ["01/01/24", "NEFT-RELIANCE-INV001", "", "500000", "1500000"],
        ["02/01/24", "RTGS-TATA-PAY002", "", "300000", "1800000"],
        ["03/01/24", "IMPS-VENDOR-PAY", "", "200000", "2000000"],
        ["04/01/24", "EMI PAYMENT HDFC LOAN", "100000", "", "1900000"],
        ["05/01/24", "UPI-SUPPLIER-CREDIT", "", "150000", "2050000"],
        ["06/01/24", "LOAN DISBURSEMENT TL", "", "1000000", "3050000"],
        ["07/01/24", "CHEQUE BOUNCE RETURN", "50000", "", "3000000"],
        ["08/01/24", "NEFT-CUSTOMER-PAY", "", "250000", "3250000"],
        ["10/01/24", "CASH DEPOSIT BRANCH", "", "100000", "3350000"],
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
        csv_path = f.name

    try:
        parser = BankStatementParser(bank_name="HDFC")
        parsed = parser.parse(csv_path)

        results.append(check("Bank statement parsed successfully",
            parsed['bank_name'] == "HDFC"))
        results.append(check(f"Found {len(parsed['transactions'])} transactions",
            len(parsed['transactions']) > 0))

        metrics = parsed['metrics']
        results.append(check("Metrics computed (total_credits_lakhs exists)",
            'total_credits_lakhs' in metrics))
        results.append(check(f"Bounce count = {metrics.get('bounce_count', 'N/A')}",
            metrics['bounce_count'] == 1))

        # Business credits should EXCLUDE the loan disbursement
        biz_credits = metrics['business_credits_lakhs'].value
        results.append(check(f"Business credits = {biz_credits:.2f}L (excludes loan)",
            biz_credits > 0))

        # Validation
        results.append(check("Bank statement validates",
            parser.validate(parsed)))

        # Create BankStatement object
        stmt = parser.create_bank_statement(parsed)
        results.append(check("BankStatement object created",
            stmt.bank_name == "HDFC" and stmt.bounce_count == 1))
    finally:
        os.unlink(csv_path)

    return all(results)


# ══════════════════════════════════════════════════════════════════════════════
#  TEST 5: GST-Bank Reconciler
# ══════════════════════════════════════════════════════════════════════════════

def test_reconciler():
    section("TEST 5: GST-Bank Reconciler")
    from intellicredit.models import BorrowerProfile, ProvenanceField, GSTProfile, BankStatement
    from intellicredit.ingestor.reconciler import GSTBankReconciler

    results = []

    # Scenario A: Revenue inflation (GST >> Bank credits)
    profile_a = BorrowerProfile(company_name="Inflated Corp")
    profile_a.gst_profiles.append(GSTProfile(
        gstin="27TESTGSTIN",
        legal_name=ProvenanceField(value="Inflated Corp", source_file="test"),
        state="27",
        gstr3b_turnover_lakhs=ProvenanceField(value=500.0, source_file="test"),
    ))
    profile_a.bank_statements.append(BankStatement(
        bank_name="HDFC", account_number="XXXX",
        statement_period_start=datetime(2024, 1, 1),
        statement_period_end=datetime(2024, 3, 31),
        business_credits_lakhs=ProvenanceField(value=200.0, source_file="test"),
    ))

    reconciler_a = GSTBankReconciler(profile_a)
    reconciler_a.reconcile()
    has_inflation = any(
        s.subcategory == "REVENUE_INFLATION"
        for s in profile_a.ingestor_risk_signals
    )
    results.append(check("Scenario A: Revenue inflation detected (GST 500L vs Bank 200L)",
        has_inflation))

    # Scenario B: GST evasion (Bank >> GST)
    profile_b = BorrowerProfile(company_name="Evasion Corp")
    profile_b.gst_profiles.append(GSTProfile(
        gstin="27TESTGSTIN2",
        legal_name=ProvenanceField(value="Evasion Corp", source_file="test"),
        state="27",
        gstr3b_turnover_lakhs=ProvenanceField(value=100.0, source_file="test"),
    ))
    profile_b.bank_statements.append(BankStatement(
        bank_name="SBI", account_number="XXXX",
        statement_period_start=datetime(2024, 1, 1),
        statement_period_end=datetime(2024, 3, 31),
        business_credits_lakhs=ProvenanceField(value=500.0, source_file="test"),
    ))

    reconciler_b = GSTBankReconciler(profile_b)
    reconciler_b.reconcile()
    has_evasion = any(
        s.subcategory == "GST_EVASION"
        for s in profile_b.ingestor_risk_signals
    )
    results.append(check("Scenario B: GST evasion detected (GST 100L vs Bank 500L)",
        has_evasion))

    # Scenario C: Normal (within tolerance)
    profile_c = BorrowerProfile(company_name="Normal Corp")
    profile_c.gst_profiles.append(GSTProfile(
        gstin="27TESTGSTIN3",
        legal_name=ProvenanceField(value="Normal Corp", source_file="test"),
        state="27",
        gstr3b_turnover_lakhs=ProvenanceField(value=400.0, source_file="test"),
    ))
    profile_c.bank_statements.append(BankStatement(
        bank_name="ICICI", account_number="XXXX",
        statement_period_start=datetime(2024, 1, 1),
        statement_period_end=datetime(2024, 3, 31),
        business_credits_lakhs=ProvenanceField(value=420.0, source_file="test"),
    ))

    reconciler_c = GSTBankReconciler(profile_c)
    reconciler_c.reconcile()
    results.append(check("Scenario C: No red flags for normal case (GST 400L vs Bank 420L)",
        len(profile_c.ingestor_risk_signals) == 0))

    return all(results)


# ══════════════════════════════════════════════════════════════════════════════
#  TEST 6: Rule Engine (existing — regression test)
# ══════════════════════════════════════════════════════════════════════════════

def test_rule_engine():
    section("TEST 6: Rule Engine (existing — regression test)")
    from intellicredit.models import BorrowerProfile
    from intellicredit.rule_engine import RuleEngine

    results = []

    # Scenario A: Clean profile → APPROVE
    clean = BorrowerProfile(
        company_name="Good Corp",
        loan_amount=5_000_000,
        annual_turnover=12_000_000,
        net_profit=800_000,
        debt_to_equity=1.5,
        current_ratio=2.0,
        credit_score=780,
    )
    engine = RuleEngine()
    engine.evaluate(clean)
    results.append(check(f"Clean profile → {clean.final_decision} (expected APPROVE)",
        clean.final_decision == "APPROVE"))

    # Scenario B: Bad D/E ratio → REJECT
    bad_de = BorrowerProfile(
        company_name="Over-leveraged Corp",
        debt_to_equity=6.0,
        current_ratio=0.8,
        credit_score=550,
    )
    engine.evaluate(bad_de)
    results.append(check(f"Bad D/E + low credit score → {bad_de.final_decision} (expected REJECT)",
        bad_de.final_decision == "REJECT"))

    return all(results)


# ══════════════════════════════════════════════════════════════════════════════
#  TEST 7: Full Pipeline (Ingestor → Rule Engine)
# ══════════════════════════════════════════════════════════════════════════════

def test_full_pipeline():
    section("TEST 7: Full Pipeline (Ingestor → Rule Engine)")
    from intellicredit.models import BorrowerProfile, ProvenanceField, GSTProfile, BankStatement
    from intellicredit.ingestor.gst_parser import GSTParser
    from intellicredit.ingestor.reconciler import GSTBankReconciler
    from intellicredit.rule_engine import RuleEngine

    results = []

    # Build a profile with both ingestor data AND financials
    profile = BorrowerProfile(
        company_name="Acme Exports Pvt Ltd",
        promoter_names=["Ramesh Kumar"],
        sector="textile",
        cin="U74999MH2010PTC123456",
        loan_amount=5_000_000,
        annual_turnover=12_000_000,
        net_profit=800_000,
        debt_to_equity=2.8,
        current_ratio=1.3,
        credit_score=720,
    )

    # Add GST data (simulating revenue inflation)
    profile.gst_profiles.append(GSTProfile(
        gstin="27AABCU9603R1ZM",
        legal_name=ProvenanceField(value="Acme Exports Pvt Ltd", source_file="gstr3b.json"),
        state="27",
        gstr3b_turnover_lakhs=ProvenanceField(value=800.0, source_file="gstr3b.json"),
    ))

    # Add bank data (lower than GST → triggers inflation flag)
    profile.bank_statements.append(BankStatement(
        bank_name="HDFC", account_number="XXXX1234",
        statement_period_start=datetime(2024, 1, 1),
        statement_period_end=datetime(2024, 12, 31),
        business_credits_lakhs=ProvenanceField(value=500.0, source_file="hdfc_stmt.csv"),
    ))

    # Step 1: Run Reconciler
    reconciler = GSTBankReconciler(profile)
    profile = reconciler.reconcile()

    has_inflation = any(s.subcategory == "REVENUE_INFLATION" for s in profile.ingestor_risk_signals)
    results.append(check("Reconciler detected revenue inflation",
        has_inflation))
    results.append(check(f"Score after reconciliation: {profile.final_score:.1f}",
        profile.final_score < 100.0))

    # Step 2: Run Rule Engine on the same profile
    engine = RuleEngine()
    profile = engine.evaluate(profile)

    results.append(check(f"Final decision: {profile.final_decision}",
        profile.final_decision is not None))
    results.append(check(f"Rule results: {len(profile.rule_results)} rules evaluated",
        len(profile.rule_results) == 10))

    # Print summary
    print(f"\n  📊 Final Score: {profile.final_score:.1f}")
    print(f"  📋 Decision: {profile.final_decision}")
    print(f"  🔍 Ingestor signals: {len(profile.ingestor_risk_signals)}")
    print(f"  🔍 Total risk signals: {len(profile.risk_signals)}")
    print(f"  📐 Rule results: {len(profile.rule_results)}")

    return all(results)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     IntelliCredit — Full Pipeline Verification Test      ║")
    print("╚════════════════════════════════════════════════════════════╝")

    tests = [
        ("Config Module", test_config),
        ("Models (new classes)", test_models),
        ("GST Parser", test_gst_parser),
        ("Bank Statement Parser", test_bank_parser),
        ("GST-Bank Reconciler", test_reconciler),
        ("Rule Engine (regression)", test_rule_engine),
        ("Full Pipeline", test_full_pipeline),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ EXCEPTION in {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    section("RESULTS")
    print(f"  ✅ Passed: {passed}/{passed + failed}")
    if failed:
        print(f"  ❌ Failed: {failed}/{passed + failed}")
    else:
        print("  🎉 All tests passed!")

    sys.exit(0 if failed == 0 else 1)
