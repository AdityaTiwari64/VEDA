"""
ingestor/gst_parser.py — GST filing parser

Parses GSTR-1, GSTR-2A, GSTR-3B JSON exports from GST portal.
"""

import json
import logging
from typing import Dict, Any
from datetime import datetime

from ..models import GSTProfile, ProvenanceField
from ..config import Confidence
from .base import BaseParser

logger = logging.getLogger(__name__)


class GSTParser(BaseParser):
    """
    Parses GST JSON exports.
    Handles GSTR-3B (self-declared) and GSTR-2A (auto-populated).
    """

    def parse(self, filepath: str) -> Dict[str, Any]:
        """
        Parse GST JSON file.

        Expected structure:
        {
          "gstin": "27XXXXX",
          "legal_name": "Company Name",
          "filing_type": "GSTR3B" or "GSTR2A",
          "period": "032024",
          "data": {...}
        }
        """
        logger.info(f"Parsing GST file: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            gst_data = json.load(f)

        filing_type = gst_data.get('filing_type', '').upper()

        if filing_type == 'GSTR3B':
            return self._parse_gstr3b(gst_data, filepath)
        elif filing_type == 'GSTR2A':
            return self._parse_gstr2a(gst_data, filepath)
        else:
            raise ValueError(f"Unknown GST filing type: {filing_type}")

    def _parse_gstr3b(self, data: Dict, filepath: str) -> Dict[str, Any]:
        """Parse GSTR-3B (self-declared monthly/quarterly return)"""

        gstin = data.get('gstin', '')
        legal_name = data.get('legal_name', '')
        period = data.get('period', '')

        # Box 3.1: Outward taxable supplies (excluding zero rated, nil rated, exempted)
        gstr3b_data = data.get('data', {})

        # Total turnover (Box 3.1)
        taxable_turnover = gstr3b_data.get('taxable_turnover', 0)

        # ITC claimed (Box 4)
        itc_claimed = gstr3b_data.get('itc_claimed', 0)

        result = {
            'gstin': gstin,
            'legal_name': ProvenanceField(
                value=legal_name,
                source_file=filepath,
                extraction_method='structured_parse',
                confidence=Confidence.HIGH
            ),
            'filing_type': 'GSTR3B',
            'period': period,
            'turnover_lakhs': ProvenanceField(
                value=taxable_turnover / 100000,  # Convert to Lakhs
                source_file=filepath,
                extraction_method='structured_parse',
                confidence=Confidence.HIGH,
                raw_text=f"Box 3.1: Taxable turnover ₹{taxable_turnover}"
            ),
            'itc_claimed_lakhs': ProvenanceField(
                value=itc_claimed / 100000,
                source_file=filepath,
                extraction_method='structured_parse',
                confidence=Confidence.HIGH,
                raw_text=f"Box 4: ITC claimed ₹{itc_claimed}"
            )
        }

        logger.info(f"Parsed GSTR-3B: {gstin}, Turnover ₹{taxable_turnover/100000:.2f}L")
        return result

    def _parse_gstr2a(self, data: Dict, filepath: str) -> Dict[str, Any]:
        """Parse GSTR-2A (auto-populated from supplier filings)"""

        gstin = data.get('gstin', '')
        period = data.get('period', '')

        gstr2a_data = data.get('data', {})

        # ITC available (sum of all eligible ITC from suppliers)
        itc_available = gstr2a_data.get('itc_available', 0)

        result = {
            'gstin': gstin,
            'filing_type': 'GSTR2A',
            'period': period,
            'itc_available_lakhs': ProvenanceField(
                value=itc_available / 100000,
                source_file=filepath,
                extraction_method='structured_parse',
                confidence=Confidence.HIGH,
                raw_text=f"GSTR-2A ITC available ₹{itc_available}"
            )
        }

        logger.info(f"Parsed GSTR-2A: {gstin}, ITC available ₹{itc_available/100000:.2f}L")
        return result

    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate parsed GST data"""
        required_fields = ['gstin', 'filing_type']

        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return False

        if data['filing_type'] == 'GSTR3B':
            if 'turnover_lakhs' not in data:
                logger.error("GSTR3B missing turnover_lakhs")
                return False

        return True

    def create_gst_profile(self, gstr3b_data: Dict, gstr2a_data: Dict = None) -> GSTProfile:
        """
        Create GSTProfile from parsed data.

        Args:
            gstr3b_data: Parsed GSTR-3B data
            gstr2a_data: Optional parsed GSTR-2A data

        Returns:
            GSTProfile object
        """
        profile = GSTProfile(
            gstin=gstr3b_data['gstin'],
            legal_name=gstr3b_data['legal_name'],
            state=gstr3b_data['gstin'][:2],  # First 2 digits = state code
            gstr3b_turnover_lakhs=gstr3b_data.get('turnover_lakhs'),
            gstr3b_itc_claimed_lakhs=gstr3b_data.get('itc_claimed_lakhs')
        )

        if gstr2a_data:
            profile.gstr2a_itc_available_lakhs = gstr2a_data.get('itc_available_lakhs')

        return profile
