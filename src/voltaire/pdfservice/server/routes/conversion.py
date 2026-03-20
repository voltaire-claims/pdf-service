"""HTML conversion and hashing routes."""

import base64
from hashlib import sha512
from typing import TYPE_CHECKING

import pymupdf

from voltaire.pdfservice.models.requests import FileUploadInput, FromHtmlRequest, ToHtmlInput
from voltaire.pdfservice.models.responses import (
    FromHtmlResponse,
    HashResponse,
    ServiceError,
    ToHtmlResponse,
)
from voltaire.pdfservice.server.pdf_to_html import (
    PDFToHTMLParsingError,
    PDFToHTMLService,
)
from voltaire.pdfservice.server.routes.helpers import (
    ERROR_RESPONSES,
    decode_data_url,
    open_pdf,
    select_pages,
)

if TYPE_CHECKING:
    from apiflask import APIFlask


def register_from_html_route(app: APIFlask) -> None:
    """Register the HTML-to-PDF conversion route."""

    @app.post("/from-html")
    @app.input(FromHtmlRequest, location="json", arg_name="body")
    @app.output(FromHtmlResponse)
    @app.doc(responses=ERROR_RESPONSES)
    def from_html(*, body: FromHtmlRequest) -> FromHtmlResponse:
        """Convert HTML to a PDF document."""
        if not body.html or not body.html.strip():
            raise ServiceError("HTML content is empty", 422)

        try:
            with pymupdf.open() as doc:
                page = doc.new_page(width=body.page_width, height=body.page_height)
                rect = pymupdf.Rect(
                    body.margin,
                    body.margin,
                    body.page_width - body.margin,
                    body.page_height - body.margin,
                )
                page.insert_htmlbox(rect, body.html)
                pdf_bytes = doc.tobytes()
        except (pymupdf.FileDataError, RuntimeError) as exc:
            raise ServiceError(
                "An internal error occurred during PDF conversion.",
                500,
            ) from exc

        b64 = base64.b64encode(pdf_bytes).decode("ascii")
        return FromHtmlResponse(file=f"data:application/pdf;base64,{b64}")


def register_to_html_route(app: APIFlask) -> None:
    """Register the PDF-to-HTML conversion route."""

    @app.post("/to-html")
    @app.input(ToHtmlInput, location="json", arg_name="body")
    @app.output(ToHtmlResponse)
    @app.doc(responses=ERROR_RESPONSES)
    def to_html(*, body: ToHtmlInput) -> ToHtmlResponse:
        """Convert a PDF to HTML with layout preservation."""
        with open_pdf(decode_data_url(body.file)) as doc:
            selected = select_pages(doc, body.pages)

            try:
                service = PDFToHTMLService()
                html = service.convert_pdf_to_html(doc, selected, body.name)
            except PDFToHTMLParsingError as exc:
                raise ServiceError(
                    "An internal error occurred while parsing the PDF.",
                    422,
                ) from exc

            return ToHtmlResponse(html=html)


def register_hash_route(app: APIFlask) -> None:
    """Register the PDF hashing route."""

    @app.post("/hash")
    @app.input(FileUploadInput, location="json", arg_name="body")
    @app.output(HashResponse)
    @app.doc(responses=ERROR_RESPONSES)
    def hash_pdf(*, body: FileUploadInput) -> HashResponse:
        """Compute a SHA-512 hash of the PDF text content."""
        with open_pdf(decode_data_url(body.file)) as doc:
            hasher = sha512()
            hasher.update("|".join(page.get_text() for page in doc).encode())

            return HashResponse(
                hash=hasher.hexdigest(),
                algorithm="sha512",
                page_count=doc.page_count,
            )
