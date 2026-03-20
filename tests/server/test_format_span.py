"""Tests for bold/italic detection in convert_pdf_to_html output."""

import pymupdf

from voltaire.pdfservice.server.pdf_to_html import PDFToHTMLService


def _make_pdf(*, fontname: str = "helv", text: str = "hello") -> pymupdf.Document:
    """Create a single-page PDF with one line of text in the given font."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontname=fontname)
    return doc


class TestBoldItalicDetection:
    """Bold and italic styling should appear in the HTML output."""

    def test_plain_text(self) -> None:
        html = PDFToHTMLService().convert_pdf_to_html(_make_pdf())
        assert "font-weight:bold" not in html
        assert "font-style:italic" not in html

    def test_bold(self) -> None:
        html = PDFToHTMLService().convert_pdf_to_html(_make_pdf(fontname="hebo"))
        assert "font-weight:bold" in html
        assert "font-style:italic" not in html

    def test_italic(self) -> None:
        html = PDFToHTMLService().convert_pdf_to_html(_make_pdf(fontname="heit"))
        assert "font-style:italic" in html
        assert "font-weight:bold" not in html

    def test_bold_and_italic(self) -> None:
        html = PDFToHTMLService().convert_pdf_to_html(_make_pdf(fontname="hebi"))
        assert "font-weight:bold" in html
        assert "font-style:italic" in html
