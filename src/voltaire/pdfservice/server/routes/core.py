"""Core routes: root redirect and health check."""

from typing import TYPE_CHECKING

from flask import redirect

from voltaire.pdfservice import __version__
from voltaire.pdfservice.models.responses import HealthResponse

if TYPE_CHECKING:
    from apiflask import APIFlask
    from werkzeug.wrappers import Response


def register_core_routes(app: APIFlask) -> None:
    """Register root and health routes."""

    @app.route("/")
    @app.doc(hide=True)
    def root() -> Response:
        """Redirect to the OpenAPI documentation."""
        return redirect("/docs")

    @app.get("/health")
    @app.output(HealthResponse)
    def health() -> HealthResponse:
        """Return service health status and version."""
        return HealthResponse(status="healthy", version=__version__)
