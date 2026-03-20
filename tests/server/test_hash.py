from hashlib import sha512
from io import BytesIO
from typing import TYPE_CHECKING

import pymupdf

from tests.server.conftest import to_data_url

if TYPE_CHECKING:
    from flask.testing import FlaskClient


def test_hash_deterministic(client: FlaskClient, sample_pdf_bytes: bytes) -> None:
    response1 = client.post(
        "/hash",
        json={"file": to_data_url(sample_pdf_bytes)},
    )
    response2 = client.post(
        "/hash",
        json={"file": to_data_url(sample_pdf_bytes)},
    )
    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.get_json()["hash"] == response2.get_json()["hash"]


def test_hash_matches_formula(client: FlaskClient, sample_pdf_bytes: bytes) -> None:
    response = client.post(
        "/hash",
        json={"file": to_data_url(sample_pdf_bytes)},
    )
    assert response.status_code == 200
    data = response.get_json()

    # Verify against the exact formula
    doc = pymupdf.open(stream=BytesIO(sample_pdf_bytes))
    hasher = sha512()
    hasher.update("|".join(page.get_text() for page in doc).encode())
    expected = hasher.hexdigest()
    doc.close()

    assert data["hash"] == expected
    assert data["algorithm"] == "sha512"
    assert data["page_count"] == 4


def test_hash_different_pdfs(
    client: FlaskClient, sample_pdf_bytes: bytes, single_page_pdf_bytes: bytes
) -> None:
    response1 = client.post(
        "/hash",
        json={"file": to_data_url(sample_pdf_bytes)},
    )
    response2 = client.post(
        "/hash",
        json={"file": to_data_url(single_page_pdf_bytes)},
    )
    assert response1.get_json()["hash"] != response2.get_json()["hash"]
