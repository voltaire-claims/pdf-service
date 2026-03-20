# Copyright (C) 2026 Voltaire Claims
# SPDX-License-Identifier: AGPL-3.0-only

"""Response models for PDF service endpoints."""

from pydantic import BaseModel, ConfigDict, Field

from voltaire.pdfservice.models.requests import (
    DataURL,  # noqa: TC001  # needed at runtime by Pydantic
)


class FieldError(BaseModel):
    """Validation error for a single input field."""

    name: str = Field(description="Name of the field that failed validation")
    errors: list[str] = Field(description="List of validation error messages for this field")


class ErrorResponse(BaseModel):
    """Standard error response returned by the service."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Validation error",
                "reference_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "fields": [
                    {"name": "dpi", "errors": ["Input should be greater than or equal to 72"]},
                ],
            },
        }
    )

    message: str = Field(description="Human-readable error description")
    reference_id: str | None = Field(
        default=None,
        description="Error reference ID for log correlation",
    )
    fields: list[FieldError] | None = Field(
        default=None,
        description="Per-field validation errors, present only for input validation failures",
    )


class ServiceError(Exception):
    """Raise from route handlers to return an ErrorResponse."""

    def __init__(self, message: str, status_code: int) -> None:
        """Create a service error with a message and HTTP status."""
        self.status_code = status_code
        super().__init__(message)

    def response(self, reference_id: str) -> tuple[ErrorResponse, int]:
        """Return an ``(ErrorResponse, status_code)`` tuple for Flask."""
        return ErrorResponse(
            message=str(self),
            reference_id=reference_id,
        ), self.status_code


class HealthResponse(BaseModel):
    """Response from the health check endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"status": "healthy", "version": "1.2.0"},
        }
    )

    status: str = Field(description="Service health status")
    version: str = Field(description="Service version")


class PdfMetadata(BaseModel):
    """Basic PDF metadata extracted during validation."""

    title: str | None = Field(default=None, description="PDF title")
    author: str | None = Field(default=None, description="PDF author")


class ValidateResponse(BaseModel):
    """Response from the PDF validation endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "valid": True,
                "page_count": 12,
                "metadata": {"title": "Quarterly Report Q4 2025", "author": "Jane Smith"},
            },
        }
    )

    valid: bool = Field(description="Whether the PDF is valid")
    page_count: int = Field(default=0, description="Number of pages")
    metadata: PdfMetadata | None = Field(default=None, description="PDF metadata")


class PageImage(BaseModel):
    """A single rendered page image."""

    page: int = Field(description="Page number (1-based)")
    image: DataURL = Field(
        description="Rendered image as a data URL",
        examples=["data:image/png;base64,iVBORw0KGgo..."],
    )


class ToImagesResponse(BaseModel):
    """Response from the PDF-to-images endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "images": [
                    {"page": 1, "image": "data:image/png;base64,iVBORw0KGgo..."},
                ],
                "total_pages": 5,
                "pages_converted": 1,
            },
        }
    )

    images: list[PageImage] = Field(description="List of page images")
    total_pages: int = Field(description="Total pages in the PDF")
    pages_converted: int = Field(description="Number of pages converted")


class PageText(BaseModel):
    """Text content for a single page."""

    page: int = Field(description="Page number (1-based)")
    text: str = Field(description="Page text")


class ExtractTextResponse(BaseModel):
    """Response for text extraction."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pages": [
                    {"page": 1, "text": "Chapter 1: Introduction\n\nThis document describes..."},
                    {"page": 2, "text": "1.1 Background\n\nThe project was initiated..."},
                ],
                "page_count": 2,
            },
        }
    )

    pages: list[PageText] = Field(description="Per-page text")
    page_count: int = Field(description="Total pages in the PDF")


class FontInfo(BaseModel):
    """Font information for a single page."""

    name: str = Field(description="Font name")
    type: str = Field(description="Font type")
    page: int = Field(description="Page number (1-based)")


class DetectTypeResponse(BaseModel):
    """Response from the PDF type detection endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "text",
                "has_extractable_text": True,
                "has_type3_fonts": False,
                "page_count": 12,
                "fonts": [
                    {"name": "Helvetica", "type": "Type1", "page": 1},
                    {"name": "TimesNewRoman", "type": "TrueType", "page": 2},
                ],
            },
        }
    )

    type: str = Field(description="PDF type: text, image, or type3")
    has_extractable_text: bool = Field(description="Whether text can be extracted")
    has_type3_fonts: bool = Field(description="Whether Type3 fonts are present")
    page_count: int = Field(description="Total pages")
    fonts: list[FontInfo] = Field(description="Font information")


class ToHtmlResponse(BaseModel):
    """Response from the PDF-to-HTML endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "html": "<html><body><p>Chapter 1: Introduction</p></body></html>",
            },
        }
    )

    html: str = Field(description="HTML output")


class FromHtmlResponse(BaseModel):
    """Response from the HTML-to-PDF endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"file": "data:application/pdf;base64,JVBERi0xLjQg..."},
        }
    )

    file: DataURL = Field(
        description="PDF file as a data URL",
        examples=["data:application/pdf;base64,JVBERi0xLjQg..."],
    )


class HashResponse(BaseModel):
    """Response from the PDF hashing endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hash": (
                    "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce"
                    "47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e"
                ),
                "algorithm": "sha512",
                "page_count": 12,
            },
        }
    )

    hash: str = Field(description="SHA-512 hash hex digest")
    algorithm: str = Field(description="Hash algorithm used")
    page_count: int = Field(description="Total pages in the PDF")
