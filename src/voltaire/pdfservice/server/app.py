# Copyright (C) 2026 Voltaire Claims
# SPDX-License-Identifier: AGPL-3.0-only

"""Flask application for the Voltaire PDF microservice."""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

from apiflask import APIFlask
from pydantic import BaseModel

if TYPE_CHECKING:
    import flask.typing as ft
    from flask import Response

from voltaire.pdfservice import __version__
from voltaire.pdfservice.models.responses import ErrorResponse, FieldError, ServiceError
from voltaire.pdfservice.server.routes import (
    register_core_routes,
    register_detect_type_route,
    register_extraction_routes,
    register_from_html_route,
    register_hash_route,
    register_pdf_routes,
    register_to_html_route,
)


class PydanticAPIFlask(APIFlask):
    """APIFlask subclass that serialises Pydantic model return values."""

    def make_response(self, rv: ft.ResponseReturnValue) -> Response:
        """Convert BaseModel instances to dicts before standard processing."""
        if isinstance(rv, BaseModel):
            rv = rv.model_dump(exclude_none=True)
        elif isinstance(rv, tuple) and rv and isinstance(rv[0], BaseModel):
            rv = (rv[0].model_dump(exclude_none=True), *rv[1:])  # type: ignore[assignment]
        return super().make_response(rv)


def create_app() -> PydanticAPIFlask:
    """Create and configure the Flask application."""
    app = PydanticAPIFlask(
        __name__,
        title="Voltaire PDF Service",
        version=__version__,
    )
    max_pdf_size = int(os.environ.get("MAX_PDF_SIZE_MB", "50")) * 1024 * 1024
    max_html_size = int(os.environ.get("MAX_HTML_SIZE_MB", "5")) * 1024 * 1024
    max_page_limit = int(os.environ.get("MAX_PAGE_LIMIT", "50"))
    app.config["MAX_CONTENT_LENGTH"] = max(max_pdf_size, max_html_size)
    _error_schema = ErrorResponse.model_json_schema(ref_template="#/components/schemas/{model}")
    _error_defs = _error_schema.pop("$defs", {})
    app.config["VALIDATION_ERROR_SCHEMA"] = _error_schema

    @app.spec_processor
    def _inject_error_defs(spec):  # noqa: ANN001, ANN202
        schemas = spec.setdefault("components", {}).setdefault("schemas", {})
        schemas.setdefault("ErrorResponse", _error_schema)
        for name, defn in _error_defs.items():
            schemas.setdefault(name, defn)
        return spec

    @app.error_processor
    def handle_http_error(error):  # noqa: ANN001, ANN202
        ref_id = str(uuid.uuid4())
        detail = getattr(error, "detail", None)
        fields: list[FieldError] | None = None
        if detail:
            fields = [
                FieldError(name=field, errors=msgs)
                for loc in detail.values()
                for field, msgs in loc.items()
            ]
        app.logger.error(
            "error_ref=%s status=%s message=%s", ref_id, error.status_code, error.message
        )
        return (
            ErrorResponse(
                message=error.message,
                reference_id=ref_id,
                fields=fields,
            ).model_dump(exclude_none=True),
            error.status_code,
            error.headers,
        )

    @app.errorhandler(ServiceError)
    def handle_service_error(exc: ServiceError):  # noqa: ANN202
        ref_id = str(uuid.uuid4())
        app.logger.exception("error_ref=%s", ref_id, exc_info=exc)
        return exc.response(ref_id)

    register_core_routes(app)
    register_pdf_routes(app, max_page_limit)
    register_detect_type_route(app)
    register_extraction_routes(app)
    register_from_html_route(app)
    register_to_html_route(app)
    register_hash_route(app)

    return app


def run() -> None:
    """Start the Flask development server."""
    app = create_app()
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, debug=os.environ.get("FLASK_DEBUG", "0") == "1", port=port)
