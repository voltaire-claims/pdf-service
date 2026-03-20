# Voltaire PDF Service

A microservice for PDF manipulation and conversion, built with PyMuPDF and Flask.

## Capabilities

- **Validation** — Validate PDF files and extract metadata (title, author, page count).
- **Type Detection** — Classify PDFs as text-based, image-based, or Type3-font-based, with detailed font information.
- **Text Extraction** — Extract text from PDFs in plain or per-page mode, with optional header/footer exclusion.
- **PDF to Images** — Render PDF pages to base64-encoded images with configurable DPI, zoom, and format.
- **PDF to HTML** — Convert PDFs to HTML with layout preservation.
- **HTML to PDF** — Generate PDFs from HTML content with configurable page dimensions and margins.
- **Hashing** — Compute SHA-512 hashes of PDF text content for content verification.

## Architecture

The project provides two components:

- **Server** — A Flask (APIFlask) application exposing a JSON API. All file inputs and outputs use data URLs (`data:application/pdf;base64,...`).
- **Client** — An async Python client (`PdfServiceClient`) using HTTPX for communicating with the server.

## Installation

Install from a [GitHub release](https://github.com/voltaire-claims/pdf-service/releases):

```bash
# Client only (async HTTP client + models)
pip install "voltaire-pdf-service[client] @ https://github.com/voltaire-claims/pdf-service/releases/latest/download/voltaire_pdf_service-0.1.4-py3-none-any.whl"

# Server only
pip install "voltaire-pdf-service[server] @ https://github.com/voltaire-claims/pdf-service/releases/latest/download/voltaire_pdf_service-0.1.4-py3-none-any.whl"

# Both
pip install "voltaire-pdf-service[client,server] @ https://github.com/voltaire-claims/pdf-service/releases/latest/download/voltaire_pdf_service-0.1.4-py3-none-any.whl"
```

Or install directly from the repository:

```bash
pip install "voltaire-pdf-service[client] @ git+https://github.com/voltaire-claims/pdf-service.git"
```

## Running the Server

### With Docker (recommended)

```bash
docker run -p 8080:80 \
  -e MAX_PDF_SIZE_MB=50 \
  -e MAX_HTML_SIZE_MB=5 \
  -e MAX_PAGE_LIMIT=50 \
  ghcr.io/voltaire-claims/pdf-service:latest
```

### With a WSGI Server

The application exposes a standard WSGI entry point at `voltaire.pdfservice.server.app:create_app()`. For example, with gunicorn:

```bash
pip install "voltaire-pdf-service[server]" gunicorn
gunicorn "voltaire.pdfservice.server.app:create_app()" --bind 0.0.0.0:8080 --workers 4
```

### Development Server

```bash
pip install "voltaire-pdf-service[server]"
pdf-service
```

The development server starts on `http://127.0.0.1:8080` by default. Interactive API docs are available at `/docs`.

> **Warning:** The `pdf-service` command runs the Flask development server, which is not suitable for production use due to security and stability concerns. Use the Docker image or a WSGI server such as gunicorn for production deployments.

### Environment Variables

#### Application

| Variable | Default | Description |
|---|---|---|
| `HOST` | `127.0.0.1` | Listen address |
| `PORT` | `8080` | Listen port |
| `MAX_PDF_SIZE_MB` | `50` | Maximum PDF upload size in megabytes |
| `MAX_HTML_SIZE_MB` | `5` | Maximum HTML input size in megabytes |
| `MAX_PAGE_LIMIT` | `50` | Maximum pages per conversion/extraction request |
| `FLASK_DEBUG` | `0` | Set to `1` to enable Flask debug mode |

#### Docker

| Variable | Default | Description |
|---|---|---|
| `GUNICORN_WORKERS` | `4` | Number of gunicorn worker processes |
| `GUNICORN_TIMEOUT` | `120` | Worker timeout in seconds |

## Using the Client

The client is an async Python class that handles data URL encoding/decoding automatically.

```python
from pathlib import Path
from voltaire.pdfservice.client import PdfServiceClient

async def main():
    async with PdfServiceClient("http://localhost:8080") as client:
        pdf = Path("document.pdf").read_bytes()

        # Validate a PDF
        result = await client.validate(pdf)
        print(result.page_count, result.metadata)

        # Extract text
        text = await client.extract_text(pdf)
        for page in text.pages:
            print(page.text)

        # Extract text from specific pages, excluding headers/footers
        text = await client.extract_text(
            pdf, pages=[1, 2], header_pixels=50, footer_pixels=40
        )

        # Detect PDF type (text-based, image-based, or type3)
        pdf_type = await client.detect_type(pdf)
        print(pdf_type.type, pdf_type.fonts)

        # Convert pages to images
        images = await client.to_images(pdf, dpi=150, zoom=1.5, page_limit=10)
        # images.images is a list of data URLs

        # Convert PDF to HTML
        html = await client.to_html(pdf, pages=[1])
        print(html.html)

        # Convert HTML to PDF (returns raw bytes)
        pdf_bytes = await client.from_html(
            "<h1>Hello</h1>", page_width=612, page_height=792, margin=72
        )

        # Hash PDF text content
        h = await client.hash_pdf(pdf)
        print(h.hash, h.algorithm)
```

All methods raise `PdfServiceError` on API errors, which includes `status_code`, `error`, and `message` attributes.
