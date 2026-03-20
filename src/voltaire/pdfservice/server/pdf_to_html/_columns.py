"""Column detection and coordinate frequency helpers."""

import logging
from collections import Counter

from voltaire.pdfservice.server.pdf_to_html._constants import (
    COL_DISTANCE_THRESHOLD,
    COLUMN_END_PROXIMITY,
    COLUMN_GAP_OFFSET,
    COLUMN_PROXIMITY,
    LARGE_INDENT_THRESHOLD,
    MERGE_GAP_THRESHOLD,
    SMALL_COLUMN_WIDTH,
    Y_ROUNDING_FACTOR,
    Span,
)

logger = logging.getLogger(__name__)


def check_span_overlap(spans: list[Span]) -> bool:
    """Check whether spans can be merged without excessive gaps."""
    spans = sorted(spans, key=lambda s: s.get("x0", 0))
    for i in range(len(spans) - 1):
        text = spans[i].get("text") or ""
        if text.strip() == "" and len(spans) > Y_ROUNDING_FACTOR:
            continue
        x1_current = spans[i].get("x1", 0)
        x0_next = spans[i + 1].get("x0", 0)
        if abs(x0_next - x1_current) > MERGE_GAP_THRESHOLD:
            return False
    return True


def build_coordinate_frequencies(
    all_spans: list[Span],
) -> tuple[dict[int, int], dict[int, int]]:
    """Build frequency maps of x0 and x1 coordinates from spans."""
    x1_freq: dict[int, int] = {}
    x0_freq: dict[int, int] = {}

    for span in all_spans:
        if span["text"].strip() == "":
            continue
        rounded_x0 = round(span["x0"])
        rounded_x1 = round(span["x1"])
        x0_freq[rounded_x0] = x0_freq.get(rounded_x0, 0) + 1
        x1_freq[rounded_x1] = x1_freq.get(rounded_x1, 0) + 1

    return x1_freq, x0_freq


def find_most_frequent_vertical_line(
    page_vertical_lines: list[tuple[float, float]],
    page_count: int,
) -> float | None:
    """Find the most frequently occurring vertical line position."""
    freq: dict[float, int] = Counter(line[0] for line in page_vertical_lines)
    if freq and max(freq.values()) >= (page_count * 0.8):
        return max(freq.items(), key=lambda t: t[1])[0]
    return None


def resolve_column_ends(
    sorted_x1: list[tuple[int, int]],
    most_frequent_vertical_line: float | None,
) -> tuple[int, int]:
    """Determine the x1 boundaries of the two columns."""
    sorted_probable_column_ends = sorted([sorted_x1[0][0], sorted_x1[1][0]])

    if most_frequent_vertical_line:
        x1_column_one = int(most_frequent_vertical_line)
        x1_column_two = -1
        for item in sorted_x1:
            if item[0] > x1_column_one and item[0] - x1_column_one > COLUMN_END_PROXIMITY:
                x1_column_two = item[0]
                break
            if x1_column_two == -1:
                x1_column_two = sorted_probable_column_ends[1]
    else:
        x1_column_one = sorted_probable_column_ends[0]
        x1_column_two = sorted_probable_column_ends[1]

    if abs(x1_column_one - x1_column_two) < COLUMN_GAP_OFFSET:
        for column in sorted_x1[2:]:
            if abs(x1_column_one - column[0]) > COLUMN_GAP_OFFSET:
                x1_column_two = column[0]
                if x1_column_two < x1_column_one:
                    logger.debug(
                        "Rare instance of column ends being inverted was detected, "
                        "likely due to non-justified document. Swapping values.",
                    )
                    x1_column_one, x1_column_two = x1_column_two, x1_column_one
                break

    return x1_column_one, x1_column_two


def find_column_starts(
    sorted_x0: list[tuple[int, int]],
    x1_column_one: int,
    page_count: int,
) -> tuple[int, int]:
    """Find the starting x0 positions for each column."""
    column_two_start: int = 10000
    column_one_start: int = 10000
    frequency_threshold = 7 if page_count > Y_ROUNDING_FACTOR else Y_ROUNDING_FACTOR

    for coordinate, count in sorted_x0:
        if count > frequency_threshold:
            if (
                (x1_column_one < coordinate < column_two_start)
                and (abs(coordinate - column_two_start) > COLUMN_PROXIMITY)
                and (abs(coordinate - x1_column_one) > COLUMN_PROXIMITY)
            ):
                column_two_start = coordinate
            column_one_start = min(column_one_start, coordinate)

    return column_one_start, column_two_start


def adjust_column_starts(
    x0_freq: dict[int, int],
    column_one_start: int,
    column_two_start: int,
    column_ends: tuple[int, int],
    page_count: int,
) -> tuple[int, int]:
    """Adjust column start positions to balance column widths."""
    x1_column_one, x1_column_two = column_ends
    frequency_threshold = 7 if page_count > Y_ROUNDING_FACTOR else Y_ROUNDING_FACTOR
    column_one_diff = x1_column_one - column_one_start
    column_two_diff = x1_column_two - column_two_start

    if column_one_diff > column_two_diff:
        candidate = column_one_diff - column_two_diff + column_one_start
        if x0_freq.get(candidate, 0) > frequency_threshold:
            column_one_start = abs(column_one_diff - column_two_diff) + column_one_start
            logger.debug("Column 1 fixed: true")
    elif (
        column_two_diff > column_one_diff
        and x0_freq.get(column_two_diff + column_two_start, 0) > frequency_threshold
    ):
        column_two_start = abs(column_one_diff - column_two_diff) + column_two_start
        logger.debug("Column 2 fixed: true")

    return column_one_start, column_two_start


def finalize_columns(
    column_one_start: int,
    column_two_start: int,
    x1_column_one: int,
    x1_column_two: int,
    x1_freq: dict[int, int],
) -> tuple[list[tuple[int, int]], bool]:
    """Apply single-column detection and return final column coordinates."""
    column_1 = (column_one_start, x1_column_one)
    column_2 = (column_two_start, x1_column_two)
    single_column_mode = False
    column_one_diff = x1_column_one - column_one_start

    if column_one_diff < SMALL_COLUMN_WIDTH:
        logger.warning("Tiny column was detected, setting to one column mode")
        column_1 = (column_one_start, x1_column_two)
        if abs(x1_column_two - max(x1_freq.keys())) > COL_DISTANCE_THRESHOLD:
            logger.debug(
                "Column distance was not detected correctly. Applying a maximum fixed "
                "value based on document size",
            )
            max_x1 = max(x1_freq.keys())
            column_1 = (column_one_start, max_x1)
            column_2 = (max_x1 + COLUMN_GAP_OFFSET, max_x1 + LARGE_INDENT_THRESHOLD)
        else:
            column_2 = (x1_column_two + COLUMN_GAP_OFFSET, x1_column_two + COLUMN_END_PROXIMITY)
        single_column_mode = True

    column_end_diff = abs(column_1[1] - column_2[1])
    if column_end_diff < COLUMN_END_PROXIMITY and not single_column_mode:
        logger.debug(
            "Column Ends found at %d, %d, setting to one column mode",
            x1_column_one,
            x1_column_two,
        )
        single_column_mode = True
        column_1 = (column_one_start, x1_column_two)
        column_2 = (x1_column_two + COLUMN_GAP_OFFSET, x1_column_two + COLUMN_END_PROXIMITY)

    logger.debug("Columns Detected: %s, %s", column_1, column_2)
    return [column_1, column_2], single_column_mode
