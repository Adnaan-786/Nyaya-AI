"""Google Document AI — C.1's primary OCR provider ("Indian court scans are poor").

Talks to the v1 REST endpoint rather than the `google-cloud-documentai` client, for
the same reason app/integrations/fcm.py talks to FCM over HTTP: google-auth is already
a dependency (it mints the push token), and a single POST does not justify installing
a second Google SDK.

Unconfigured is the normal state on this deployment, and it raises rather than
returning empty — the factory reads that as "try the next provider", and if there
isn't one the document lands in `failed` saying so.
"""

import asyncio
import base64
import logging

import httpx

from app.core.config import get_settings
from app.integrations.ocr.base import OcrProvider, OcrProviderError

logger = logging.getLogger(__name__)
settings = get_settings()

SCOPE = "https://www.googleapis.com/auth/cloud-platform"
# The location is part of the hostname *and* of the resource path; they must agree, or
# the API answers 404 for a processor that plainly exists.
ENDPOINT = (
    "https://{location}-documentai.googleapis.com/v1/"
    "projects/{project}/locations/{location}/processors/{processor}:process"
)

# Google caps the synchronous `:process` call at 20 MB. Anything larger needs the
# batch API, which writes results to a GCS bucket and is polled — a different shape of
# integration, and one this pipeline has nowhere to put yet.
MAX_SYNC_BYTES = 20 * 1024 * 1024

# A 40-page scan is minutes of work on Google's side, and this already runs in a
# background task, so the only thing a short timeout would buy is a failed document.
REQUEST_TIMEOUT_SECONDS = 180


class DocumentAIProvider(OcrProvider):
    name = "Document AI"

    def is_configured(self) -> bool:
        return bool(
            settings.document_ai_project_id
            and settings.document_ai_processor_id
            and settings.google_credentials_path
        )

    async def extract_text(self, data: bytes, mime_type: str) -> str:
        if not self.is_configured():
            raise OcrProviderError(
                "Google Document AI is not configured. Set DOCUMENT_AI_PROJECT_ID, "
                "DOCUMENT_AI_PROCESSOR_ID and GOOGLE_CREDENTIALS_PATH."
            )

        if len(data) > MAX_SYNC_BYTES:
            raise OcrProviderError(
                f"This file is {len(data) // (1024 * 1024)} MB; Document AI processes "
                f"at most {MAX_SYNC_BYTES // (1024 * 1024)} MB in one request."
            )

        token = await self._access_token()
        url = ENDPOINT.format(
            location=settings.document_ai_location,
            project=settings.document_ai_project_id,
            processor=settings.document_ai_processor_id,
        )
        payload = {
            "rawDocument": {
                "content": base64.b64encode(data).decode(),
                "mimeType": mime_type,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    url, headers={"Authorization": f"Bearer {token}"}, json=payload
                )
        except httpx.HTTPError as exc:
            raise OcrProviderError(f"Document AI could not be reached: {exc}") from exc

        if response.status_code >= 400:
            # Truncated: the body carries the whole request context on some errors, and
            # this string ends up in a database column somebody has to read.
            raise OcrProviderError(
                f"Document AI rejected the file ({response.status_code}): "
                f"{response.text[:300]}"
            )

        return response.json().get("document", {}).get("text", "")

    async def _access_token(self) -> str:
        try:
            from google.auth.transport.requests import Request  # type: ignore[import-untyped]
            from google.oauth2 import service_account  # type: ignore[import-untyped]
        except ImportError as exc:
            # Reports the real import error: google-auth can be installed and still
            # fail here because its default transport needs `requests`.
            raise OcrProviderError(
                f"cannot call Document AI: {exc}. "
                "Install with: pip install google-auth requests"
            ) from exc

        def _mint() -> str:
            credentials = service_account.Credentials.from_service_account_file(
                settings.google_credentials_path, scopes=[SCOPE]
            )
            credentials.refresh(Request())
            return credentials.token

        try:
            # Blocking, and cached for an hour by the library — but this runs inside a
            # background task on the request loop, so it does not get to block it.
            return await asyncio.to_thread(_mint)
        except Exception as exc:  # noqa: BLE001 - a bad key file must not 500 the worker
            raise OcrProviderError(
                f"Document AI credentials could not be loaded: {exc}"
            ) from exc
