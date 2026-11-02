#!/usr/bin/env python3
"""Generate a tiny synthetic annual report used to reproduce the skill offline.

The document is fictional and holds no real company data.  It is written with
a minimal PDF writer so that the sample needs no dependency beyond the Python
standard library.

Usage::

    python scripts/make_sample_pdf.py --out sample_annual_report.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

__all__ = ["build_pdf", "sample_pages"]

PAGES: list[list[str]] = [
    [
        "EXAMPLE DYNAMICS CORPORATION",
        "",
        "ANNUAL REPORT ON FORM 10-K",
        "For the fiscal year ended December 31, 2023",
        "",
        "Synthetic document generated for skill testing only.",
        "It describes no real company and contains no real financial data.",
    ],
    [
        "TABLE OF CONTENTS",
        "",
        "Part I",
        "Item 1. Business ....................................... 3",
        "Item 7. Management's Discussion and Analysis .......... 25",
        "Item 8. Financial Statements and Supplementary Data .. 40",
        "",
        "Consolidated Statements of Operations .................. 42",
        "Consolidated Balance Sheets .......................... 43",
        "Consolidated Statements of Cash Flows .................. 44",
        "Notes to Consolidated Financial Statements ............. 45",
    ],
    [
        "EXAMPLE DYNAMICS CORPORATION",
        "CONSOLIDATED STATEMENTS OF OPERATIONS",
        "(in millions, except per share data)",
        "",
        "                                                        2023      2022      2021",
        "Net sales                                           12,480    11,020     9,745",
        "Cost of sales                                        7,240     6,530     5,880",
        "Gross profit                                         5,240     4,490     3,865",
        "Operating income                                     2,010     1,640     1,310",
        "Net income                                           1,455     1,180       905",
        "Diluted earnings per share                             4.35      3.52      2.70",
    ],
    [
        "EXAMPLE DYNAMICS CORPORATION",
        "CONSOLIDATED BALANCE SHEETS",
        "(in millions)",
        "",
        "                                                        2023      2022",
        "Cash and cash equivalents                            2,310     1,880",
        "Accounts receivable, net                              1,540     1,320",
        "Inventories                                          1,170       910",
        "Total current assets                                 5,020     4,110",
        "Total current liabilities                            2,760     2,395",
        "Total stockholders' equity                          11,430    10,115",
    ],
    [
        "EXAMPLE DYNAMICS CORPORATION",
        "CONSOLIDATED STATEMENTS OF CASH FLOWS",
        "(in millions)",
        "",
        "                                                        2023      2022",
        "Net cash provided by operating activities            1,890     1,470",
        "Purchases of property, plant and equipment            (640)     (520)",
        "Net cash used in investing activities                (705)     (560)",
        "Net cash provided by financing activities              (120)     (180)",
        "Net increase in cash and cash equivalents             1,065       730",
    ],
    [
        "NOTE 8 - PROPERTY, PLANT AND EQUIPMENT",
        "",
        "The Company's property, plant and equipment consisted of the following:",
        "",
        "                                                        2023      2022",
        "Manufacturing equipment                              3,120     2,860",
        "Office and warehouse buildings                       1,540     1,410",
        "Leasehold improvements                                 610       520",
        "",
        "During fiscal 2023 the Company made capital expenditures of $640 million,",
        "compared with $520 million in fiscal 2022. Capital expenditures are",
        "presented as purchases of property, plant and equipment in the consolidated",
        "statements of cash flows.",
    ],
]


def _escape(text: str) -> str:
    """Escape a string for a PDF literal."""

    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content_stream(lines: list[str]) -> bytes:
    """Build the page content stream that draws the lines."""

    parts = ["BT", "/F1 11 Tf", "14 TL", "56 736 Td"]
    for line in lines:
        parts.append(f"({_escape(line)}) Tj")
        parts.append("T*")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1", "replace")


def build_pdf(pages: list[list[str]]) -> bytes:
    """Render the pages into a minimal, valid PDF file."""

    count = len(pages)
    kids = [f"{4 + 2 * index} 0 R" for index in range(count)]
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {count} >>".encode("ascii"),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    }
    for index, lines in enumerate(pages):
        page_id = 4 + 2 * index
        content_id = 5 + 2 * index
        stream = _content_stream(lines)
        objects[content_id] = (
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
        objects[page_id] = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        ).encode("ascii")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for number in range(1, max(objects) + 1):
        offsets[number] = len(out)
        out += f"{number} 0 obj\n".encode("ascii") + objects[number] + b"\nendobj\n"

    xref_position = len(out)
    size = max(objects) + 1
    out += f"xref\n0 {size}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for number in range(1, size):
        out += f"{offsets[number]:010d} 00000 n \n".encode("ascii")
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF\n".encode("ascii")
    return bytes(out)


def sample_pages() -> list[list[str]]:
    """The pages of the synthetic annual report."""

    return [list(page) for page in PAGES]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="make_sample_pdf.py",
        description="生成一个用于离线复现的极小合成年报 PDF。",
    )
    parser.add_argument("--out", default="sample_annual_report.pdf", help="输出 PDF 路径")
    args = parser.parse_args(argv)

    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(build_pdf(sample_pages()))
    print(f"wrote {target} ({len(sample_pages())} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
