"""
IntelliCredit — Rule Engine
10 configurable credit risk rules + final decision logic.
"""

from __future__ import annotations

from .models import (
    BorrowerProfile,
    RuleOutcome,
    RuleResult,
    Severity,
    SignalType,
)

# ── Configurable thresholds ──────────────────────────────────────────────────

THRESHOLDS = {
    "max_debt_to_equity_reject": 5.0,
    "max_debt_to_equity_flag": 3.0,
    "min_current_ratio_flag": 1.0,
    "max_loan_to_turnover": 3.0,
    "min_credit_score_reject": 600,
    "min_credit_score_flag": 700,
    "min_score_approve": 70.0,
    "min_score_review": 45.0,
}


class RuleEngine:
    """Evaluates a BorrowerProfile against 10 credit-risk rules."""

    def evaluate(self, profile: BorrowerProfile) -> BorrowerProfile:
        """Run all rules and set final_decision on the profile."""
        profile.rule_results = []

        profile.rule_results.append(self._r001_wilful_defaulter(profile))
        profile.rule_results.append(self._r002_insolvency(profile))
        profile.rule_results.append(self._r003_promoter_fraud(profile))
        profile.rule_results.append(self._r004_active_litigation(profile))
        profile.rule_results.append(self._r005_regulatory_action(profile))
        profile.rule_results.append(self._r006_debt_to_equity(profile))
        profile.rule_results.append(self._r007_current_ratio(profile))
        profile.rule_results.append(self._r008_loan_to_turnover(profile))
        profile.rule_results.append(self._r009_credit_score(profile))
        profile.rule_results.append(self._r010_composite_score(profile))

        # ── Final decision ───────────────────────────────────────────────
        outcomes = [r.outcome for r in profile.rule_results]
        if RuleOutcome.REJECT in outcomes:
            profile.final_decision = "REJECT"
        elif RuleOutcome.FLAG in outcomes:
            profile.final_decision = "REVIEW"
        else:
            profile.final_decision = "APPROVE"

        return profile

    # ── Individual rules ─────────────────────────────────────────────────

    @staticmethod
    def _r001_wilful_defaulter(p: BorrowerProfile) -> RuleResult:
        """R001: Wilful Defaulter / NPA — REJECT if any HIGH-severity fraud signal."""
        high_fraud = [
            s for s in p.risk_signals
            if s.signal_type == SignalType.FRAUD and s.severity == Severity.HIGH
        ]
        if high_fraud:
            return RuleResult(
                rule_id="R001",
                rule_name="Wilful Defaulter / NPA",
                outcome=RuleOutcome.REJECT,
                reason="HIGH-severity fraud signal detected",
                detail=high_fraud[0].summary,
            )
        return RuleResult(
            rule_id="R001",
            rule_name="Wilful Defaulter / NPA",
            outcome=RuleOutcome.PASS,
            reason="No HIGH-severity fraud signals",
        )

    @staticmethod
    def _r002_insolvency(p: BorrowerProfile) -> RuleResult:
        """R002: Insolvency / NCLT — REJECT if insolvency_flag is True."""
        if p.insolvency_flag:
            return RuleResult(
                rule_id="R002",
                rule_name="Insolvency / NCLT",
                outcome=RuleOutcome.REJECT,
                reason="Insolvency flag is set",
            )
        return RuleResult(
            rule_id="R002",
            rule_name="Insolvency / NCLT",
            outcome=RuleOutcome.PASS,
            reason="No insolvency indicators",
        )

    @staticmethod
    def _r003_promoter_fraud(p: BorrowerProfile) -> RuleResult:
        """R003: Promoter Fraud — REJECT if flag + HIGH; FLAG if MEDIUM only."""
        if not p.promoter_fraud_flag:
            return RuleResult(
                rule_id="R003",
                rule_name="Promoter Fraud",
                outcome=RuleOutcome.PASS,
                reason="No promoter fraud indicators",
            )

        high_promoter = [
            s for s in p.risk_signals
            if s.signal_type in (SignalType.FRAUD, SignalType.PROMOTER_RISK)
            and s.severity == Severity.HIGH
        ]
        if high_promoter:
            return RuleResult(
                rule_id="R003",
                rule_name="Promoter Fraud",
                outcome=RuleOutcome.REJECT,
                reason="Promoter fraud flag with HIGH-severity signal",
                detail=high_promoter[0].summary,
            )
        return RuleResult(
            rule_id="R003",
            rule_name="Promoter Fraud",
            outcome=RuleOutcome.FLAG,
            reason="Promoter fraud flag with MEDIUM-severity signal",
        )

    @staticmethod
    def _r004_active_litigation(p: BorrowerProfile) -> RuleResult:
        """R004: Active Litigation — FLAG if litigation_flag is True."""
        if p.litigation_flag:
            return RuleResult(
                rule_id="R004",
                rule_name="Active Litigation",
                outcome=RuleOutcome.FLAG,
                reason="Litigation flag is set",
            )
        return RuleResult(
            rule_id="R004",
            rule_name="Active Litigation",
            outcome=RuleOutcome.PASS,
            reason="No active litigation",
        )

    @staticmethod
    def _r005_regulatory_action(p: BorrowerProfile) -> RuleResult:
        """R005: Regulatory Action — FLAG if regulatory_flag is True."""
        if p.regulatory_flag:
            return RuleResult(
                rule_id="R005",
                rule_name="Regulatory Action",
                outcome=RuleOutcome.FLAG,
                reason="Regulatory flag is set",
            )
        return RuleResult(
            rule_id="R005",
            rule_name="Regulatory Action",
            outcome=RuleOutcome.PASS,
            reason="No regulatory actions",
        )

    @staticmethod
    def _r006_debt_to_equity(p: BorrowerProfile) -> RuleResult:
        """R006: Debt-to-Equity — REJECT if > 5.0; FLAG if > 3.0; skip if <= 0."""
        de = p.debt_to_equity
        if de <= 0:
            return RuleResult(
                rule_id="R006",
                rule_name="Debt-to-Equity Ratio",
                outcome=RuleOutcome.PASS,
                reason=f"D/E ratio is {de} (skipped — non-positive)",
            )
        if de > THRESHOLDS["max_debt_to_equity_reject"]:
            return RuleResult(
                rule_id="R006",
                rule_name="Debt-to-Equity Ratio",
                outcome=RuleOutcome.REJECT,
                reason=f"D/E ratio {de} exceeds reject threshold {THRESHOLDS['max_debt_to_equity_reject']}",
            )
        if de > THRESHOLDS["max_debt_to_equity_flag"]:
            return RuleResult(
                rule_id="R006",
                rule_name="Debt-to-Equity Ratio",
                outcome=RuleOutcome.FLAG,
                reason=f"D/E ratio {de} exceeds flag threshold {THRESHOLDS['max_debt_to_equity_flag']}",
            )
        return RuleResult(
            rule_id="R006",
            rule_name="Debt-to-Equity Ratio",
            outcome=RuleOutcome.PASS,
            reason=f"D/E ratio {de} is within acceptable range",
        )

    @staticmethod
    def _r007_current_ratio(p: BorrowerProfile) -> RuleResult:
        """R007: Current Ratio — FLAG if < 1.0; skip if <= 0."""
        cr = p.current_ratio
        if cr <= 0:
            return RuleResult(
                rule_id="R007",
                rule_name="Current Ratio",
                outcome=RuleOutcome.PASS,
                reason=f"Current ratio is {cr} (skipped — non-positive)",
            )
        if cr < THRESHOLDS["min_current_ratio_flag"]:
            return RuleResult(
                rule_id="R007",
                rule_name="Current Ratio",
                outcome=RuleOutcome.FLAG,
                reason=f"Current ratio {cr} below flag threshold {THRESHOLDS['min_current_ratio_flag']}",
            )
        return RuleResult(
            rule_id="R007",
            rule_name="Current Ratio",
            outcome=RuleOutcome.PASS,
            reason=f"Current ratio {cr} is acceptable",
        )

    @staticmethod
    def _r008_loan_to_turnover(p: BorrowerProfile) -> RuleResult:
        """R008: Loan-to-Turnover — FLAG if ratio > 3.0; skip if either <= 0."""
        if p.loan_amount <= 0 or p.annual_turnover <= 0:
            return RuleResult(
                rule_id="R008",
                rule_name="Loan-to-Turnover Ratio",
                outcome=RuleOutcome.PASS,
                reason="Skipped — loan or turnover is non-positive",
            )
        ratio = p.loan_amount / p.annual_turnover
        if ratio > THRESHOLDS["max_loan_to_turnover"]:
            return RuleResult(
                rule_id="R008",
                rule_name="Loan-to-Turnover Ratio",
                outcome=RuleOutcome.FLAG,
                reason=f"Loan/Turnover ratio {ratio:.2f} exceeds threshold {THRESHOLDS['max_loan_to_turnover']}",
            )
        return RuleResult(
            rule_id="R008",
            rule_name="Loan-to-Turnover Ratio",
            outcome=RuleOutcome.PASS,
            reason=f"Loan/Turnover ratio {ratio:.2f} is acceptable",
        )

    @staticmethod
    def _r009_credit_score(p: BorrowerProfile) -> RuleResult:
        """R009: Credit Score — REJECT if < 600; FLAG if < 700; FLAG if None."""
        if p.credit_score is None:
            return RuleResult(
                rule_id="R009",
                rule_name="Credit Score",
                outcome=RuleOutcome.FLAG,
                reason="Credit score is not available",
            )
        if p.credit_score < THRESHOLDS["min_credit_score_reject"]:
            return RuleResult(
                rule_id="R009",
                rule_name="Credit Score",
                outcome=RuleOutcome.REJECT,
                reason=f"Credit score {p.credit_score} below reject threshold {THRESHOLDS['min_credit_score_reject']}",
            )
        if p.credit_score < THRESHOLDS["min_credit_score_flag"]:
            return RuleResult(
                rule_id="R009",
                rule_name="Credit Score",
                outcome=RuleOutcome.FLAG,
                reason=f"Credit score {p.credit_score} below flag threshold {THRESHOLDS['min_credit_score_flag']}",
            )
        return RuleResult(
            rule_id="R009",
            rule_name="Credit Score",
            outcome=RuleOutcome.PASS,
            reason=f"Credit score {p.credit_score} is acceptable",
        )

    @staticmethod
    def _r010_composite_score(p: BorrowerProfile) -> RuleResult:
        """R010: Composite Score — PASS if ≥ 70; FLAG if 45–70; REJECT if < 45."""
        score = p.final_score
        if score >= THRESHOLDS["min_score_approve"]:
            return RuleResult(
                rule_id="R010",
                rule_name="Composite Risk Score",
                outcome=RuleOutcome.PASS,
                reason=f"Composite score {score:.1f} ≥ {THRESHOLDS['min_score_approve']}",
            )
        if score >= THRESHOLDS["min_score_review"]:
            return RuleResult(
                rule_id="R010",
                rule_name="Composite Risk Score",
                outcome=RuleOutcome.FLAG,
                reason=f"Composite score {score:.1f} in review range ({THRESHOLDS['min_score_review']}–{THRESHOLDS['min_score_approve']})",
            )
        return RuleResult(
            rule_id="R010",
            rule_name="Composite Risk Score",
            outcome=RuleOutcome.REJECT,
            reason=f"Composite score {score:.1f} below reject threshold {THRESHOLDS['min_score_review']}",
        )

    # ── Reporting ────────────────────────────────────────────────────────

    @staticmethod
    def print_report(profile: BorrowerProfile) -> None:
        """Pretty-print the rule evaluation results."""
        outcome_icon = {
            RuleOutcome.PASS: "✅",
            RuleOutcome.FLAG: "🟡",
            RuleOutcome.REJECT: "🔴",
        }

        print("\n╔══════════════════════════════════════════════════════════╗")
        print("║              RULE ENGINE — EVALUATION REPORT            ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print(f"  Company  : {profile.company_name}")
        print(f"  Score    : {profile.final_score:.1f} / 100")
        print(f"  Decision : {profile.final_decision}")
        print()

        for r in profile.rule_results:
            icon = outcome_icon.get(r.outcome, "❓")
            print(f"  {icon} {r.rule_id} {r.rule_name}")
            print(f"       Outcome: {r.outcome.value}  |  {r.reason}")
            if r.detail:
                print(f"       Detail : {r.detail}")
            print()
