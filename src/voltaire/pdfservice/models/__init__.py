"""Models package for PDF service requests and responses."""

from .requests import FromHtmlRequest
from .responses import (
    DetectTypeResponse,
    ErrorResponse,
    ExtractTextResponse,
    HashResponse,
    HealthResponse,
    ServiceError,
    ToHtmlResponse,
    ToImagesResponse,
    ValidateResponse,
)

__all__ = [
    "DetectTypeResponse",
    "ErrorResponse",
    "ExtractTextResponse",
    "FromHtmlRequest",
    "HashResponse",
    "HealthResponse",
    "ServiceError",
    "ToHtmlResponse",
    "ToImagesResponse",
    "ValidateResponse",
]
