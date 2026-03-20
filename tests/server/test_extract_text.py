from typing import TYPE_CHECKING

from tests.server.conftest import to_data_url

if TYPE_CHECKING:
    from flask.testing import FlaskClient


def test_extract_text(client: FlaskClient, sample_pdf_bytes: bytes) -> None:
    response = client.post(
        "/extract-text",
        json={"file": to_data_url(sample_pdf_bytes)},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "pages" in data
    assert len(data["pages"]) == 4
    assert data["page_count"] == 4
    for page_data in data["pages"]:
        assert "page" in page_data
        assert "text" in page_data


def test_extract_text_specific_pages(client: FlaskClient, sample_pdf_bytes: bytes) -> None:
    response = client.post(
        "/extract-text",
        json={
            "file": to_data_url(sample_pdf_bytes),
            "pages": [1, 3],
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["pages"]) == 2
    assert data["pages"][0]["page"] == 1
    assert data["pages"][1]["page"] == 3
    assert "Page 1" in data["pages"][0]["text"]
    assert "Page 3" in data["pages"][1]["text"]


def test_extract_text_with_header_footer_clipping(
    client: FlaskClient, sample_pdf_bytes: bytes
) -> None:
    response = client.post(
        "/extract-text",
        json={
            "file": to_data_url(sample_pdf_bytes),
            "header_pixels": 100,
            "footer_pixels": 100,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["pages"]) == 4


def test_extract_text_excessive_clipping_returns_empty(
    client: FlaskClient, single_page_pdf_bytes: bytes
) -> None:
    response = client.post(
        "/extract-text",
        json={
            "file": to_data_url(single_page_pdf_bytes),
            "header_pixels": 9999,
            "footer_pixels": 9999,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["pages"][0]["text"] == ""


def test_extract_text_empty_pages_list(client: FlaskClient, sample_pdf_bytes: bytes) -> None:
    response = client.post(
        "/extract-text",
        json={
            "file": to_data_url(sample_pdf_bytes),
            "pages": [],
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["pages"]) == 0


def test_extract_text_page_out_of_range(
    client: FlaskClient, sample_pdf_bytes: bytes, fixed_ref_id: str
) -> None:
    response = client.post(
        "/extract-text",
        json={
            "file": to_data_url(sample_pdf_bytes),
            "pages": [1, 99],
        },
    )
    assert response.status_code == 422
    assert response.get_json() == {
        "message": "Page 99 out of range (1-4)",
        "reference_id": fixed_ref_id,
    }
