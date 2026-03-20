# Copyright (C) 2026 Voltaire Claims
# SPDX-License-Identifier: AGPL-3.0-only

"""Request models for PDF service endpoints."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_DATA_URL_EXAMPLE = "data:application/pdf;base64,JVBERi0xLjQg..."

DataURL = Annotated[
    str,
    Field(
        title="DataURL",
        description="Base64-encoded file as a data URL.",
        examples=[_DATA_URL_EXAMPLE],
    ),
]


class FileUploadInput(BaseModel):
    """JSON input for endpoints that only accept a PDF file."""

    model_config = ConfigDict(json_schema_extra={"example": {"file": _DATA_URL_EXAMPLE}})

    file: DataURL


class ToImagesInput(BaseModel):
    """JSON input for the PDF-to-images endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file": _DATA_URL_EXAMPLE,
                "format": "PNG",
                "dpi": 300,
                "zoom": 2.0,
                "page_limit": 50,
            },
        }
    )

    file: DataURL
    format: Literal["PNG", "JPEG", "PNM", "PGM", "PPM", "PBM", "PAM", "PSD", "PS"] = Field(
        default="PNG",
        description="Image format for rendered pages",
    )
    dpi: int = Field(default=300, ge=72, le=600, description="DPI for rendering")
    zoom: float = Field(default=2.0, gt=0, le=5.0, description="Zoom factor")
    page_limit: int = Field(default=50, ge=1, description="Maximum pages to convert")


class ExtractTextInput(BaseModel):
    """JSON input for the text extraction endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file": _DATA_URL_EXAMPLE,
                "header_pixels": 0,
                "footer_pixels": 0,
                "pages": [1, 2, 3],
            },
        }
    )

    file: DataURL
    header_pixels: float = Field(
        default=0,
        ge=0,
        description="Pixels to exclude from top of each page",
    )
    footer_pixels: float = Field(
        default=0,
        ge=0,
        description="Pixels to exclude from bottom of each page",
    )
    pages: list[int] | None = Field(
        default=None,
        description="1-based page numbers to extract (defaults to all pages)",
    )


class ToHtmlInput(BaseModel):
    """JSON input for the PDF-to-HTML endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file": _DATA_URL_EXAMPLE,
                "pages": [1, 2, 3],
                "name": "quarterly-report.pdf",
            },
        }
    )

    file: DataURL
    pages: list[int] | None = Field(default=None, description="1-based page numbers to extract")
    name: str = Field(default="", description="Document name for error reporting")


class FromHtmlRequest(BaseModel):
    """JSON request body for the HTML-to-PDF endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "html": "<html><body><h1>Invoice #1042</h1><p>Total: $250.00</p></body></html>",
                "page_width": 612,
                "page_height": 792,
                "margin": 72,
            },
        }
    )

    html: str = Field(description="HTML string to render as PDF")
    page_width: float = Field(default=612, gt=0, description="Page width in points (8.5 x 72)")
    page_height: float = Field(default=792, gt=0, description="Page height in points (11 x 72)")
    margin: float = Field(default=72, ge=0, description="Margin in points (1 inch)")

    @model_validator(mode="after")
    def _check_margin_fits(self) -> FromHtmlRequest:
        if self.margin * 2 >= self.page_width:
            msg = "Margin is too large for the page width"
            raise ValueError(msg)
        if self.margin * 2 >= self.page_height:
            msg = "Margin is too large for the page height"
            raise ValueError(msg)
        return self
