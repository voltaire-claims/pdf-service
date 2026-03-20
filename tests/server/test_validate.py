import base64
from typing import TYPE_CHECKING

from tests.server.conftest import to_data_url

if TYPE_CHECKING:
    from flask.testing import FlaskClient


def test_validate_valid_pdf(client: FlaskClient, sample_pdf_bytes: bytes) -> None:
    response = client.post(
        "/validate",
        json={"file": to_data_url(sample_pdf_bytes)},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "valid": True,
        "page_count": 4,
        "metadata": {"title": "", "author": ""},
    }


def test_validate_empty_file(client: FlaskClient, fixed_ref_id: str) -> None:
    b64 = base64.b64encode(b"").decode()
    response = client.post(
        "/validate",
        json={"file": f"data:application/pdf;base64,{b64}"},
    )
    assert response.status_code == 422
    assert response.get_json() == {
        "message": "Empty file",
        "reference_id": fixed_ref_id,
    }


def test_validate_corrupt_pdf(client: FlaskClient, fixed_ref_id: str) -> None:
    b64 = base64.b64encode(b"not a pdf").decode()
    response = client.post(
        "/validate",
        json={"file": f"data:application/pdf;base64,{b64}"},
    )
    assert response.status_code == 422
    assert response.get_json() == {
        "message": "Could not open as PDF",
        "reference_id": fixed_ref_id,
    }


def test_validate_no_file(client: FlaskClient) -> None:
    response = client.post("/validate", json={})
    assert response.status_code == 422
