"""PDF generation utilities for stockmgr table exports."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from fpdf import FPDF

# Approximate mm per character at 9pt Helvetica
_CHAR_W = 2.0
_ROW_H = 6.0
_HEADER_H = 7.0
_TITLE_H = 8.0
_FILTER_H = 5.0
_FOOTER_MARGIN = 12.0


class _TablePDF(FPDF):
    """FPDF subclass that renders title, filter summary, and column headers on every page."""

    def __init__(
        self,
        doc_title: str,
        filters_text: str,
        col_headers: list[str],
        col_widths: list[float],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._doc_title = doc_title
        self._filters_text = filters_text
        self._col_headers = col_headers
        self._col_widths = col_widths

    def header(self) -> None:
        # Title — shown on every page so multi-page PDFs are self-contained
        self.set_font("Helvetica", "B", 12)
        self.cell(0, _TITLE_H, self._doc_title, new_x="LMARGIN", new_y="NEXT")

        # Filter summary (compact, grey) — repeated so each page has context
        if self._filters_text:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(100, 100, 100)
            self.cell(
                0,
                _FILTER_H,
                "Filters: " + self._filters_text,
                new_x="LMARGIN",
                new_y="NEXT",
            )
            self.set_text_color(0, 0, 0)

        self.ln(2)

        # Column header row — shaded, repeated on every page
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(220, 230, 245)
        for header_text, width in zip(self._col_headers, self._col_widths):
            max_chars = max(4, math.floor(width / _CHAR_W) - 1)
            self.cell(width, _HEADER_H, str(header_text)[:max_chars], border=1, fill=True)
        self.ln()

    def footer(self) -> None:
        self.set_y(-_FOOTER_MARGIN)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        dt_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.cell(0, 5, f"Page {self.page_no()} | {dt_str}", align="C")
        self.set_text_color(0, 0, 0)


def generate_table_pdf(
    title: str,
    filters: dict[str, str],
    columns: list[str],
    rows: list[list[str]],
) -> bytes:
    """Return A4 PDF bytes for a filterable data table.

    Args:
        title: Document title shown on every page.
        filters: Active filter key/value pairs shown as a summary line.
        columns: Column header labels.
        rows: Table data — each inner list corresponds to one row.
    """
    n_cols = max(len(columns), 1)
    orientation = "L" if n_cols > 6 else "P"

    # Compute column widths before creating the PDF instance so we can pass them
    # to __init__ (which is called before add_page → header).
    l_margin = r_margin = 12.0
    page_w = 297.0 if orientation == "L" else 210.0
    usable_w = page_w - l_margin - r_margin
    col_width = usable_w / n_cols
    col_widths = [col_width] * n_cols

    filters_text = "  |  ".join(f"{k}: {v}" for k, v in filters.items() if v)

    pdf = _TablePDF(
        doc_title=title or "Export",
        filters_text=filters_text,
        col_headers=columns,
        col_widths=col_widths,
        orientation=orientation,
        unit="mm",
        format="A4",
    )
    pdf.set_auto_page_break(auto=True, margin=_FOOTER_MARGIN + 3)
    pdf.set_margins(left=l_margin, top=8, right=r_margin)
    pdf.add_page()

    # Data rows with alternating shading
    pdf.set_font("Helvetica", "", 9)
    for idx, row_data in enumerate(rows):
        if idx % 2 == 1:
            pdf.set_fill_color(245, 248, 255)
        else:
            pdf.set_fill_color(255, 255, 255)
        for i, cell_text in enumerate(row_data):
            width = col_widths[i] if i < len(col_widths) else col_widths[-1]
            max_chars = max(4, math.floor(width / _CHAR_W) - 1)
            text = str(cell_text or "").strip()[:max_chars]
            pdf.cell(width, _ROW_H, text, border=1, fill=True)
        pdf.ln()

    return bytes(pdf.output())
