from app.integrations.ocr.base import OCRProvider


class DocumentAIProvider(OCRProvider):
    """
    Google Document AI (plan C.1: "OCR: Google Document AI (primary),
    Tesseract fallback ... Indian court scans are poor quality; budget
    for Document AI").

    Left unimplemented until a GCP project + Document AI processor are
    provisioned (plan C.1 "Accounts/keys to obtain in Week 1"). Wiring
    this in later is additive: `app/integrations/ocr/factory.py` will
    prefer this provider automatically once GOOGLE_APPLICATION_CREDENTIALS
    is set, falling back to Tesseract on failure exactly as today.
    """

    async def extract_text(self, file_bytes: bytes, mime_type: str) -> str:
        raise NotImplementedError(
            "Google Document AI is not configured. Set "
            "GOOGLE_APPLICATION_CREDENTIALS and a processor ID, or use "
            "FAKE_MODE=true / rely on the Tesseract fallback for now."
        )
