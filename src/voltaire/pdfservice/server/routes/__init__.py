# Copyright (C) 2026 Voltaire Claims
# SPDX-License-Identifier: AGPL-3.0-only

"""Route registration for the PDF service."""

from voltaire.pdfservice.server.routes.conversion import (
    register_from_html_route,
    register_hash_route,
    register_to_html_route,
)
from voltaire.pdfservice.server.routes.core import register_core_routes
from voltaire.pdfservice.server.routes.extraction import register_extraction_routes
from voltaire.pdfservice.server.routes.pdf import register_detect_type_route, register_pdf_routes

__all__ = [
    "register_core_routes",
    "register_detect_type_route",
    "register_extraction_routes",
    "register_from_html_route",
    "register_hash_route",
    "register_pdf_routes",
    "register_to_html_route",
]
