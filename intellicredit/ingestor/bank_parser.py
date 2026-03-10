"""
ingestor/bank_parser.py — Bank statement CSV parser

Multi-bank format support via BANK_FORMAT_REGISTRY.
Handles HDFC, SBI, ICICI, AXIS formats.
"""

import pandas as pd
import logging
from typing import Dict, Any, List
from datetime import datetime
import re

from ..models import BankStatement, ProvenanceField
from ..config import Confidence, BANK_FORMAT_REGISTRY
from .base import BaseParser

logger = logging.getLogger(__name__)


class BankStatementParser(BaseParser):
    """
    Parses bank statement CSVs from multiple Indian banks.
    Uses BANK_FORMAT_REGISTRY for format detection.
    """

    def __init__(self, bank_name: str = None):
        super().__init__()
        self.bank_name = bank_name

    def parse(self, filepath: str) -> Dict[str, Any]:
        """
        Parse bank statement CSV.

        Args:
            filepath: Path to CSV file

        Returns:
            Parsed bank statement data
        """
        logger.info(f"Parsing bank statement: {filepath}")

        # Auto-detect bank if not specified
        if not self.bank_name:
            self.bank_name = self._detect_bank(filepath)
            logger.info(f"Detected bank: {self.bank_name}")

        if self.bank_name not in BANK_FORMAT_REGISTRY:
            raise ValueError(f"Unsupported bank: {self.bank_name}")

        format_config = BANK_FORMAT_REGISTRY[self.bank_name]

        # Read CSV with bank-specific settings
        df = pd.read_csv(
            filepath,
            skiprows=format_config['skip_rows'],
            encoding='utf-8'
        )

        # Parse transactions
        transactions = self._parse_transactions(df, format_config)

        # Compute aggregated metrics
        metrics = self._compute_metrics(transactions, filepath)

        return {
            'bank_name': self.bank_name,
            'transactions': transactions,
            'metrics': metrics,
            'filepath': filepath
        }

    def _detect_bank(self, filepath: str) -> str:
        """Auto-detect bank from file content"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                first_lines = ''.join([f.readline() for _ in range(5)]).lower()

            if 'hdfc' in first_lines:
                return 'HDFC'
            elif 'state bank' in first_lines or 'sbi' in first_lines:
                return 'SBI'
            elif 'icici' in first_lines:
                return 'ICICI'
            elif 'axis' in first_lines:
                return 'AXIS'
            else:
                logger.warning("Could not detect bank, defaulting to HDFC format")
                return 'HDFC'
        except Exception as e:
            logger.error(f"Bank detection failed: {e}")
            return 'HDFC'

    def _parse_transactions(self, df: pd.DataFrame, format_config: Dict) -> List[Dict]:
        """Parse individual transactions from dataframe"""
        transactions = []

        date_col = format_config['date_col']
        desc_col = format_config['desc_col']
        debit_col = format_config['debit_col']
        credit_col = format_config['credit_col']
        balance_col = format_config['balance_col']
        date_format = format_config['date_format']

        for idx, row in df.iterrows():
            try:
                # Parse date
                date_str = str(row[date_col])
                txn_date = datetime.strptime(date_str, date_format)

                # Parse amounts (handle Indian comma format: 1,23,456.78)
                debit = self._parse_amount(row.get(debit_col, 0))
                credit = self._parse_amount(row.get(credit_col, 0))
                balance = self._parse_amount(row.get(balance_col, 0))

                # Description
                description = str(row.get(desc_col, '')).strip()

                # Classify transaction type
                txn_type = self._classify_transaction(description)

                transactions.append({
                    'date': txn_date,
                    'description': description,
                    'debit': debit,
                    'credit': credit,
                    'balance': balance,
                    'type': txn_type
                })

            except Exception as e:
                logger.warning(f"Failed to parse row {idx}: {e}")
                continue

        logger.info(f"Parsed {len(transactions)} transactions")
        return transactions

    def _parse_amount(self, value) -> float:
        """Parse amount handling Indian comma format"""
        if pd.isna(value) or value == '' or value == 0:
            return 0.0

        # Convert to string and remove commas
        amount_str = str(value).replace(',', '').strip()

        try:
            return float(amount_str)
        except ValueError:
            return 0.0

    def _classify_transaction(self, description: str) -> str:
        """
        Classify transaction as business credit, loan, refund, etc.
        This is crucial for GST-bank reconciliation.
        """
        desc_lower = description.lower()

        # Exclude from business credits
        if any(keyword in desc_lower for keyword in [
            'loan disbursement', 'term loan', 'cc limit', 'od limit',
            'gst refund', 'tds refund', 'income tax refund',
            'fixed deposit', 'fd maturity', 'fd interest',
            'own account', 'internal transfer', 'neft-own'
        ]):
            return 'NON_BUSINESS_CREDIT'

        # Cheque bounces
        if 'bounce' in desc_lower or 'return' in desc_lower or 'dishonour' in desc_lower:
            return 'BOUNCE'

        # Regular business credits
        if any(keyword in desc_lower for keyword in [
            'neft', 'rtgs', 'imps', 'upi', 'cheque', 'cash deposit'
        ]):
            return 'BUSINESS_CREDIT'

        return 'OTHER'

    def _compute_metrics(self, transactions: List[Dict], filepath: str) -> Dict:
        """Compute aggregated metrics from transactions"""

        if not transactions:
            return {}

        # Total credits and debits
        total_credits = sum(t['credit'] for t in transactions)
        total_debits = sum(t['debit'] for t in transactions)

        # Business credits (exclude loans, refunds, own transfers)
        business_credits = sum(
            t['credit'] for t in transactions
            if t['type'] == 'BUSINESS_CREDIT'
        )

        # Bounce count
        bounce_count = sum(1 for t in transactions if t['type'] == 'BOUNCE')

        # Average balance
        balances = [t['balance'] for t in transactions if t['balance'] > 0]
        avg_balance = sum(balances) / len(balances) if balances else 0

        # Period
        dates = [t['date'] for t in transactions]
        period_start = min(dates)
        period_end = max(dates)

        return {
            'total_credits_lakhs': ProvenanceField(
                value=total_credits / 100000,
                source_file=filepath,
                extraction_method='structured_parse',
                confidence=Confidence.HIGH
            ),
            'total_debits_lakhs': ProvenanceField(
                value=total_debits / 100000,
                source_file=filepath,
                extraction_method='structured_parse',
                confidence=Confidence.HIGH
            ),
            'business_credits_lakhs': ProvenanceField(
                value=business_credits / 100000,
                source_file=filepath,
                extraction_method='structured_parse',
                confidence=Confidence.HIGH,
                raw_text=f"Business credits excluding loans/refunds/own transfers"
            ),
            'bounce_count': bounce_count,
            'avg_balance_lakhs': avg_balance / 100000,
            'period_start': period_start,
            'period_end': period_end,
            'transaction_count': len(transactions)
        }

    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate parsed bank statement data"""
        required_fields = ['bank_name', 'transactions', 'metrics']

        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return False

        if not data['transactions']:
            logger.warning("No transactions found in bank statement")
            return False

        return True

    def create_bank_statement(self, parsed_data: Dict) -> BankStatement:
        """
        Create BankStatement object from parsed data.

        Args:
            parsed_data: Output from parse()

        Returns:
            BankStatement object
        """
        metrics = parsed_data['metrics']

        # Extract account number from first transaction (if available)
        account_number = "XXXXXX"  # Placeholder

        statement = BankStatement(
            bank_name=parsed_data['bank_name'],
            account_number=account_number,
            statement_period_start=metrics['period_start'],
            statement_period_end=metrics['period_end'],
            total_credits_lakhs=metrics['total_credits_lakhs'],
            total_debits_lakhs=metrics['total_debits_lakhs'],
            business_credits_lakhs=metrics['business_credits_lakhs'],
            bounce_count=metrics['bounce_count'],
            avg_balance_lakhs=metrics['avg_balance_lakhs'],
            transactions=parsed_data['transactions']
        )

        return statement
