"""
IntelliCredit — Configuration
All thresholds, weights, and constants. NEVER hardcode numbers elsewhere.
"""

from enum import Enum


class Confidence(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RiskSeverity(Enum):
    GREEN = 1
    AMBER = 2
    RED = 3


# ─── RECONCILIATION THRESHOLDS ────────────────────────────────────────────────
class ReconciliationThresholds:
    """GST-Bank reconciliation flags"""
    REVENUE_INFLATION_WARN = 15  # % delta triggers warning
    REVENUE_INFLATION_FLAG = 25  # % delta triggers red flag
    GST_SUPPRESSION_WARN = -20   # Negative delta (GST > Bank)
    ITC_EXCESS_FLAG = 10         # % excess ITC claimed vs 2A
    MAX_MISSED_FILINGS = 2       # Consecutive missed GST filings

# ─── SCORING WEIGHTS ──────────────────────────────────────────────────────────
class ScoringWeights:
    """5C Scorecard weights (must sum to 100)"""
    CHARACTER = 20
    CAPACITY = 25
    CAPITAL = 20
    COLLATERAL = 20
    CONDITIONS = 15

# ─── RATIO NORMS ──────────────────────────────────────────────────────────────
class RatioNorms:
    """Indian banking ratio benchmarks"""
    # DSCR (Debt Service Coverage Ratio)
    DSCR_MIN = 1.5
    DSCR_GOOD = 1.75
    DSCR_EXCELLENT = 2.25

    # TOL/TNW (Total Outside Liabilities / Tangible Net Worth)
    TOL_TNW_MAX = 4.0
    TOL_TNW_GOOD = 3.0
    TOL_TNW_EXCELLENT = 2.0

    # Current Ratio (Tandon Committee)
    CURRENT_RATIO_MIN = 1.33

    # Interest Coverage Ratio
    ICR_MIN = 2.0
    ICR_GOOD = 3.0

    # EBITDA Margin
    EBITDA_MARGIN_MIN = 0.08  # 8%

# ─── LIMIT SIZING RULES ───────────────────────────────────────────────────────
class LimitSizingRules:
    """Working capital limit calculation"""
    MAX_WC_TO_TNW_MULTIPLE = 4.0
    MPBF_SECOND_METHOD_MARGIN = 0.25  # Borrower contributes 25%
    MAX_LIMIT_TO_REVENUE_PCT = 0.25   # Max 25% of annual revenue

# ─── PRICING (Spread over MCLR in basis points) ───────────────────────────────
class PricingBps:
    """Risk-based pricing spreads"""
    GRADE_A_PLUS = 50
    GRADE_A = 75
    GRADE_B_PLUS = 125
    GRADE_B = 175
    GRADE_C = 250
    GRADE_D = None  # Decline

# ─── GRADE MAP ────────────────────────────────────────────────────────────────
GRADE_MAP = [
    (85, "A+", "APPROVE", PricingBps.GRADE_A_PLUS),
    (75, "A", "APPROVE", PricingBps.GRADE_A),
    (65, "B+", "CONDITIONAL_APPROVE", PricingBps.GRADE_B_PLUS),
    (55, "B", "CONDITIONAL_APPROVE", PricingBps.GRADE_B),
    (45, "C", "REFER", PricingBps.GRADE_C),
    (0, "D", "DECLINE", PricingBps.GRADE_D),
]

# ─── BANK FORMAT REGISTRY ─────────────────────────────────────────────────────
BANK_FORMAT_REGISTRY = {
    "HDFC": {
        "date_col": "Date",
        "desc_col": "Narration",
        "debit_col": "Withdrawal Amt.",
        "credit_col": "Deposit Amt.",
        "balance_col": "Closing Balance",
        "date_format": "%d/%m/%y",
        "skip_rows": 0,
    },
    "SBI": {
        "date_col": "Txn Date",
        "desc_col": "Description",
        "debit_col": "Debit",
        "credit_col": "Credit",
        "balance_col": "Balance",
        "date_format": "%d %b %Y",
        "skip_rows": 16,  # SBI has metadata header
    },
    "ICICI": {
        "date_col": "Transaction Date",
        "desc_col": "Transaction Remarks",
        "debit_col": "Withdrawal",
        "credit_col": "Deposit",
        "balance_col": "Balance",
        "date_format": "%d-%m-%Y",
        "skip_rows": 0,
    },
    "AXIS": {
        "date_col": "TRAN DATE",
        "desc_col": "PARTICULARS",
        "debit_col": "DR",
        "credit_col": "CR",
        "balance_col": "BALANCE",
        "date_format": "%d-%m-%Y",
        "skip_rows": 0,
    },
}

# ─── INDIAN BANKING RED FLAGS ─────────────────────────────────────────────────
RED_FLAG_PATTERNS = [
    "SARFAESI proceedings initiated",
    "Account classified as NPA",
    "NCLT admission",
    "DIN deactivation",
    "DIN suspension",
    "SFIO investigation",
    "struck-off company",
    "GSTR-3B filed with delay",
    "Enforcement Directorate",
    "wilful defaulter",
    "fraud",
    "forensic audit",
    "RBI show cause notice",
]
