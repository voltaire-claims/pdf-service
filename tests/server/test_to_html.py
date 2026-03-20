import base64
from typing import TYPE_CHECKING

from tests.server.conftest import to_data_url

if TYPE_CHECKING:
    from flask.testing import FlaskClient


def test_to_html_success(client: FlaskClient, sample_pdf_bytes: bytes) -> None:
    response = client.post(
        "/to-html",
        json={"file": to_data_url(sample_pdf_bytes)},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "html" in data
    assert "<html>" in data["html"]


def test_to_html_with_name(client: FlaskClient, sample_pdf_bytes: bytes) -> None:
    response = client.post(
        "/to-html",
        json={
            "file": to_data_url(sample_pdf_bytes),
            "name": "Test Document",
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "html" in data


def test_to_html_with_page_selection(client: FlaskClient, sample_pdf_bytes: bytes) -> None:
    response = client.post(
        "/to-html",
        json={
            "file": to_data_url(sample_pdf_bytes),
            "pages": [1, 3],
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "html" in data
    assert "<html>" in data["html"]


def test_to_html_corrupt_pdf(client: FlaskClient) -> None:
    b64 = base64.b64encode(b"not a pdf").decode()
    response = client.post(
        "/to-html",
        json={"file": f"data:application/pdf;base64,{b64}"},
    )
    assert response.status_code == 422
