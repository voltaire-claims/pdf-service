"""Text extraction routes."""

from typing import TYPE_CHECKING

from voltaire.pdfservice.models.requests import ExtractTextInput
from voltaire.pdfservice.models.responses import (
    ExtractTextResponse,
    PageText,
)
from voltaire.pdfservice.server.routes.helpers import (
    ERROR_RESPONSES,
    decode_data_url,
    get_page_text,
    open_pdf,
    select_pages,
)

if TYPE_CHECKING:
    from apiflask import APIFlask


def register_extraction_routes(app: APIFlask) -> None:
    """Register text extraction routes."""

    @app.post("/extract-text")
    @app.input(ExtractTextInput, location="json", arg_name="body")
    @app.output(ExtractTextResponse)
    @app.doc(responses=ERROR_RESPONSES)
    def extract_text(*, body: ExtractTextInput) -> ExtractTextResponse:
        """Extract text from a PDF, returning text for each page separately."""
        with open_pdf(decode_data_url(body.file)) as doc:
            selected = select_pages(doc, body.pages)

            page_results = [
                PageText(
                    page=p,
                    text=get_page_text(
                        doc[p - 1],
                        body.header_pixels,
                        body.footer_pixels,
                    ),
                )
                for p in selected
            ]
            return ExtractTextResponse(pages=page_results, page_count=doc.page_count)
