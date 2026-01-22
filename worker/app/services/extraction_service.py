"""
Extraction service to parse structured data from OCR text.

Extracts:
- Merchant name
- Total amount
- Transaction date
- Confidence score
"""
import re
from datetime import datetime
from typing import Optional, Dict, Any
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class ExtractionService:
    """
    Parse OCR text to extract structured receipt data.

    Uses regex patterns and heuristics to identify:
    - Merchant name (first line, common patterns)
    - Total amount (currency symbols, "total", "amount due")
    - Date (various date formats)
    """

    # Common currency symbols and patterns
    CURRENCY_SYMBOLS = r'[$€£¥₹]'
    AMOUNT_PATTERNS = [
        r'(?:total|amount|due|balance|grand\s*total)\s*:?\s*' + CURRENCY_SYMBOLS + r'?\s*(\d+[.,]\d{2})',
        CURRENCY_SYMBOLS + r'\s*(\d+[.,]\d{2})',
        r'(\d+[.,]\d{2})\s*' + CURRENCY_SYMBOLS,
    ]

    # Date patterns (various formats)
    DATE_PATTERNS = [
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # MM/DD/YYYY or DD/MM/YYYY
        r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',  # YYYY/MM/DD
        r'(\w{3,}\s+\d{1,2},?\s+\d{4})',  # Month DD, YYYY
    ]

    def parse(self, ocr_text: str) -> Dict[str, Any]:
        """
        Parse OCR text to extract structured data.

        Args:
            ocr_text: Raw OCR text

        Returns:
            Dictionary with extracted fields:
            - merchant_name: str or None
            - total_amount: Decimal or None
            - transaction_date: date or None
            - currency: str (default 'USD')
            - confidence_score: float (0-1)
        """
        if not ocr_text or len(ocr_text.strip()) < 5:
            logger.warning("OCR text too short for extraction")
            return {
                "merchant_name": None,
                "total_amount": None,
                "transaction_date": None,
                "currency": "USD",
                "confidence_score": 0.0
            }

        result = {
            "merchant_name": self._extract_merchant(ocr_text),
            "total_amount": self._extract_amount(ocr_text),
            "transaction_date": self._extract_date(ocr_text),
            "currency": "USD",  # TODO: Detect currency from text
            "confidence_score": 0.0
        }

        # Calculate confidence score based on what we extracted
        result["confidence_score"] = self._calculate_confidence(result)

        logger.info(f"Extraction result: {result}")

        return result

    def _extract_merchant(self, text: str) -> Optional[str]:
        """
        Extract merchant name (heuristic: first line or first capitalized sequence).

        Args:
            text: OCR text

        Returns:
            Merchant name or None
        """
        lines = text.strip().split('\n')

        # Try first non-empty line
        for line in lines:
            line = line.strip()
            if len(line) > 2 and not re.match(r'^\d', line):
                # Clean up
                merchant = re.sub(r'[^a-zA-Z0-9\s&\'-]', '', line)
                if len(merchant) > 2:
                    return merchant[:100]  # Limit length

        # Fallback: find first sequence of capitalized words
        match = re.search(r'([A-Z][A-Z\s&]+[A-Z])', text)
        if match:
            return match.group(1).strip()[:100]

        return None

    def _extract_amount(self, text: str) -> Optional[Decimal]:
        """
        Extract total amount from text.

        Args:
            text: OCR text

        Returns:
            Decimal amount or None
        """
        # Normalize text for easier matching
        text_lower = text.lower()

        # Try patterns in order of specificity
        for pattern in self.AMOUNT_PATTERNS:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                # Take the last match (often the total)
                amount_str = matches[-1]

                # Clean and convert
                amount_str = amount_str.replace(',', '.')
                try:
                    amount = Decimal(amount_str)
                    if 0 < amount < 1000000:  # Sanity check
                        return amount
                except Exception:
                    continue

        return None

    def _extract_date(self, text: str) -> Optional[datetime.date]:
        """
        Extract transaction date from text.

        Args:
            text: OCR text

        Returns:
            Date object or None
        """
        for pattern in self.DATE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Try to parse with dateutil
                try:
                    from dateutil import parser
                    parsed_date = parser.parse(match, fuzzy=True)

                    # Sanity check (not future, not too old)
                    if parsed_date.date() <= datetime.now().date():
                        if (datetime.now() - parsed_date).days < 3650:  # Within 10 years
                            return parsed_date.date()
                except Exception:
                    continue

        return None

    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """
        Calculate confidence score based on extracted fields.

        Args:
            result: Extraction result dictionary

        Returns:
            Confidence score (0-1)
        """
        score = 0.0

        # Merchant name: 30% weight
        if result.get("merchant_name"):
            score += 0.3

        # Amount: 40% weight
        if result.get("total_amount"):
            score += 0.4

        # Date: 30% weight
        if result.get("transaction_date"):
            score += 0.3

        return round(score, 2)
