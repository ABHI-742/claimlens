"""OCR providers. Plain-text files bypass OCR entirely."""

import io

import boto3

from app.core.config import settings
from app.services.interfaces import OcrProvider, OcrResult

TEXT_TYPES = {"text/plain", "text/markdown", "text/csv"}


class TesseractOcr:
    """Local OCR with Tesseract; PDFs are rasterised with pdf2image (poppler)."""

    def extract(self, data: bytes, mime_type: str) -> OcrResult:
        import pytesseract
        from PIL import Image

        if mime_type == "application/pdf":
            from pdf2image import convert_from_bytes

            images = convert_from_bytes(data, dpi=300)
        else:
            images = [Image.open(io.BytesIO(data))]

        texts: list[str] = []
        confidences: list[float] = []
        for image in images:
            result = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            words = [w for w in result["text"] if w.strip()]
            texts.append(" ".join(words))
            confidences += [
                float(c) / 100
                for c, w in zip(result["conf"], result["text"], strict=False)
                if w.strip() and float(c) >= 0
            ]
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return OcrResult(text="\n\n".join(texts), confidence=round(confidence, 3))


class TextractOcr:
    """AWS Textract synchronous text detection (images and single-page PDFs)."""

    def __init__(self) -> None:
        self._client = boto3.client("textract", region_name=settings.aws_region)

    def extract(self, data: bytes, mime_type: str) -> OcrResult:
        response = self._client.detect_document_text(Document={"Bytes": data})
        lines = [b for b in response["Blocks"] if b["BlockType"] == "LINE"]
        text = "\n".join(b["Text"] for b in lines)
        confidence = sum(b["Confidence"] for b in lines) / len(lines) / 100 if lines else 0.0
        return OcrResult(text=text, confidence=round(confidence, 3))


class OcrRouter:
    """Routes text files straight through and everything else to the configured OCR provider."""

    def __init__(self, provider: OcrProvider) -> None:
        self.provider = provider

    def extract(self, data: bytes, mime_type: str) -> OcrResult:
        if mime_type in TEXT_TYPES:
            return OcrResult(text=data.decode("utf-8", errors="replace"), confidence=1.0)
        return self.provider.extract(data, mime_type)


def build_ocr() -> OcrRouter:
    provider: OcrProvider = TextractOcr() if settings.ocr_provider == "textract" else TesseractOcr()
    return OcrRouter(provider)
