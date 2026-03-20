import base64
import logging
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from tests.server.conftest import to_data_url
from voltaire.pdfservice.server.pdf_to_html import PDFToHTMLParsingError

if TYPE_CHECKING:
    from collections.abc import Generator

    from flask.testing import FlaskClient


@pytest.fixture
def _pymupdf_open_raises() -> Generator[None]:
    """Make pymupdf.open raise RuntimeError in the from-html route."""
    with patch(
        "voltaire.pdfservice.server.routes.conversion.pymupdf.open",
        side_effect=RuntimeError("secret internal detail"),
    ):
        yield


@pytest.fixture
def _parsing_raises() -> Generator[None]:
    """Make PDFToHTMLService.convert_pdf_to_html raise a parsing exception."""
    with patch(
        "voltaire.pdfservice.server.routes.conversion.PDFToHTMLService.convert_pdf_to_html",
        side_effect=PDFToHTMLParsingError("secret.pdf"),
    ):
        yield


@pytest.mark.usefixtures("_pymupdf_open_raises")
def test_from_html_conversion_error_returns_reference_id(
    client: FlaskClient, fixed_ref_id: str
) -> None:
    """Internal errors return a deterministic reference_id, not the exception message."""
    response = client.post(
        "/from-html",
        json={"html": "<p>test</p>"},
    )
    assert response.status_code == 500
    assert response.get_json() == {
        "message": "An internal error occurred during PDF conversion.",
        "reference_id": fixed_ref_id,
    }


@pytest.mark.usefixtures("_pymupdf_open_raises")
def test_from_html_conversion_error_logs_exception_with_ref_id(
    client: FlaskClient, fixed_ref_id: str, caplog: pytest.LogCaptureFixture
) -> None:
    """The error log contains both the reference_id and the exception."""
    with caplog.at_level(logging.ERROR):
        client.post(
            "/from-html",
            json={"html": "<p>test</p>"},
        )
    assert any(fixed_ref_id in record.message for record in caplog.records)


@pytest.mark.usefixtures("_parsing_raises")
def test_to_html_parsing_error_returns_reference_id(
    client: FlaskClient, fixed_ref_id: str, sample_pdf_bytes: bytes
) -> None:
    """PDF-to-HTML parsing errors return a deterministic reference_id, not exception details."""
    response = client.post(
        "/to-html",
        json={"file": to_data_url(sample_pdf_bytes)},
    )
    assert response.status_code == 422
    assert response.get_json() == {
        "message": "An internal error occurred while parsing the PDF.",
        "reference_id": fixed_ref_id,
    }


@pytest.mark.usefixtures("_parsing_raises")
def test_to_html_parsing_error_logs_exception_with_ref_id(
    client: FlaskClient,
    fixed_ref_id: str,
    sample_pdf_bytes: bytes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The parsing error log contains both the reference_id and the exception."""
    with caplog.at_level(logging.ERROR):
        client.post(
            "/to-html",
            json={"file": to_data_url(sample_pdf_bytes)},
        )
    assert any(fixed_ref_id in record.message for record in caplog.records)


def test_error_reference_ids_are_unique(client: FlaskClient) -> None:
    """Each error response gets a unique reference_id."""
    ref_ids = set()
    for _ in range(5):
        with patch(
            "voltaire.pdfservice.server.routes.conversion.pymupdf.open",
            side_effect=RuntimeError("fail"),
        ):
            response = client.post(
                "/from-html",
                json={"html": "<p>x</p>"},
            )
        ref_ids.add(response.get_json()["reference_id"])
    assert len(ref_ids) == 5


def test_known_errors_include_reference_id(client: FlaskClient) -> None:
    """All errors include a reference_id for log correlation."""
    b64 = base64.b64encode(b"").decode()
    response = client.post(
        "/validate",
        json={"file": f"data:application/pdf;base64,{b64}"},
    )
    assert response.status_code == 422
    assert "reference_id" in response.get_json()
