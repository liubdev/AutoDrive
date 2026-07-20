"""
OCR - text extraction from images using Tesseract
"""
import logging
from pathlib import Path
from typing import Optional, List, Dict

from config import settings

logger = logging.getLogger("autocar.ocr")


class OCR:
    """
    Optical Character Recognition module

    Requires Tesseract-OCR installed:
        Windows: https://github.com/UB-Mannheim/tesseract/wiki
    """

    def __init__(self, lang: str = None):
        self.lang = lang or settings.ocr_lang
        self._tesseract = None
        self._initialized = False

    def _init_tesseract(self):
        """Lazy-init Tesseract"""
        if self._initialized:
            return True

        try:
            import pytesseract
            try:
                pytesseract.get_tesseract_version()
            except Exception:
                import platform
                if platform.system() == "Windows":
                    candidates = [
                        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                    ]
                    for c in candidates:
                        if Path(c).exists():
                            pytesseract.pytesseract.tesseract_cmd = c
                            break
                else:
                    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

            self._tesseract = pytesseract
            self._initialized = True
            logger.info("Tesseract OCR ready")
            return True
        except ImportError:
            logger.warning("pytesseract not installed: pip install pytesseract")
            return False
        except Exception as e:
            logger.warning(f"OCR init failed: {e} (install Tesseract-OCR)")
            return False

    def text_from_image(self, image_path: str) -> str:
        """
        Extract text from an image

        Args:
            image_path: path to image file
        Returns:
            extracted text
        """
        if not self._init_tesseract():
            return ""

        try:
            text = self._tesseract.image_to_string(
                image_path, lang=self.lang
            )
            return text.strip()
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return ""

    def text_with_boxes(self, image_path: str) -> List[Dict]:
        """
        Extract text with bounding boxes

        Returns:
            [{"text": "...", "conf": 95, "x": 10, "y": 20, "w": 30, "h": 15}, ...]
        """
        if not self._init_tesseract():
            return []

        try:
            data = self._tesseract.image_to_data(
                image_path, lang=self.lang, output_type=self._tesseract.Output.DICT
            )
            results = []
            n = len(data["text"])
            for i in range(n):
                text = data["text"][i].strip()
                if text and int(data["conf"][i]) > 0:
                    results.append({
                        "text": text,
                        "conf": int(data["conf"][i]),
                        "x": data["left"][i],
                        "y": data["top"][i],
                        "w": data["width"][i],
                        "h": data["height"][i],
                    })
            return results
        except Exception as e:
            logger.error(f"OCR detail failed: {e}")
            return []

    def search_text(self, image_path: str, keyword: str) -> Optional[Dict]:
        """
        Search for specific text in an image

        Returns:
            box with position, or None
        """
        boxes = self.text_with_boxes(image_path)
        for box in boxes:
            if keyword.lower() in box["text"].lower():
                return box
        return None

    def is_available(self) -> bool:
        """Check if OCR is available"""
        return self._init_tesseract()
