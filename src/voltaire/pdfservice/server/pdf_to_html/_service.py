"""PDF to HTML converter with column detection and layout preservation."""

import logging
import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup

from voltaire.pdfservice.server.pdf_to_html._columns import (
    adjust_column_starts,
    build_coordinate_frequencies,
    check_span_overlap,
    finalize_columns,
    find_column_starts,
    find_most_frequent_vertical_line,
    resolve_column_ends,
)
from voltaire.pdfservice.server.pdf_to_html._constants import (
    BOLD_FLAG,
    COLUMN_END_PROXIMITY,
    COLUMN_GAP_OFFSET,
    COLUMN_PROXIMITY,
    DEFAULT_COL2_END,
    DEFAULT_COL2_START,
    DEFAULT_PAGE_RIGHT,
    DUPE_THRESHOLD_RATIO,
    FOOTER_HEIGHT_RATIO,
    HALF_PAGE_MIN_PAGES,
    HEADER_FIRST_PAGE_RATIO,
    HEADER_HEIGHT_RATIO,
    HEADER_RIGHT_RATIO,
    HEADER_WIDE_RATIO,
    HORIZONTAL_RULE_PROXIMITY,
    ITALIC_FLAG,
    LARGE_INDENT_THRESHOLD,
    LINE_ASPECT_RATIO,
    MAX_LINE_HEIGHT,
    MIN_DUPE_PAGES,
    MIN_FOOTER_TEXT_LEN,
    MIN_LINE_LENGTH,
    MIN_SECTION_TEXT_LEN,
    SPAN_GAP_THRESHOLD,
    VERTICAL_MAX_WIDTH,
    VERTICAL_MIN_HEIGHT,
    X1_MIN_THRESHOLD,
    Y_ROUNDING_FACTOR,
    Y_ROUNDING_TOLERANCE,
    ColumnSpacingContext,
    HtmlLine,
    SectionHeader,
    Span,
)

if TYPE_CHECKING:
    import pymupdf

logger = logging.getLogger(__name__)

_SECTION_HEADER_PATTERNS = [
    re.compile(r"^[a-z]\..*$"),
    re.compile(r"^\([a-z]\)$"),
    re.compile(r"^\d+\.$"),
    re.compile(r"^\(\d+\)$"),
    re.compile(r"^[ivx]+\.$"),
    re.compile(r"^\([ivx]+\)$"),
    re.compile(r"^[A-Z]\.$"),
    re.compile(r"^\([A-Z]\)$"),
    re.compile(r"^[IVX]+\.$"),
    re.compile(r"^\([IVX]+\)$"),
]

_NON_SECTION_REGEX = re.compile(
    r"""^(?!(SECTION\s+[IVXLCDM]+))\b(
        AGREEMENT|
        INSURING\s+AGREEMENT|
        DECLARATIONS|
        POLICY\s+DECLARATIONS|
        DEFINITIONS|
        DEFINITIONS\s+OF\s+INSURED|
        DEFINITIONS\s+OF\s+INSURED\s+LOCATIONS|
        COVERAGES|
        PROPERTY\s+COVERAGES|
        LIABILITY\s+COVERAGES|
        ADDITIONAL\s+COVERAGES|
        OPTIONAL\s+COVERAGES|
        PERILS\s+INSURED\s+AGAINST|
        GENERAL\s+EXCLUSIONS|
        EXCLUSIONS|
        CONDITIONS|
        LOSS\s+CONDITIONS|
        CONDITIONS\s+APPLICABLE\s+TO\s+ALL\s+COVERAGES|
        DEDUCTIBLES|
        LIMITS\s+OF\s+LIABILITY|
        LOSS\s+SETTLEMENT|
        DUTIES\s+AFTER\s+LOSS|
        DUTIES\s+IN\s+THE\s+EVENT\s+OF\s+LOSS|
        ENDORSEMENTS|
        POLICY\s+PERIOD|
        POLICY\s+TERRITORY|
        TERRITORY|
        GENERAL\s+PROVISIONS|
        SPECIAL\s+PROVISIONS|
        APPRAISAL|
        CANCELLATION|
        NON[-\s]?RENEWAL|
        TRANSFER\s+OF\s+RIGHTS|
        SUBROGATION|
        OTHER\s+INSURANCE|
        CONFORMITY\s+TO\s+STATE\s+LAW|
        INSPECTIONS?\s+AND\s+SURVEYS|
        CONDITIONS?\s+PRECEDENT|
        BASIS\s+OF\s+RECOVERY|
        LIMITATIONS
    )\b$""",
    re.IGNORECASE | re.VERBOSE,
)

