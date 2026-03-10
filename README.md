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
