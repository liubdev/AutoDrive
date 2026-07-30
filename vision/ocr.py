"""
OCR - Windows 内置 OCR（无需安装，Win10/11 自带）

替换了 Tesseract，用户机器零依赖。
"""

import io
import logging
from pathlib import Path
from typing import Optional, List, Dict

from PIL import Image
import winsdk.windows.media.ocr as wocr
import winsdk.windows.globalization as wg
from winsdk.windows.graphics.imaging import BitmapDecoder, BitmapPixelFormat
from winsdk.windows.storage.streams import InMemoryRandomAccessStream

logger = logging.getLogger("autocar.ocr")


class OCR:
    """Windows 内置 OCR（支持中英文）"""

    def __init__(self, lang: str = "zh-CN"):
        self.lang = lang
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            try:
                lang = wg.Language(self.lang)
                self._engine = wocr.OcrEngine.try_create_from_language(lang)
                if self._engine is None:
                    # 回退到系统默认语言
                    self._engine = wocr.OcrEngine.try_create_from_language(
                        wg.Language("en")
                    )
                    logger.info("Windows OCR: 中文不可用，回退英文")
                else:
                    logger.info(f"Windows OCR 就绪 ({self.lang})")
            except Exception as e:
                logger.warning(f"Windows OCR 初始化失败: {e}")
                return None
        return self._engine

    def _image_to_stream(self, image_path: str) -> InMemoryRandomAccessStream:
        """PIL Image → Windows 流"""
        img = Image.open(image_path)
        buf = io.BytesIO()
        img.save(buf, format="bmp")
        stream = InMemoryRandomAccessStream()
        stream.write_bytes(buf.getvalue())
        stream.seek(0)
        return stream

    def text_from_image(self, image_path: str) -> str:
        """识别图片中的文字"""
        engine = self._get_engine()
        if not engine:
            return ""

        try:
            stream = self._image_to_stream(image_path)
            decoder = BitmapDecoder.create_async(stream).get()
            bitmap = decoder.get_software_async().get()

            result = engine.recognize_async(bitmap).get()
            return result.text.strip()
        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            return ""

    def text_with_boxes(self, image_path: str) -> List[Dict]:
        """识别文字及位置"""
        engine = self._get_engine()
        if not engine:
            return []

        try:
            stream = self._image_to_stream(image_path)
            decoder = BitmapDecoder.create_async(stream).get()
            bitmap = decoder.get_software_async().get()

            result = engine.recognize_async(bitmap).get()
            results = []
            for line in result.lines:
                text = line.text.strip()
                if not text:
                    continue
                r = line.bounding_rect
                results.append(
                    {
                        "text": text,
                        "conf": 100,
                        "x": int(r.x),
                        "y": int(r.y),
                        "w": int(r.width),
                        "h": int(r.height),
                    }
                )
            return results
        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            return []

    def search_text(self, image_path: str, keyword: str) -> Optional[Dict]:
        """在图片中搜索指定文字"""
        boxes = self.text_with_boxes(image_path)
        for box in boxes:
            if keyword.lower() in box["text"].lower():
                return box
        return None

    def is_available(self) -> bool:
        """检查 OCR 是否可用（Windows 10+ 始终可用）"""
        return self._get_engine() is not None
