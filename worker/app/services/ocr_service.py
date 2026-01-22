"""
OCR service using EasyOCR for text extraction from receipts.
"""
import easyocr
import numpy as np
from PIL import Image
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


class OCRService:
    """
    OCR service wrapper for EasyOCR.

    Handles initialization and text extraction from image bytes.
    """

    def __init__(self, languages=['en'], gpu=False):
        """
        Initialize EasyOCR reader.

        Args:
            languages: List of language codes (default: English)
            gpu: Use GPU if available (default: False for CPU-only)
        """
        self.languages = languages
        self.reader = None
        self.gpu = gpu

    def _get_reader(self):
        """Lazy initialization of OCR reader."""
        if self.reader is None:
            logger.info(f"Initializing EasyOCR reader (languages: {self.languages}, GPU: {self.gpu})")
            self.reader = easyocr.Reader(self.languages, gpu=self.gpu)
        return self.reader

    def extract_text(self, image_bytes: bytes) -> str:
        """
        Extract text from image bytes.

        Args:
            image_bytes: Image file content as bytes

        Returns:
            Extracted text as single string

        Raises:
            Exception: On OCR failure
        """
        try:
            # Convert bytes to PIL Image
            image = Image.open(BytesIO(image_bytes))

            # Convert to numpy array
            image_np = np.array(image)

            # Get OCR reader
            reader = self._get_reader()

            # Perform OCR
            results = reader.readtext(image_np)

            # Extract text from results (each result is [bbox, text, confidence])
            extracted_text = " ".join([result[1] for result in results])

            logger.info(f"OCR extracted {len(results)} text regions, {len(extracted_text)} characters")

            return extracted_text

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}", exc_info=True)
            raise
