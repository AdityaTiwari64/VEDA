"""
ingestor/base.py — Abstract base parser
All parsers must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """
    Abstract base class for all document parsers.
    Ensures consistent interface across GST, bank, PDF parsers.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def parse(self, filepath: str) -> Dict[str, Any]:
        """
        Parse the document and return structured data.

        Args:
            filepath: Path to the document

        Returns:
            Dictionary with parsed data

        Raises:
            ValueError: If document format is invalid
            FileNotFoundError: If file doesn't exist
        """
        pass

    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> bool:
        """
        Validate that parsed data has required fields.

        Args:
            data: Parsed data dictionary

        Returns:
            True if valid, False otherwise
        """
        pass

    def safe_parse(self, filepath: str) -> Dict[str, Any]:
        """
        Parse with error handling. Returns empty dict on failure.
        Logs errors but doesn't crash the pipeline.
        """
        try:
            data = self.parse(filepath)
            if self.validate(data):
                self.logger.info(f"Successfully parsed {filepath}")
                return data
            else:
                self.logger.warning(f"Validation failed for {filepath}")
                return {"error": "validation_failed", "filepath": filepath}
        except Exception as e:
            self.logger.error(f"Failed to parse {filepath}: {e}")
            return {"error": str(e), "filepath": filepath}
