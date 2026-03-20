# Copyright (C) 2026 Voltaire Claims
# SPDX-License-Identifier: AGPL-3.0-only

"""Layout detection thresholds and shared data structures."""

import dataclasses
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    import pymupdf


class Span(TypedDict):
    """A single text span extracted from a PDF page."""

    page: pymupdf.Page
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    font: str
    size: float
    flags: int
    color: int
    header_detected: bool


class HtmlLine(TypedDict):
    """A single line of HTML output with layout metadata."""

    y: int
    space_calculation: float
    content: str


class SectionHeader(TypedDict):
    """A detected section header with its y-position and constituent spans."""

    y: int
    spans: list[Span]


# Layout detection thresholds
HEADER_HEIGHT_RATIO = 0.15
HEADER_RIGHT_RATIO = 0.7
HEADER_WIDE_RATIO = 0.5
HEADER_FIRST_PAGE_RATIO = 0.6
FOOTER_HEIGHT_RATIO = 0.9
MIN_DUPE_PAGES = 5
DUPE_THRESHOLD_RATIO = 0.85
HALF_PAGE_MIN_PAGES = 8
MIN_FOOTER_TEXT_LEN = 6
MIN_SECTION_TEXT_LEN = 9
HORIZONTAL_RULE_PROXIMITY = 50
Y_ROUNDING_TOLERANCE = 0.6
Y_ROUNDING_FACTOR = 2
SPAN_GAP_THRESHOLD = 10
MERGE_GAP_THRESHOLD = 17
LARGE_INDENT_THRESHOLD = 20
SMALL_COLUMN_WIDTH = 100
COLUMN_END_PROXIMITY = 100
X1_MIN_THRESHOLD = 100
COLUMN_PROXIMITY = 2
MIN_LINE_LENGTH = 50
MAX_LINE_HEIGHT = 5
LINE_ASPECT_RATIO = 10
VERTICAL_MIN_HEIGHT = 100
VERTICAL_MAX_WIDTH = 20
DEFAULT_PAGE_RIGHT = 612
DEFAULT_COL2_START = 622
DEFAULT_COL2_END = 722
COLUMN_GAP_OFFSET = 10
BOLD_FLAG = 16
ITALIC_FLAG = 2
COL_DISTANCE_THRESHOLD = 50


@dataclasses.dataclass
class ColumnSpacingContext:
    """Shared context for column spacing calculations."""

    columns: list[tuple[int, int]]
    column_idx: int
    existing_html: list[str]
    section_header_spacing: dict[tuple[int, int], int]
    single_column_mode: bool