_SECTION_LINE_PATTERNS = [
    re.compile(r"SECTION\s+[IVX]+\s*[-\u2013\u2014]\s*", re.IGNORECASE),
    re.compile(r"SECTION\s+[IVX]+\s*\u2013\s*", re.IGNORECASE),
    re.compile(r"SECTIONS\s+[IVX]+\s*AND\s*[IVX]+\s*[-\u2013\u2014]\s*", re.IGNORECASE),
    _NON_SECTION_REGEX,
]


class PDFToHTMLParsingError(Exception):
    """Raised when there is an error parsing the PDF to HTML."""

    def __init__(self, document_name: str = "") -> None:
        """Initialize with the document name for error context."""
        super().__init__(f"Error parsing PDF to HTML: {document_name}")


class PDFToHTMLService:
    """Advanced PDF to HTML converter with column detection and layout preservation.

    Handles column detection and layout analysis, footer and header filtering,
    indentation mapping and preservation, section header detection, and
    multi-column content processing.
    """

    # ------------ public API ----------------------
    def convert_pdf_to_html(
        self,
        pdf: pymupdf.Document,
        pages: list[int] | None = None,
        name: str | None = None,
    ) -> str:
        """Convert PDF to HTML with the given pages."""
        if pages is None:
            pages = list(range(1, pdf.page_count + 1))

        section_header_spacing: dict[tuple[int, int], int] = {}

        try:
            all_spans = self._extract_all_spans(pdf, pages)
            columns, single_column_mode = self._detect_columns(all_spans, pages, pdf)
            html_output: str = self._generate_html(
                pdf,
                pages,
                columns,
                section_header_spacing,
                single_column_mode=single_column_mode,
            )
        except Exception as e:
            logger.exception("PDF to HTML conversion failed")
            raise PDFToHTMLParsingError(name or "") from e
        else:
            return self._remove_dupe_items(html_output, pdf, name, all_spans)

    # ------------ methods for tracking section header spacing -----------------------
    @staticmethod
    def _is_section_header(text: str) -> bool:
        """Detect if text is a legal section header/subitem."""
        text = text.strip()
        return any(pattern.match(text) for pattern in _SECTION_HEADER_PATTERNS)

    @staticmethod
    def _get_x_position_group(x_pos: float, tolerance: int = 2) -> int:
        """Group x positions into ranges for consistent spacing tracking."""
        return int(x_pos // tolerance * tolerance)

    def _get_or_set_section_header_spacing(
        self,
        span: Span,
        column_idx: int,
        column: tuple[int, int],
        section_header_spacing: dict[tuple[int, int], int],
        *,
        single_column_mode: bool,
    ) -> tuple[int, float]:
        """Get cached spacing for section headers, or calculate and cache it."""
        x_pos: int = round(span.get("x0", 0))
        x_group: int = self._get_x_position_group(x_pos)
        cache_key = (column_idx, x_group)

        if cache_key in section_header_spacing:
            cached_spaces = section_header_spacing[cache_key]
            return cached_spaces, cached_spaces

        _spaces, unrounded_spaces = self._calculate_spaces(span, column)
        spaces = round(unrounded_spaces)

        if spaces >= LARGE_INDENT_THRESHOLD and not single_column_mode:
            spaces = spaces // 2

        section_header_spacing[cache_key] = spaces

        return spaces, unrounded_spaces

    # ------------ internals -----------------------
    def _remove_dupe_items(
        self,
        html_content: str,
        pdf: pymupdf.Document,
        name: str | None = None,
        all_spans: list[Span] | None = None,
    ) -> str:
        """Remove duplicated headers and footers from the HTML output."""
        dupe_lines: dict[str, int] = {}
        for line in html_content.split("\n"):
            if line not in dupe_lines:
                dupe_lines[line] = 1
            else:
                dupe_lines[line] += 1

        lines_to_remove = sorted(
            [
                line[0]
                for line in dupe_lines.items()
                if line[1] >= pdf.page_count * DUPE_THRESHOLD_RATIO
                and pdf.page_count >= MIN_DUPE_PAGES
            ],
            key=lambda t: -dupe_lines[t],
        )

        potential_repeated_header_footers = self._find_repeated_header_footers(
            dupe_lines,
            pdf.page_count,
        )

        if all_spans:
            self._detect_repeated_headers(
                all_spans,
                potential_repeated_header_footers,
                lines_to_remove,
            )

        targeted_footer_lines: dict[str, int] = {}
        if all_spans:
            self._detect_repeated_footers(
                all_spans,
                potential_repeated_header_footers,
                lines_to_remove,
                targeted_footer_lines,
            )

        if not potential_repeated_header_footers:
            self._detect_varying_footers(
                targeted_footer_lines,
                pdf.page_count,
                html_content,
                lines_to_remove,
            )

        self._detect_page_number_footers(html_content, lines_to_remove)

        if pdf.page_count < MIN_DUPE_PAGES and name is not None:
            self._detect_doc_name_lines(
                name,
                html_content,
                lines_to_remove,
            )

        logger.debug("REMOVING THESE ITEMS: %s", lines_to_remove)
        removal_set = set(lines_to_remove)
        html_output: str = ""
        for line in html_content.split("\n"):
            html_output += line + "\n" if line not in removal_set else ""
        return html_output

    @staticmethod
    def _find_repeated_header_footers(
        dupe_lines: dict[str, int],
        page_count: int,
    ) -> list[tuple[str, str]]:
        """Find lines that repeat on every page (likely headers/footers)."""
        result: list[tuple[str, str]] = []
        for line_text, count in dupe_lines.items():
            if count == page_count:
                soup = BeautifulSoup(line_text, "html.parser")
                bs_span = soup.find("span")
                if bs_span and bs_span.text:
                    result.append((line_text, bs_span.text))
            if page_count >= HALF_PAGE_MIN_PAGES and (
                count == page_count // 2 or count == page_count // 2 + 1
            ):
                soup = BeautifulSoup(line_text, "html.parser")
                bs_span = soup.find("span")
                if bs_span and bs_span.text:
                    result.append((line_text, bs_span.text))
        return result

    @staticmethod
    def _detect_repeated_headers(
        all_spans: list[Span],
        potential: list[tuple[str, str]],
        lines_to_remove: list[str],
    ) -> None:
        """Mark repeated header lines for removal."""
        for span in all_spans:
            if span.get("header_detected", False):
                span_text = span.get("text", "")
                for item in potential:
                    if item[1] == span_text and item[0] not in lines_to_remove:
                        lines_to_remove.append(item[0])

    def _detect_repeated_footers(
        self,
        all_spans: list[Span],
        potential: list[tuple[str, str]],
        lines_to_remove: list[str],
        targeted_footer_lines: dict[str, int],
    ) -> None:
        """Mark repeated footer lines for removal."""
        for span in all_spans:
            if self._is_footer_block(span):
                if not potential:
                    text = span.get("text", "")
                    targeted_footer_lines[text] = targeted_footer_lines.get(text, 0) + 1
                for item in potential:
                    if item[1] == span.get("text", "") and item[0] not in lines_to_remove:
                        lines_to_remove.append(item[0])

    @staticmethod
    def _detect_varying_footers(
        targeted_footer_lines: dict[str, int],
        page_count: int,
        html_content: str,
        lines_to_remove: list[str],
    ) -> None:
        """Detect footers that differ slightly per page."""
        for text, count in targeted_footer_lines.items():
            if len(text) > MIN_FOOTER_TEXT_LEN and (
                count == page_count // 2 or count == page_count // 2 + 1
            ):
                for line in html_content.split("\n"):
                    regex = rf".*>\s*{re.escape(text)}\s*</span>.*"
                    if re.match(regex, line):
                        lines_to_remove.append(line)

    @staticmethod
    def _detect_page_number_footers(
        html_content: str,
        lines_to_remove: list[str],
    ) -> None:
        """Remove footer lines containing page number patterns."""
        page_of_regex = re.compile(r"\bPage\s*\d{1,4}\s*of\s*\d{1,4}\b", re.IGNORECASE)
        for line in html_content.split("\n"):
            try:
                text_line = BeautifulSoup(line, "html.parser").get_text(" ", strip=True)
            except TypeError:
                text_line = line
            if page_of_regex.search(text_line):
                lines_to_remove.append(line)

    @staticmethod
    def _detect_doc_name_lines(
        name: str,
        html_content: str,
        lines_to_remove: list[str],
    ) -> None:
        """Remove lines that match the document name."""
        if not name:
            return

        for line in lines_to_remove:
            soup = BeautifulSoup(line, "html.parser")
            soup_span = soup.find("span")
            if soup_span and soup_span.text and soup_span.text.strip() in name:
                name = soup_span.text or ""
                break

        if not name:
            return

        lines_to_remove.extend(
            line
            for line in html_content.split("\n")
            if re.match(r".*>(" + re.escape(name) + r")<.*", line)
            and line.count("span") == Y_ROUNDING_FACTOR
        )

    def _generate_html(
        self,
        pdf: pymupdf.Document,
        pages: list[int],
        columns: list[tuple[int, int]],
        section_header_spacing: dict[tuple[int, int], int],
        *,
        single_column_mode: bool,
    ) -> str:
        """Generate HTML with section-aware column-stacking approach."""
        styles = "<style>span {font-family: 'Courier New', monospace;}</style>"

        html = [f"<html><head><meta charset='utf-8'></head>{styles}<body><pre>\n"]
        for page_num in pages:
            page: pymupdf.Page = pdf[page_num - 1]
            page_spans = self._extract_spans_for_page(page)
            document_content = self._process_page_content(
                pdf,
                page_spans,
                columns,
                section_header_spacing,
                single_column_mode=single_column_mode,
            )
            html.append(document_content)

        html.append("</pre></body></html>\n")

        html_string = "".join(html)
        return self._remove_blank_lines(html_string)

    @staticmethod
    def _remove_blank_lines(html_content: str) -> str:
        """Collapse blank lines and remove empty spans."""
        modified_html = re.sub(r"\n\s*\n", "\n", html_content)
        modified_html = re.sub(r"<span[^>]*> </span>", "", modified_html)
        modified_html = re.sub(r"^\s+$", "", modified_html, flags=re.MULTILINE)
        return re.sub(r"\n{2,}", "\n", modified_html)

    @staticmethod
    def _calculate_spaces(
        span: Span,
        column: tuple[int, int],
    ) -> tuple[int, float]:
        """Calculate the number of leading spaces for a span relative to a column."""
        size = span.get("size", 0) or 1
        unrounded_spaces = (span.get("x0", 0) - column[0]) / (size * 0.5) - 0.05
        spaces = round(unrounded_spaces)
        return spaces, unrounded_spaces

    def _process_page_content(
        self,
        pdf: pymupdf.Document,
        page_spans: list[Span],
        columns: list[tuple[int, int]],
        section_header_spacing: dict[tuple[int, int], int],
        *,
        single_column_mode: bool,
    ) -> str:
        """Process a single page and return its HTML content."""
        lines = defaultdict(list)
        rounded_groups_to_check: list[int] = []
        for span in page_spans:
            y_pos = round(span["y0"] / Y_ROUNDING_FACTOR) * Y_ROUNDING_FACTOR
            if (
                abs(y_pos - span["y0"]) > Y_ROUNDING_TOLERANCE
                and y_pos not in rounded_groups_to_check
            ):
                rounded_groups_to_check.append(y_pos)
            lines[y_pos].append(span)

        rounded_groups_to_check.sort()
        sorted_rounded_groups = [
            (a, b)
            for i, a in enumerate(rounded_groups_to_check)
            for b in rounded_groups_to_check[i + 1 :]
            if abs(a - b) == Y_ROUNDING_FACTOR
        ]
        lines = self._merge_rounded_groups(lines, sorted_rounded_groups, columns)

        sorted_lines = sorted(lines.items())
        html: list[HtmlLine] = []
        right_html: list[HtmlLine] = []

        for y_coordinate, spans in sorted_lines:
            left_html, right_col_html, space_calc = self._process_line_spans(
                spans,
                y_coordinate,
                columns,
                section_header_spacing,
                single_column_mode=single_column_mode,
            )

            if left_html:
                html.append(
                    {
                        "y": y_coordinate,
                        "space_calculation": space_calc,
                        "content": "".join(left_html) + "\n",
                    },
                )
            if right_col_html:
                right_html.append(
                    {
                        "y": y_coordinate,
                        "space_calculation": space_calc,
                        "content": "".join(right_col_html) + "\n",
                    },
                )

        section_headers = self._detect_section_headers(
            page_spans,
            self._get_page_num_from_spans(page_spans),
            columns,
            pdf,
        )
        return "".join(self._combine_html(html, right_html, section_headers))

    def _process_line_spans(
        self,
        spans: list[Span],
        _y_coordinate: int,
        columns: list[tuple[int, int]],
        section_header_spacing: dict[tuple[int, int], int],
        *,
        single_column_mode: bool,
    ) -> tuple[list[str], list[str], float]:
        """Process all spans on a single line and return left/right column HTML."""
        span_left_column_html: list[str] = []
        span_right_column_html: list[str] = []
        text_spans_columns = False
        main_span_space_calculation: float = 0.0
        spans = sorted(spans, key=lambda s: s["x0"])

        for index, span in enumerate(spans):
            if not (span.get("text") or "").strip():
                continue

            if span.get("x0") <= columns[0][1] and span.get("x1") >= columns[1][0]:
                text_spans_columns = True

            if span.get("x0") <= columns[0][1]:
                ctx = ColumnSpacingContext(
                    columns=columns,
                    column_idx=0,
                    existing_html=span_left_column_html,
                    section_header_spacing=section_header_spacing,
                    single_column_mode=single_column_mode,
                )
                spaces, main_span_space_calculation = self._compute_column_spaces(
                    span,
                    index,
                    spans,
                    ctx,
                )
                span_left_column_html.append(" " * spaces + self._format_span(span))
            else:
                ctx = ColumnSpacingContext(
                    columns=columns,
                    column_idx=1,
                    existing_html=span_right_column_html,
                    section_header_spacing=section_header_spacing,
                    single_column_mode=single_column_mode,
                )
                spaces, main_span_space_calculation = self._compute_column_spaces(
                    span,
                    index,
                    spans,
                    ctx,
                )
                if text_spans_columns or span.get("header_detected", False):
                    span_left_column_html.append(self._format_span(span))
                else:
                    span_right_column_html.append(" " * spaces + self._format_span(span))

        return span_left_column_html, span_right_column_html, main_span_space_calculation

    def _compute_column_spaces(
        self,
        span: Span,
        index: int,
        spans: list[Span],
        ctx: ColumnSpacingContext,
    ) -> tuple[int, float]:
        """Compute spacing for a span in the given column."""
        column = ctx.columns[ctx.column_idx]

        if not ctx.existing_html:
            if self._is_section_header(span.get("text", "").strip()):
                spaces, unrounded = self._get_or_set_section_header_spacing(
                    span,
                    ctx.column_idx,
                    column,
                    ctx.section_header_spacing,
                    single_column_mode=ctx.single_column_mode,
                )
            else:
                spaces, unrounded = self._calculate_spaces(span, column)
                if (
                    ctx.column_idx == 0
                    and spaces >= LARGE_INDENT_THRESHOLD
                    and not ctx.single_column_mode
                ):
                    spaces = spaces // 2
            return spaces, unrounded

        if ctx.column_idx == 0:
            return self._inter_span_spacing(span, index, spans, column), 0.0

        prev = spans[index - 1]
        prev_text = prev.get("text") or ""
        span_text = span.get("text") or ""
        if prev_text and span_text and prev_text[-1] != " " and span_text[0] != " ":
            if span.get("x0") - prev.get("x1") > SPAN_GAP_THRESHOLD:
                spaces, _unrounded = self._calculate_spaces(span, column)
                prior_spaces, _ = self._calculate_spaces(prev, column)
                spaces = max(1, spaces - prior_spaces - len(prev_text))
            else:
                spaces = 1
        else:
            spaces = 0

        if spaces >= LARGE_INDENT_THRESHOLD:
            spaces = spaces // 2
        return spaces, 0.0

    def _inter_span_spacing(
        self,
        span: Span,
        index: int,
        spans: list[Span],
        column: tuple[int, int],
    ) -> int:
        """Calculate spacing between consecutive spans on the same line."""
        prev = spans[index - 1]
        prev_text = prev.get("text") or ""
        span_text = span.get("text") or ""
        if not prev_text or not span_text:
            return 0
        if (prev_text[-1] != " " or prev_text == " ") and span_text[0] != " ":
            if span.get("x0") - prev.get("x1") > SPAN_GAP_THRESHOLD:
                spaces, _unrounded = self._calculate_spaces(span, column)
                prior_spaces, _ = self._calculate_spaces(prev, column)
                return max(1, spaces - prior_spaces - len(prev_text))
            return 1
        return 0

    @staticmethod
    def _merge_rounded_groups(
        lines: defaultdict[int, list[Span]],
        rounded_groups: list[tuple[int, int]],
        columns: list[tuple[int, int]],
    ) -> defaultdict[int, list[Span]]:
        """Merge y-position groups that were split by rounding."""
        for y_pos_1, y_pos_2 in rounded_groups:
            if y_pos_1 not in lines or y_pos_2 not in lines:
                continue

            spans_1 = lines[y_pos_1]
            spans_2 = lines[y_pos_2]

            left_spans: list[Span] = []
            right_spans: list[Span] = []

            for span in [*spans_1, *spans_2]:
                if span.get("x0", 0) <= columns[0][1]:
                    left_spans.append(span)
                else:
                    right_spans.append(span)

            can_merge_left = len(left_spans) > 1 and check_span_overlap(left_spans)
            can_merge_right = len(right_spans) > 1 and check_span_overlap(right_spans)

            if can_merge_left or can_merge_right:
                new_y_pos = (
                    y_pos_2
                    if y_pos_2 in [group[0] for group in rounded_groups]
                    else (y_pos_1 + y_pos_2) // 2
                )
                merged_spans = left_spans + right_spans
                merged_spans.sort(key=lambda s: s.get("x0", 0))
                del lines[y_pos_1]
                del lines[y_pos_2]
                lines[new_y_pos] = merged_spans
        return lines

    @staticmethod
    def _combine_html(
        left_col_html: list[HtmlLine],
        right_col_html: list[HtmlLine],
        section_headers: list[SectionHeader] | None = None,
    ) -> list[str]:
        """Combine left and right column HTML, respecting section boundaries."""
        if not section_headers:
            return [item["content"] for item in [*left_col_html, *right_col_html]]

        combined: list[str] = []

        section_y_positions: list[float] = [header["y"] for header in section_headers]
        section_y_positions.append(float("inf"))

        prev_y = 0
        for section_y in section_y_positions:
            left_section_content = [
                item["content"] for item in left_col_html if prev_y <= item["y"] < section_y
            ]
            right_section_content = [
                item["content"] for item in right_col_html if prev_y <= item["y"] < section_y
            ]

            combined.extend(left_section_content)
            combined.extend(right_section_content)

            prev_y = section_y

        return combined

    @staticmethod
    def _get_page_num_from_spans(spans: list[Span]) -> int:
        """Get the page number from the first span."""
        if not spans:
            return 1
        first_span = spans[0]
        if hasattr(first_span["page"], "number"):
            return first_span["page"].number + 1
        return 1

    def _detect_columns(
        self,
        all_spans: list[Span],
        pages: list[int],
        pdf: pymupdf.Document,
    ) -> tuple[list[tuple[int, int]], bool]:
        """Detect column structure in the PDF pages based on spans and vertical lines."""
        page_vertical_lines = self._extract_vertical_lines(pdf)
        return self._find_columns(all_spans, pages, page_vertical_lines)

    @staticmethod
    def _format_span(span: Span) -> str:
        """Format a single span as HTML with styling."""
        pdf_font = span["font"]
        style = f"font-size:10pt; color:#{span['color']:06x};"

        if "Bold" in pdf_font or span.get("flags", 0) & BOLD_FLAG:
            style += " font-weight:bold;"

        if "Italic" in pdf_font or span.get("flags", 0) & ITALIC_FLAG:
            style += " font-style:italic;"

        safe_text = span["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return f'<span style="{style}">{safe_text}</span>'

    @staticmethod
    def _is_floating_header_block(block: dict[str, Any], page: pymupdf.Page) -> bool:
        """Detect if a text block is likely a floating header based on its position."""
        page_height = page.rect.height
        page_width = page.rect.width

        x0, _y0, x1, y1 = block["bbox"]

        if y1 < page_height * HEADER_HEIGHT_RATIO and (
            x0 > page_width * HEADER_RIGHT_RATIO or abs(x0 - x1) > page_width * HEADER_WIDE_RATIO
        ):
            return True

        return bool(
            y1 < page_height * HEADER_HEIGHT_RATIO
            and x0 > page_width * HEADER_FIRST_PAGE_RATIO
            and page.number == 0,
        )

    @staticmethod
    def _is_footer_block(block: Span) -> bool:
        """Detect if a text block is likely a footer."""
        page = block.get("page")
        if not page:
            return False

        page_height = page.rect.height
        y1 = block["y1"]

        return y1 > page_height * FOOTER_HEIGHT_RATIO

    def _extract_all_spans(
        self,
        pdf: pymupdf.Document,
        pages: list[int],
    ) -> list[Span]:
        """Return raw spans for the requested pages."""
        spans: list[Span] = []
        for page_num in pages:
            page = pdf[page_num - 1]
            spans.extend(self._extract_spans_for_page(page))
        return spans

    def _extract_spans_for_page(self, page: pymupdf.Page) -> list[Span]:
        """Extract all text spans from a single page."""
        spans: list[Span] = []
        blocks: list[dict[str, Any]] = page.get_text("dict")["blocks"]  # type: ignore[assignment]
        for block in blocks:
            if block["type"] != 0:
                continue

            header_detected = self._is_floating_header_block(block, page)

            for line in block["lines"]:
                spans.extend(
                    Span(
                        page=page,
                        x0=span["bbox"][0],
                        y0=span["bbox"][1],
                        x1=span["bbox"][2],
                        y1=span["bbox"][3],
                        text=span["text"],
                        font=span["font"],
                        size=span["size"],
                        flags=span.get("flags", 0),
                        color=span["color"],
                        header_detected=header_detected,
                    )
                    for span in line["spans"]
                )
        return spans

    @staticmethod
    def _find_columns(
        all_spans: list[Span],
        pages: list[int],
        page_vertical_lines: list[tuple[float, float]],
    ) -> tuple[list[tuple[int, int]], bool]:
        """Detect column boundaries from span positions and vertical lines."""
        x1_freq, x0_freq = build_coordinate_frequencies(all_spans)

        sorted_x0 = sorted(x0_freq.items(), key=lambda t: -t[1])
        sorted_x1 = sorted(x1_freq.items(), key=lambda t: -t[1])

        if not sorted_x0 or not sorted_x1:
            return [
                (0, DEFAULT_PAGE_RIGHT),
                (DEFAULT_COL2_START, DEFAULT_COL2_END),
            ], True

        if sorted_x1[0][0] < X1_MIN_THRESHOLD:
            logger.debug("sorted x1 for column one was less than 100, trying to pop")
            sorted_x1.pop(0)

        if len(sorted_x1) < Y_ROUNDING_FACTOR:
            col_end = sorted_x1[0][0] if sorted_x1 else DEFAULT_PAGE_RIGHT
            col_start = sorted_x0[0][0] if sorted_x0 else 0
            return [
                (col_start, col_end),
                (col_end + COLUMN_GAP_OFFSET, col_end + COLUMN_END_PROXIMITY),
            ], True

        most_frequent_vline = find_most_frequent_vertical_line(
            page_vertical_lines,
            len(pages),
        )

        x1_column_one, x1_column_two = resolve_column_ends(
            sorted_x1,
            most_frequent_vline,
        )

        logger.debug("Column Ends found at %d, %d", x1_column_one, x1_column_two)

        column_one_start, column_two_start = find_column_starts(
            sorted_x0,
            x1_column_one,
            len(pages),
        )

        column_one_start, column_two_start = adjust_column_starts(
            x0_freq,
            column_one_start,
            column_two_start,
            (x1_column_one, x1_column_two),
            len(pages),
        )

        return finalize_columns(
            column_one_start,
            column_two_start,
            x1_column_one,
            x1_column_two,
            x1_freq,
        )

    @staticmethod
    def _extract_vertical_lines(pdf: pymupdf.Document) -> list[tuple[float, float]]:
        """Extract vertical line positions from PDF drawings."""
        vertical_lines: list[tuple[float, float]] = []
        for page in pdf.pages():
            try:
                drawings = page.get_drawings()
            except ValueError, RuntimeError:
                return []

            for drawing in drawings:
                for line in drawing["items"]:
                    if line[0] == "re":
                        rect = line[1]
                        width = rect.x1 - rect.x0
                        height = rect.y1 - rect.y0
                        if height > VERTICAL_MIN_HEIGHT and width < VERTICAL_MAX_WIDTH:
                            vertical_lines.append((rect.x0, rect.x1))
                    elif line[0] == "l":
                        rect = drawing.get("rect")
                        if rect:
                            width = rect.x1 - rect.x0
                            height = rect.y1 - rect.y0
                            if height > VERTICAL_MIN_HEIGHT and width < VERTICAL_MAX_WIDTH:
                                vertical_lines.append((rect.x0, rect.x1))

        return vertical_lines

    @staticmethod
    def _extract_horizontal_lines(
        pdf: pymupdf.Document,
        page_num: int,
    ) -> list[dict[str, float]]:
        """Extract horizontal line positions from a PDF page."""
        page = pdf[page_num - 1]

        try:
            drawings = page.get_drawings()
        except ValueError, RuntimeError:
            return []

        horizontal_lines: list[dict[str, float]] = []

        for drawing in drawings:
            for item in drawing["items"]:
                if item[0] == "l":
                    from_point = item[1]
                    to_point = item[2]

                    if abs(from_point.y - to_point.y) <= COLUMN_PROXIMITY:
                        line_length = abs(to_point.x - from_point.x)
                        if line_length > MIN_LINE_LENGTH:
                            horizontal_lines.append(
                                {
                                    "x0": min(from_point.x, to_point.x),
                                    "x1": max(from_point.x, to_point.x),
                                    "y": from_point.y,
                                    "length": line_length,
                                },
                            )

                elif item[0] == "re":
                    rect = item[1]
                    width = rect.x1 - rect.x0
                    height = rect.y1 - rect.y0

                    if (
                        height > 0
                        and width > MIN_LINE_LENGTH
                        and height <= MAX_LINE_HEIGHT
                        and (width / height) > LINE_ASPECT_RATIO
                    ):
                        horizontal_lines.append(
                            {
                                "x0": rect.x0,
                                "x1": rect.x1,
                                "y": (rect.y0 + rect.y1) / 2,
                                "length": width,
                            },
                        )

        return horizontal_lines

    def _detect_section_headers(
        self,
        page_spans: list[Span],
        page_num: int,
        columns: list[tuple[int, int]],
        pdf: pymupdf.Document,
    ) -> list[SectionHeader]:
        """Detect section headers bounded by horizontal rules."""
        horizontal_lines = self._extract_horizontal_lines(pdf, page_num)

        lines: dict[int, list[Span]] = defaultdict(list)
        for span in page_spans:
            y_pos = round(span["y0"] / Y_ROUNDING_FACTOR) * Y_ROUNDING_FACTOR
            lines[y_pos].append(span)

        section_headers: list[SectionHeader] = []

        for y_coord, line_spans in lines.items():
            if self._is_line_between_horizontal_rules(
                y_coord,
                horizontal_lines,
            ) and self._is_section_header_line(line_spans, columns):
                section_headers.append({"y": y_coord, "spans": line_spans})

        return sorted(section_headers, key=lambda h: h["y"])

    @staticmethod
    def _is_line_between_horizontal_rules(
        y_coord: int,
        horizontal_lines: list[dict[str, float]],
    ) -> bool:
        """Check if a y-coordinate falls between two horizontal rules."""
        if not horizontal_lines:
            return False

        lines_above = [line for line in horizontal_lines if line["y"] < y_coord]
        lines_below = [line for line in horizontal_lines if line["y"] > y_coord]

        if not lines_above or not lines_below:
            return False

        closest_above = max(lines_above, key=lambda la: la["y"])
        closest_below = min(lines_below, key=lambda lb: lb["y"])

        distance_above = y_coord - closest_above["y"]
        distance_below = closest_below["y"] - y_coord

        return (
            distance_above <= HORIZONTAL_RULE_PROXIMITY
            and distance_below <= HORIZONTAL_RULE_PROXIMITY
        )

    @staticmethod
    def _is_section_header_line(
        line_spans: list[Span],
        columns: list[tuple[int, int]],
    ) -> bool:
        """Check if a line of spans represents a section header."""
        if not line_spans:
            return False

        leftmost_x = min(s["x0"] for s in line_spans)
        rightmost_x = max(s["x1"] for s in line_spans)

        column_gap_start = columns[0][1]
        column_gap_end = columns[1][0]

        spans_column_gap = leftmost_x < column_gap_end and rightmost_x > column_gap_start

        combined_text = " ".join(s["text"].strip() for s in line_spans).strip()
        has_section_pattern = any(
            pattern.match(combined_text) for pattern in _SECTION_LINE_PATTERNS
        )

        return (
            spans_column_gap and has_section_pattern and len(combined_text) >= MIN_SECTION_TEXT_LEN
        )
