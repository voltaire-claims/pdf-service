"""Async client for the Voltaire PDF microservice."""

import base64
import json
from typing import Self

import httpx

from voltaire.pdfservice.models.responses import (
    DetectTypeResponse,
    ExtractTextResponse,
    HashResponse,
    HealthResponse,
    ToHtmlResponse,
    ToImagesResponse,
    ValidateResponse,
)

HTTP_CLIENT_ERROR = 400


def _to_data_url(pdf_bytes: bytes) -> str:
    """Encode raw PDF bytes as a data URL."""
    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    return f"data:application/pdf;base64,{b64}"


class PdfServiceError(Exception):
    """Error returned by the PDF service API."""

    def __init__(self, error: str, message: str, status_code: int) -> None:
        """Initialize with error code, message, and HTTP status code."""
        self.error = error
        self.message = message
        self.status_code = status_code
        super().__init__(f"{error}: {message}")


class PdfServiceClient:
    """Async HTTP client for communicating with the PDF service."""

    def __init__(self, base_url: str = "http://pdf-service:8080") -> None:
        """Initialize the client with the service base URL."""
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=120.0)

    async def close(self) -> None:
        """Close the underlying HTTP client connection."""
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit the async context manager and close the client."""
        await self.close()

    def _check_response(self, response: httpx.Response) -> None:
        if response.status_code >= HTTP_CLIENT_ERROR:
            try:
                data = response.json()
                raise PdfServiceError(
                    error=data.get("error", "unknown"),
                    message=data.get("message", "Unknown error"),
                    status_code=response.status_code,
                )
            except json.JSONDecodeError:
                response.raise_for_status()

    async def health(self) -> HealthResponse:
        """Check the service health status."""
        resp = await self._client.get("/health")
        self._check_response(resp)
        return HealthResponse.model_validate(resp.json())

    async def validate(self, pdf_bytes: bytes) -> ValidateResponse:
        """Validate a PDF and return metadata."""
        resp = await self._client.post(
            "/validate",
            json={"file": _to_data_url(pdf_bytes)},
        )
        self._check_response(resp)
        return ValidateResponse.model_validate(resp.json())

    async def to_images(
        self,
        pdf_bytes: bytes,
        dpi: int = 300,
        *,
        image_format: str = "PNG",
        zoom: float = 2.0,
        page_limit: int = 50,
    ) -> ToImagesResponse:
        """Convert PDF pages to base64-encoded images."""
        resp = await self._client.post(
            "/to-images",
            json={
                "file": _to_data_url(pdf_bytes),
                "dpi": dpi,
                "format": image_format,
                "zoom": zoom,
                "page_limit": page_limit,
            },
        )
        self._check_response(resp)
        return ToImagesResponse.model_validate(resp.json())

    async def extract_text(
        self,
        pdf_bytes: bytes,
        pages: list[int] | None = None,
        header_pixels: float = 0,
        footer_pixels: float = 0,
    ) -> ExtractTextResponse:
        """Extract text from a PDF, returning text for each page separately."""
        payload: dict = {
            "file": _to_data_url(pdf_bytes),
            "header_pixels": header_pixels,
            "footer_pixels": footer_pixels,
        }
        if pages is not None:
            payload["pages"] = pages
        resp = await self._client.post("/extract-text", json=payload)
        self._check_response(resp)
        return ExtractTextResponse.model_validate(resp.json())

    async def detect_type(self, pdf_bytes: bytes) -> DetectTypeResponse:
        """Detect whether a PDF is text-based, image-based, or uses Type3 fonts."""
        resp = await self._client.post(
            "/detect-type",
            json={"file": _to_data_url(pdf_bytes)},
        )
        self._check_response(resp)
        return DetectTypeResponse.model_validate(resp.json())

    async def from_html(
        self,
        html: str,
        page_width: float = 612,
        page_height: float = 792,
        margin: float = 72,
    ) -> bytes:
        """Convert HTML to a PDF document."""
        resp = await self._client.post(
            "/from-html",
            json={
                "html": html,
                "page_width": page_width,
                "page_height": page_height,
                "margin": margin,
            },
        )
        self._check_response(resp)
        data_url: str = resp.json()["file"]
        _, encoded = data_url.split(",", 1)
        return base64.b64decode(encoded)

    async def to_html(
        self,
        pdf_bytes: bytes,
        pages: list[int] | None = None,
        name: str = "",
    ) -> ToHtmlResponse:
        """Convert a PDF to HTML with layout preservation."""
        payload: dict = {
            "file": _to_data_url(pdf_bytes),
            "name": name,
        }
        if pages is not None:
            payload["pages"] = pages
        resp = await self._client.post("/to-html", json=payload)
        self._check_response(resp)
        return ToHtmlResponse.model_validate(resp.json())

    async def hash_pdf(self, pdf_bytes: bytes) -> HashResponse:
        """Compute a SHA-512 hash of the PDF text content."""
        resp = await self._client.post(
            "/hash",
            json={"file": _to_data_url(pdf_bytes)},
        )
        self._check_response(resp)
        return HashResponse.model_validate(resp.json())
