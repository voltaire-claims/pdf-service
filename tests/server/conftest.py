import base64
import uuid
from typing import TYPE_CHECKING
from unittest.mock import patch

import pymupdf
import pytest

from voltaire.pdfservice.server.app import PydanticAPIFlask, create_app

if TYPE_CHECKING:
    from collections.abc import Generator

    from flask.testing import FlaskClient


def to_data_url(pdf_bytes: bytes) -> str:
    """Encode raw PDF bytes as a data URL for JSON requests."""
    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    return f"data:application/pdf;base64,{b64}"


@pytest.fixture
def app() -> PydanticAPIFlask:
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app: PydanticAPIFlask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def fixed_uuid() -> uuid.UUID:
    """Return a deterministic UUID for testing error reference IDs."""
    return uuid.UUID("aabbccdd-1122-3344-aabb-ccdd11223344")


@pytest.fixture
def fixed_ref_id(fixed_uuid: uuid.UUID) -> Generator[str]:
    """Patch uuid4 in the error handler to return a deterministic UUID."""
    with patch("voltaire.pdfservice.server.app.uuid.uuid4", return_value=fixed_uuid):
        yield str(fixed_uuid)


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Create a simple 4-page PDF with text on each page."""
    doc = pymupdf.open()
    for i in range(1, 5):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i}")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def single_page_pdf_bytes() -> bytes:
    """Create a single-page PDF."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello World")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def empty_pdf_bytes() -> bytes:
    """Create a PDF with no text (blank page)."""
    doc = pymupdf.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
