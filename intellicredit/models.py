"""
IntelliCredit — Data Models
Defines enums, dataclasses and the BorrowerProfile used throughout the system.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Enums ────────────────────────────────────────────────────────────────────

class SignalType(str, Enum):
    FRAUD = "fraud"
    LITIGATION = "litigation"
    INSOLVENCY = "insolvency"
    REGULATORY = "regulatory"
    PROMOTER_RISK = "promoter_risk"
    POSITIVE = "positive"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    POSITIVE = "POSITIVE"


class RuleOutcome(str, Enum):
    PASS = "PASS"
    FLAG = "FLAG"
    REJECT = "REJECT"


# ── Risk Signal ──────────────────────────────────────────────────────────────

@dataclass
class RiskSignal:
    signal_type: SignalType
    severity: Severity
    summary: str
    source_url: str
    source_query: str
    score_penalty: float
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Provenance Field (Ingestor) ─────────────────────────────────────────────

@dataclass
class ProvenanceField:
    """
    Wrapper for every extracted value. Tracks provenance.
    Used by the ingestor module for source tracking.
    """
    value: Any
    source_file: str
    page: Optional[int] = None
    extraction_method: str = "unknown"  # "regex" | "llm" | "ocr" | "structured_parse" | "pageindex"
    confidence: str = "MEDIUM"  # Will be a Confidence enum value
    raw_text: Optional[str] = None

    def __repr__(self):
        return f"{self.value} [src:{self.source_file}, p:{self.page}, conf:{self.confidence}]"


# ── Ingestor Risk Signal ────────────────────────────────────────────────────

@dataclass
class IngestorRiskSignal:
    """
    Risk signal format used by the ingestor/reconciler module.
    Different from the web-research RiskSignal — bridged via BorrowerProfile.
    """
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: str = ""   # "PROMOTER" | "FINANCIAL" | "LEGAL" | "OPERATIONAL" | "REGULATORY" | "COMPLIANCE"
    subcategory: str = ""  # e.g. "NCLT_CASE", "GST_MISMATCH", "NPA_HISTORY"
    description: str = ""
    severity: str = "AMBER"  # "GREEN" | "AMBER" | "RED"
    source: str = ""  # "web_search" | "gst_bank_reconciliation" | "pageindex"
    score_impact: float = 0.0  # Negative = bad, range -20 to +5
    evidence_snippet: str = ""  # EXACT text/number that triggered this
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"[{self.severity}] {self.category}/{self.subcategory}: {self.description[:50]}..."


# ── GST Profile ─────────────────────────────────────────────────────────────

@dataclass
class GSTProfile:
    """GST filing data for one GSTIN"""
    gstin: str
    legal_name: Any  # ProvenanceField
    state: str
    registration_date: Optional[datetime] = None
    status: str = "ACTIVE"

    # GSTR-3B data (self-declared)
    gstr3b_turnover_lakhs: Optional[ProvenanceField] = None
    gstr3b_itc_claimed_lakhs: Optional[ProvenanceField] = None

    # GSTR-2A data (auto-populated from suppliers)
    gstr2a_itc_available_lakhs: Optional[ProvenanceField] = None

    # Filing compliance
    missed_filings: int = 0
    last_filing_date: Optional[datetime] = None


# ── Bank Statement ──────────────────────────────────────────────────────────

@dataclass
class BankStatement:
    """Parsed bank statement data"""
    bank_name: str
    account_number: str
    statement_period_start: datetime
    statement_period_end: datetime

    # Aggregated metrics
    total_credits_lakhs: Any = None  # ProvenanceField
    total_debits_lakhs: Any = None   # ProvenanceField
    business_credits_lakhs: Any = None  # ProvenanceField — excludes loans, refunds, own transfers

    # Behavioral metrics
    bounce_count: int = 0
    avg_balance_lakhs: float = 0.0
    avg_utilization_pct: float = 0.0

    # Raw transactions (optional, for detailed analysis)
    transactions: List[Dict] = field(default_factory=list)


# ── Financial Statements ────────────────────────────────────────────────────

@dataclass
class FinancialStatements:
    """P&L and Balance Sheet for one fiscal year"""
    fiscal_year: str  # "FY2024"
    source_file: str

    # P&L (all in INR Lakhs)
    revenue: Optional[ProvenanceField] = None
    ebitda: Optional[ProvenanceField] = None
    depreciation: Optional[ProvenanceField] = None
    finance_cost: Optional[ProvenanceField] = None
    pbt: Optional[ProvenanceField] = None
    tax: Optional[ProvenanceField] = None
    pat: Optional[ProvenanceField] = None

    # Balance Sheet (all in INR Lakhs)
    total_assets: Optional[ProvenanceField] = None
    current_assets: Optional[ProvenanceField] = None
    fixed_assets: Optional[ProvenanceField] = None

    total_liabilities: Optional[ProvenanceField] = None
    current_liabilities: Optional[ProvenanceField] = None
    bank_borrowings: Optional[ProvenanceField] = None

    shareholders_equity: Optional[ProvenanceField] = None
    tangible_net_worth: Optional[ProvenanceField] = None

    # Computed ratios (stored for reference)
    ebitda_margin: Optional[float] = None
    current_ratio_computed: Optional[float] = None


# ── Rule Result ──────────────────────────────────────────────────────────────

@dataclass
class RuleResult:
    rule_id: str
    rule_name: str
    outcome: RuleOutcome
    reason: str
    detail: Optional[str] = None


# ── Borrower Profile ────────────────────────────────────────────────────────

@dataclass
class BorrowerProfile:
    # Identity
    company_name: str = ""
    promoter_names: List[str] = field(default_factory=list)
    sector: str = ""
    cin: str = ""
    pan: str = ""

    # Financials
    loan_amount: float = 0.0
    annual_turnover: float = 0.0
    net_profit: float = 0.0
    debt_to_equity: float = 0.0
    current_ratio: float = 0.0
    credit_score: Optional[int] = None

    # Research output
    risk_signals: List[RiskSignal] = field(default_factory=list)

    # Flags (set automatically by attach_signal)
    litigation_flag: bool = False
    promoter_fraud_flag: bool = False
    insolvency_flag: bool = False
    regulatory_flag: bool = False

    # Ingestor data
    gstin_list: List[str] = field(default_factory=list)
    gst_profiles: List[GSTProfile] = field(default_factory=list)
    bank_statements: List[BankStatement] = field(default_factory=list)
    financials: List[FinancialStatements] = field(default_factory=list)
    ingestor_risk_signals: List[IngestorRiskSignal] = field(default_factory=list)
    reconciliation_results: Optional[Dict] = None
    score_result: Optional[Dict] = None
    document_analysis: Dict[str, Any] = field(default_factory=dict)
    processing_errors: List[str] = field(default_factory=list)

    # Rule output
    rule_results: List[RuleResult] = field(default_factory=list)
    final_score: float = 100.0
    final_decision: Optional[str] = None

    # ── Helpers ──────────────────────────────────────────────────────────

    def attach_signal(self, signal: RiskSignal) -> None:
        """Append a signal, subtract its penalty, and set the relevant flag."""
        self.risk_signals.append(signal)
        self.final_score -= signal.score_penalty

        flag_map = {
            SignalType.LITIGATION: "litigation_flag",
            SignalType.FRAUD: "promoter_fraud_flag",
            SignalType.PROMOTER_RISK: "promoter_fraud_flag",
            SignalType.INSOLVENCY: "insolvency_flag",
            SignalType.REGULATORY: "regulatory_flag",
        }
        flag_attr = flag_map.get(signal.signal_type)
        if flag_attr:
            setattr(self, flag_attr, True)

    def high_severity_signals(self) -> List[RiskSignal]:
        return [s for s in self.risk_signals if s.severity == Severity.HIGH]

    def medium_severity_signals(self) -> List[RiskSignal]:
        return [s for s in self.risk_signals if s.severity == Severity.MEDIUM]

    def summary_dict(self) -> dict:
        return {
            "company_name": self.company_name,
            "promoter_names": self.promoter_names,
            "sector": self.sector,
            "cin": self.cin,
            "loan_amount": self.loan_amount,
            "annual_turnover": self.annual_turnover,
            "net_profit": self.net_profit,
            "debt_to_equity": self.debt_to_equity,
            "current_ratio": self.current_ratio,
            "credit_score": self.credit_score,
            "final_score": round(self.final_score, 2),
            "final_decision": self.final_decision,
            "total_signals": len(self.risk_signals),
            "high_severity": len(self.high_severity_signals()),
            "medium_severity": len(self.medium_severity_signals()),
            "flags": {
                "litigation": self.litigation_flag,
                "promoter_fraud": self.promoter_fraud_flag,
                "insolvency": self.insolvency_flag,
                "regulatory": self.regulatory_flag,
            },
            "rule_results": [
                {
                    "rule_id": r.rule_id,
                    "rule_name": r.rule_name,
                    "outcome": r.outcome.value,
                    "reason": r.reason,
                }
                for r in self.rule_results
            ],
        }

    # ── Ingestor helpers ─────────────────────────────────────────────────

    def add_risk_signal_from_ingestor(self, signal: IngestorRiskSignal) -> None:
        """
        Bridge: convert an IngestorRiskSignal to the existing RiskSignal format
        and attach it to the profile.
        """
        self.ingestor_risk_signals.append(signal)

        # Map ingestor severity to existing Severity enum
        severity_map = {
            "RED": Severity.HIGH,
            "AMBER": Severity.MEDIUM,
            "GREEN": Severity.LOW,
        }
        mapped_severity = severity_map.get(signal.severity, Severity.MEDIUM)

        # Map ingestor category to existing SignalType enum
        category_map = {
            "LEGAL": SignalType.LITIGATION,
            "FINANCIAL": SignalType.FRAUD,
            "PROMOTER": SignalType.PROMOTER_RISK,
            "REGULATORY": SignalType.REGULATORY,
            "COMPLIANCE": SignalType.REGULATORY,
            "OPERATIONAL": SignalType.UNKNOWN,
        }
        mapped_type = category_map.get(signal.category, SignalType.UNKNOWN)

        risk_signal = RiskSignal(
            signal_type=mapped_type,
            severity=mapped_severity,
            summary=signal.description,
            source_url=signal.source,
            source_query=f"{signal.category}/{signal.subcategory}",
            score_penalty=abs(signal.score_impact),
        )
        self.attach_signal(risk_signal)

    def add_risk_signal(self, signal: IngestorRiskSignal) -> None:
        """Alias used by the ingestor reconciler module."""
        self.add_risk_signal_from_ingestor(signal)

    def get_latest_financials(self) -> Optional[FinancialStatements]:
        """Get most recent financial statements."""
        return self.financials[0] if self.financials else None

    def get_total_gst_turnover_lakhs(self) -> float:
        """Sum turnover across all GSTINs."""
        total = 0.0
        for gst in self.gst_profiles:
            if gst.gstr3b_turnover_lakhs:
                total += gst.gstr3b_turnover_lakhs.value
        return total
