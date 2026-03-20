# ruff: noqa: A001, A002 — must match pymupdf's public API names

from collections.abc import Iterator, Sequence
from io import BytesIO
from typing import Any, Literal, Self, overload

class FileDataError(Exception): ...

class Rect:
    x0: float
    y0: float
    x1: float
    y1: float
    width: float
    height: float
    def __init__(self, x0: float, y0: float, x1: float, y1: float) -> None: ...

class Matrix:
    def __init__(self, zoom_x: float, zoom_y: float) -> None: ...

class Pixmap:
    def tobytes(self, output: str = "png") -> bytes: ...
    def pil_tobytes(self, format: str = "png") -> bytes: ...

class Colorspace: ...
class TextPage: ...

class Page:
    rect: Rect
    number: int
    @overload
    def get_text(
        self,
        option: Literal["text"] = "text",
        *,
        clip: Rect | None = None,
        flags: int | None = None,
        textpage: TextPage | None = None,
        sort: bool = False,
        delimiters: str | None = None,
        tolerance: int = 3,
    ) -> str: ...
    @overload
    def get_text(
        self,
        option: Literal["dict", "json", "rawdict", "rawjson", "html", "xhtml", "xml"],
        *,
        clip: Rect | None = None,
        flags: int | None = None,
        textpage: TextPage | None = None,
        sort: bool = False,
        delimiters: str | None = None,
        tolerance: int = 3,
    ) -> dict[str, object]: ...
    @overload
    def get_text(
        self,
        option: str = "text",
        *,
        clip: Rect | None = None,
        flags: int | None = None,
        textpage: TextPage | None = None,
        sort: bool = False,
        delimiters: str | None = None,
        tolerance: int = 3,
    ) -> str | dict[str, object]: ...
    def get_pixmap(
        self,
        *,
        matrix: Matrix | None = None,
        dpi: int | None = None,
        colorspace: Colorspace | None = None,
        clip: Rect | None = None,
        alpha: bool = False,
        annots: bool = True,
    ) -> Pixmap: ...
    def get_fonts(self, full: bool = False) -> list[tuple[int, str, str, str, str, str]]: ...
    def get_drawings(self, extended: bool = False) -> list[dict[str, Any]]: ...
    def insert_text(
        self,
        point: tuple[float, float],
        text: str | list[str],
        *,
        fontsize: float = 11,
        fontname: str = "helv",
        fontfile: str | None = None,
        color: Sequence[float] | None = None,
        fill: Sequence[float] | None = None,
        rotate: int = 0,
        overlay: bool = True,
    ) -> int: ...
    def insert_htmlbox(
        self,
        rect: Rect,
        text: str,
        *,
        css: str | None = None,
        archive: object = None,
        rotate: int = 0,
    ) -> float: ...

class Document:
    page_count: int
    metadata: dict[str, str] | None
    def __enter__(self) -> Self: ...
    def __exit__(self, *args: object) -> None: ...
    def __iter__(self) -> Iterator[Page]: ...
    def __getitem__(self, index: int) -> Page: ...
    def new_page(
        self,
        pno: int = -1,
        width: float = 595,
        height: float = 842,
    ) -> Page: ...
    def pages(
        self,
        start: int | None = None,
        stop: int | None = None,
        step: int | None = None,
    ) -> Iterator[Page]: ...
    def tobytes(
        self,
        garbage: bool = False,
        clean: bool = False,
        deflate: bool = False,
    ) -> bytes: ...
    def close(self) -> None: ...

def open(
    filename: str | None = None,
    *,
    stream: bytes | BytesIO | None = None,
    filetype: str | None = None,
) -> Document: ...
