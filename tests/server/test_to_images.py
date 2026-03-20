import base64
from typing import TYPE_CHECKING

from tests.server.conftest import to_data_url

if TYPE_CHECKING:
    from flask.testing import FlaskClient


def test_to_images_defaults(client: FlaskClient, sample_pdf_bytes: bytes) -> None:
    response = client.post(
        "/to-images",
        json={"file": to_data_url(sample_pdf_bytes)},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["total_pages"] == 4
    assert data["pages_converted"] == 4
    assert len(data["images"]) == 4
    for i, img in enumerate(data["images"], 1):
        assert img["page"] == i
        assert "image" in img
        assert img["image"].startswith("data:image/png;base64,")
        b64_part = img["image"].split(",", 1)[1]
        decoded = base64.b64decode(b64_part)
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"


def test_to_images_page_limit(client: FlaskClient, sample_pdf_bytes: bytes) -> None:
    response = client.post(
        "/to-images",
        json={
            "file": to_data_url(sample_pdf_bytes),
            "page_limit": 2,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["pages_converted"] == 2
    assert len(data["images"]) == 2


def test_to_images_jpeg_format(client: FlaskClient, single_page_pdf_bytes: bytes) -> None:
    response = client.post(
        "/to-images",
        json={
            "file": to_data_url(single_page_pdf_bytes),
            "format": "JPEG",
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["images"]) == 1
    assert data["images"][0]["image"].startswith("data:image/jpeg;base64,")


def test_to_images_invalid_pdf(client: FlaskClient) -> None:
    b64 = base64.b64encode(b"bad").decode()
    response = client.post(
        "/to-images",
        json={"file": f"data:application/pdf;base64,{b64}"},
    )
    assert response.status_code == 422
