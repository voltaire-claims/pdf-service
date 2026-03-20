# Copyright (C) 2026 Voltaire Claims
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared helpers for route handlers."""

from __future__ import annotations

import base64
import re
from typing import Any

import pymupdf

from voltaire.pdfservice.models.responses import ServiceError

_ERROR_SCHEMA_REF = {"$ref": "#/components/schemas/ErrorResponse"}


def _error_response(description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {"application/json": {"schema": _ERROR_SCHEMA_REF}},
    }


ERROR_RESPONSES: dict[int, dict[str, Any]] = {
    413: _error_response("Request body too large"),
    422: _error_response("Validation or processing error"),
    500: _error_response("Internal server error"),
}

_DATA_URL_RE = re.compile(r"^data:[^;]+;base64,")


def decode_data_url(data_url: str) -> bytes:
    """Decode a data URL (e.g. ``data:application/pdf;base64,...``) to raw bytes."""
    match = _DATA_URL_RE.match(data_url)
    if not match:
        raise ServiceError("Invalid data URL: expected data:<mediatype>;base64,<data>", 422)
    b64_data = data_url[match.end() :]
    try:
        return base64.b64decode(b64_data)
    except Exception as exc:
        raise ServiceError("Invalid base64 in data URL", 422) from exc


def open_pdf(file_bytes: bytes) -> pymupdf.Document:
    """Open a PDF from raw bytes, raising :class:`ServiceError` on failure."""
    if not file_bytes:
        raise ServiceError("Empty file", 422)
    try:
        return pymupdf.open(stream=file_bytes, filetype="pdf")
    except pymupdf.FileDataError as exc:
        raise ServiceError("Could not open as PDF", 422) from exc


def select_pages(
    doc: pymupdf.Document,
    pages: list[int] | None = None,
) -> list[int]:
    """Validate a page selection against the document, raising :class:`ServiceError` on failure."""
    if pages is not None:
        for p in pages:
            if p < 1 or p > doc.page_count:
                raise ServiceError(
                    f"Page {p} out of range (1-{doc.page_count})",
                    422,
                )
        return pages
    return list(range(1, doc.page_count + 1))


def get_page_text(
    page: pymupdf.Page,
    header_pixels: float,
    footer_pixels: float,
) -> str:
    """Extract text from a page, optionally clipping header/footer regions."""
    if header_pixels > 0 or footer_pixels > 0:
        y0 = min(page.rect.y0 + header_pixels, page.rect.y1)
        y1 = max(page.rect.y1 - footer_pixels, page.rect.y0)
        if y1 <= y0:
            return ""
        clip = pymupdf.Rect(page.rect.x0, y0, page.rect.x1, y1)
        return page.get_text(clip=clip)
    return page.get_text()
