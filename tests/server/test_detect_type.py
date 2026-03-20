from typing import TYPE_CHECKING

from tests.server.conftest import to_data_url

if TYPE_CHECKING:
    from flask.testing import FlaskClient


def test_detect_type_text_pdf(client: FlaskClient, sample_pdf_bytes: bytes) -> None:
    response = client.post(
        "/detect-type",
        json={"file": to_data_url(sample_pdf_bytes)},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["type"] == "text"
    assert data["has_extractable_text"] is True
    assert data["has_type3_fonts"] is False
    assert data["page_count"] == 4


def test_detect_type_image_pdf(client: FlaskClient, empty_pdf_bytes: bytes) -> None:
    response = client.post(
        "/detect-type",
        json={"file": to_data_url(empty_pdf_bytes)},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["type"] == "image"
    assert data["has_extractable_text"] is False
