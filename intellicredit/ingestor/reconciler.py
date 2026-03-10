"""
ingestor/reconciler.py — GST and Bank Statement Cross-Leverage

Identifies:
1. Circular Trading: Frequent round-trip transactions between parties.
2. Revenue Inflation: Mismatch between GST turnover and bank business credits.
"""

import logging
from typing import Dict, List, Any, Optional
from collections import Counter
import pandas as pd

from ..models import BorrowerProfile, IngestorRiskSignal, GSTProfile, BankStatement
from ..config import RiskSeverity, Confidence

logger = logging.getLogger(__name__)


class GSTBankReconciler:
    """
    Reconciles GST filings with Bank Statements to find red flags.
    """

    def __init__(self, profile: BorrowerProfile):
        self.profile = profile

    def reconcile(self) -> BorrowerProfile:
        """Run all reconciliation checks"""
        logger.info(f"Starting reconciliation for {self.profile.company_name}")

        # 1. Check for Revenue Inflation
        self._check_revenue_inflation()

        # 2. Check for Circular Trading
        self._check_circular_trading()

        return self.profile

    def _check_revenue_inflation(self):
        """
        Compare GST GSTR-3B turnover with actual business credits in bank statements.
        Tolerance: 15% (to account for timing differences, cash sales, etc.)
        """
        total_gst_turnover = self.profile.get_total_gst_turnover_lakhs()

        total_bank_business_credits = 0.0
        for statement in self.profile.bank_statements:
            if statement.business_credits_lakhs:
                total_bank_business_credits += statement.business_credits_lakhs.value

        if total_gst_turnover == 0 or total_bank_business_credits == 0:
            logger.warning("Insufficient data for revenue inflation check")
            return

        # Ratio of GST Turnover to Bank Credits
        # If GST >> Bank, it's a red flag for "Circular Trading" or "Paper Invoices"
        # If Bank >> GST, it's a red flag for "GST Evasion"

        ratio = total_gst_turnover / total_bank_business_credits if total_bank_business_credits > 0 else 0

        if ratio > 1.25:
            self.profile.add_risk_signal_from_ingestor(IngestorRiskSignal(
                category="FINANCIAL",
                subcategory="REVENUE_INFLATION",
                description=f"GST Turnover (₹{total_gst_turnover:.2f}L) is {ratio:.1f}x higher than Bank Business Credits (₹{total_bank_business_credits:.2f}L). Potential revenue inflation via paper invoices.",
                severity="RED",
                source="gst_bank_reconciliation",
                score_impact=-15.0,
                evidence_snippet=f"GST: {total_gst_turnover}, Bank: {total_bank_business_credits}"
            ))
        elif ratio < 0.70:
            self.profile.add_risk_signal_from_ingestor(IngestorRiskSignal(
                category="COMPLIANCE",
                subcategory="GST_EVASION",
                description=f"Bank Business Credits (₹{total_bank_business_credits:.2f}L) are significantly higher than GST Turnover (₹{total_gst_turnover:.2f}L). Potential GST evasion or unrecorded sales.",
                severity="AMBER",
                source="gst_bank_reconciliation",
                score_impact=-10.0,
                evidence_snippet=f"GST: {total_gst_turnover}, Bank: {total_bank_business_credits}"
            ))

    def _check_circular_trading(self):
        """
        Analyze bank transactions for circular patterns.
        Look for:
        1. Frequent same-amount round trips (A -> B -> A).
        2. High-value transactions with the same counterparty that net out.
        """
        all_txns = []
        for stmt in self.profile.bank_statements:
            all_txns.extend(stmt.transactions)

        if not all_txns:
            return

        df = pd.DataFrame(all_txns)

        # Group by description (simplistic counterparty detection)
        # In a real system, we would normalize descriptions (e.g. 'NEFT-RELIANCE-123' -> 'RELIANCE')

        # 1. Look for frequent round trips
        # Identify counterparties with both significant credits and debits
        credits = df[df['credit'] > 0].groupby('description')['credit'].sum()
        debits = df[df['debit'] > 0].groupby('description')['debit'].sum()

        common_parties = set(credits.index) & set(debits.index)

        for party in common_parties:
            c_val = credits[party]
            d_val = debits[party]

            # If credits and debits are within 10% of each other and significant
            if c_val > 5.0 and abs(c_val - d_val) / max(c_val, d_val) < 0.1:
                self.profile.add_risk_signal_from_ingestor(IngestorRiskSignal(
                    category="OPERATIONAL",
                    subcategory="CIRCULAR_TRADING",
                    description=f"Potential circular trading with party '{party}': Credits ₹{c_val:.2f} and Debits ₹{d_val:.2f} almost net out.",
                    severity="RED",
                    source="transaction_analysis",
                    score_impact=-20.0,
                    evidence_snippet=f"Party: {party}, Net: {c_val - d_val}"
                ))

        # 2. Frequent UPI/IMPS transfers to same account numbers
        # Extract account numbers from descriptions if possible
        import re
        account_pattern = r'(\d{9,18})'
        df['linked_acc'] = df['description'].str.extract(account_pattern)

        linked_accs = df.dropna(subset=['linked_acc'])
        if not linked_accs.empty:
            acc_counts = linked_accs['linked_acc'].value_counts()
            for acc, count in acc_counts.items():
                if count > 10:  # Frequent transfers to same account
                    self.profile.add_risk_signal_from_ingestor(IngestorRiskSignal(
                        category="OPERATIONAL",
                        subcategory="HIGH_FREQUENCY_TRANSFER",
                        description=f"High frequency of transfers ({count}) to account ending in ...{acc[-4:]}. Possible personal use or accommodation entries.",
                        severity="AMBER",
                        source="transaction_analysis",
                        score_impact=-5.0,
                        evidence_snippet=f"Account: {acc}, Count: {count}"
                    ))
