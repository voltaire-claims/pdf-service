import base64
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask.testing import FlaskClient


def test_from_html_success(client: FlaskClient) -> None:
    response = client.post(
        "/from-html",
        json={"html": "<p>Hello World</p>"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "file" in data
    assert data["file"].startswith("data:application/pdf;base64,")
    pdf_bytes = base64.b64decode(data["file"].split(",", 1)[1])
    assert pdf_bytes[:4] == b"%PDF"


def test_from_html_empty(client: FlaskClient, fixed_ref_id: str) -> None:
    response = client.post(
        "/from-html",
        json={"html": ""},
    )
    assert response.status_code == 422
    assert response.get_json() == {
        "message": "HTML content is empty",
        "reference_id": fixed_ref_id,
    }


def test_from_html_whitespace_only(client: FlaskClient, fixed_ref_id: str) -> None:
    response = client.post(
        "/from-html",
        json={"html": "   \n\t  "},
    )
    assert response.status_code == 422
    assert response.get_json() == {
        "message": "HTML content is empty",
        "reference_id": fixed_ref_id,
    }


def test_from_html_special_characters(client: FlaskClient) -> None:
    response = client.post(
        "/from-html",
        json={"html": "<p>&copy;, &reg;, &euro;, &pound;, &yen;</p>"},
    )
    assert response.status_code == 200
    data = response.get_json()
    pdf_bytes = base64.b64decode(data["file"].split(",", 1)[1])
    assert pdf_bytes[:4] == b"%PDF"
