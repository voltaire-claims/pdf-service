"""PDF inspection routes: validate, to-images, detect-type."""

import base64
from typing import TYPE_CHECKING

import pymupdf

from voltaire.pdfservice.models.requests import FileUploadInput, ToImagesInput
from voltaire.pdfservice.models.responses import (
    DetectTypeResponse,
    FontInfo,
    PageImage,
    PdfMetadata,
    ToImagesResponse,
    ValidateResponse,
)
from voltaire.pdfservice.server.routes.helpers import ERROR_RESPONSES, decode_data_url, open_pdf

if TYPE_CHECKING:
    from apiflask import APIFlask


def register_pdf_routes(app: APIFlask, max_page_limit: int) -> None:
    """Register PDF validation and imaging routes."""

    @app.post("/validate")
    @app.input(FileUploadInput, location="json", arg_name="body")
    @app.output(ValidateResponse)
    @app.doc(responses=ERROR_RESPONSES)
    def validate(*, body: FileUploadInput) -> ValidateResponse:
        """Validate a PDF file and return metadata."""
        with open_pdf(decode_data_url(body.file)) as doc:
            meta = doc.metadata or {}
            return ValidateResponse(
                valid=True,
                page_count=doc.page_count,
                metadata=PdfMetadata(
                    title=meta.get("title"),
                    author=meta.get("author"),
                ),
            )

    @app.post("/to-images")
    @app.input(ToImagesInput, location="json", arg_name="body")
    @app.output(ToImagesResponse)
    @app.doc(responses=ERROR_RESPONSES)
    def to_images(*, body: ToImagesInput) -> ToImagesResponse:
        """Convert PDF pages to base64-encoded images."""
        with open_pdf(decode_data_url(body.file)) as doc:
            page_limit = min(body.page_limit, max_page_limit)
            mat = pymupdf.Matrix(body.zoom, body.zoom)
            images = []
            img_format = body.format
            mime_type = "jpeg" if img_format == "JPEG" else img_format.lower()
            for i, page in enumerate(doc):
                if i >= page_limit:
                    break
                pixmap = page.get_pixmap(matrix=mat, dpi=body.dpi)
                img_bytes = pixmap.pil_tobytes(format=img_format)
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                images.append(
                    PageImage(
                        page=i + 1,
                        image=f"data:image/{mime_type};base64,{b64}",
                    ),
                )

            return ToImagesResponse(
                images=images,
                total_pages=doc.page_count,
                pages_converted=len(images),
            )


def register_detect_type_route(app: APIFlask) -> None:
    """Register the PDF type detection route."""

    @app.post("/detect-type")
    @app.input(FileUploadInput, location="json", arg_name="body")
    @app.output(DetectTypeResponse)
    @app.doc(responses=ERROR_RESPONSES)
    def detect_type(*, body: FileUploadInput) -> DetectTypeResponse:
        """Detect whether a PDF is text-based, image-based, or uses Type3 fonts."""
        with open_pdf(decode_data_url(body.file)) as doc:
            has_text = False
            has_type3_fonts = False
            fonts: list[FontInfo] = []

            for page_num, page in enumerate(doc, 1):
                if not has_text and page.get_text().strip():
                    has_text = True
                page_fonts = page.get_fonts()
                for font in page_fonts:
                    if font[2] == "Type3":
                        has_type3_fonts = True
                    fonts.append(FontInfo(name=font[3], type=font[2], page=page_num))

            if not has_text:
                pdf_type = "image"
            elif has_type3_fonts:
                pdf_type = "type3"
            else:
                pdf_type = "text"

            return DetectTypeResponse(
                type=pdf_type,
                has_extractable_text=has_text,
                has_type3_fonts=has_type3_fonts,
                page_count=doc.page_count,
                fonts=fonts,
            )
