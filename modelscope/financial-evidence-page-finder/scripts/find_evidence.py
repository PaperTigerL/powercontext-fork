#!/usr/bin/env python3
"""Locate citable evidence pages in a financial report for one question.

The tool reads every physical page of a PDF, scores each page by how much
evidence it carries for the question, and returns the best pages with their
page number, the words that matched and a short excerpt.

Design notes:

* Page numbers are *physical* PDF page numbers starting at 1.  A financial
  report also prints its own page numbers, and the two rarely agree; always
  verify against the physical page count.
* The SHA-256 of the input file is returned, so a caller can prove which
  revision of the document was read and re-locate it later.
* Scoring rewards *coverage* of the question rather than raw term frequency.
  A page that names the statement or the note the question is about outranks
  a page that merely repeats the words.
* Only the standard library and ``pypdf`` are required.  ``--text`` accepts a
  plain-text report (pages separated by a form feed) and needs no extra
  dependency at all.

Usage::

    python scripts/find_evidence.py --pdf report.pdf --question "net sales in fiscal 2023" --topk 5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

__all__ = ["main"]

TOOL_VERSION = "1.0.0"

# --------------------------------------------------------------------------
# Lexical resources
# --------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z]+|\d+")
_NUMBER_RE = re.compile(r"^\d+$")
_NOTE_TITLE_RE = re.compile(r"^\s*note\s+\d+\b", re.IGNORECASE)

# Function words and finance-question boilerplate.  These carry no evidence
# on their own and would otherwise create meaningless phrase matches.
_STOPWORD_TEXT = """a an the and or for of to in on at by from with as is are was were be been being
what which who how why when where do does did can could should would will it its
this that these those there any all both each other others some such same
if then than not no nor but so very much many more most less least
we our us you your i me my they them their he she his her him
reported reportedly please
using used use uses useful given give gives response respond question questions
relying rely relies relied detail details shown show shows showing
calculate calculated calculating calculation answer answers answered
based within between during through across above below over under
respectively approximately roughly around round decimal place precision
units unit per define defined defining definition means meaning
perspective investment analyst only assume assumes assumption
according indicate indicates including included includes include
also may might will would can could shall
year years fiscal fy quarter
company companies corporation corp inc ltd plc
respect regarding concerning subject matter
"""
_STOPWORDS = frozenset(_STOPWORD_TEXT.split())

# The three primary financial statements and the titles a 10-K gives them.
_STATEMENT_GROUPS: tuple[tuple[str, ...], ...] = (
    (
        "income statement",
        "statement of income",
        "statements of operations",
        "statement of operations",
        "profit and loss",
        "p&l",
    ),
    (
        "balance sheet",
        "balance sheets",
        "statement of financial position",
        "statements of financial position",
    ),
    (
        "cash flow",
        "cash flows",
        "statement of cash flows",
        "statements of cash flows",
    ),
)

_STATEMENT_LABELS = ("income", "balance", "cashflow")

# Financial concepts whose wording in the report differs from the wording of
# the question.  Each alias also names the statement it can be read from, so a
# question about a computed figure can still reach the statement page.
_DOMAIN_ALIASES: tuple[tuple[str, tuple[str, ...], tuple[int, ...]], ...] = (
    (
        "capital expenditure",
        (
            "capital expenditures",
            "additions to property",
            "purchases of property",
            "property plant and equipment",
        ),
        (2,),
    ),
    (
        "capex",
        (
            "capital expenditures",
            "purchases of property",
            "additions to property",
            "property plant and equipment",
        ),
        (2,),
    ),
    ("capital intensive", ("capital expenditures", "property plant and equipment", "additions to property"), (0, 2)),
    ("ebitda", ("operating income", "operating profit", "depreciation and amortization"), (0, 2)),
    ("quick ratio", ("current assets", "current liabilities"), (1,)),
    ("liquidity", ("current assets", "current liabilities", "cash and cash equivalents"), (1,)),
    ("gross margin", ("gross profit", "cost of sales", "cost of products"), (0,)),
    ("effective tax rate", ("provision for income taxes", "income tax expense"), (0,)),
    ("legal", ("legal proceedings", "litigation", "legal actions"), ()),
    ("customer concentration", ("accounted for", "customers"), ()),
    (
        "primary customers",
        (
            "significant portion of our revenue",
            "substantial portion of our revenue",
            "significant portion of our business",
            "our revenues were earned",
            "concentration of revenue",
        ),
        (),
    ),
    ("days payable outstanding", ("accounts payable",), (1,)),
    ("revenue", ("net sales", "total revenues", "net revenue"), ()),
    ("working capital", ("current assets", "current liabilities"), (1,)),
    ("operating margin", ("operating income", "operating profit", "gross profit"), (0,)),
    ("segment", ("business segment", "reportable segment", "operating segment"), ()),
    (
        "geographies",
        ("north america", "latin america", "europe", "asia pacific", "middle east", "africa"),
        (),
    ),
)

# Question concepts that are answered by a reported financial statement.
_COMPUTATIONAL_TRIGGERS = frozenset(
    {
        "quick ratio",
        "liquidity",
        "gross margin",
        "effective tax rate",
        "capital expenditure",
        "capital expenditures",
        "capital intensive",
        "days payable outstanding",
        "working capital",
        "ebitda",
        "capex",
    }
)

_COMPUTATIONAL_TERM_TEXT = """ratio ratios margin margins percentage percent rate rates outstanding dpo
ebitda capex liquidity leverage solvency coverage working inventory inventories
payable receivable
"""
_COMPUTATIONAL_TERMS = frozenset(_COMPUTATIONAL_TERM_TEXT.split())

_COMPUTATIONAL_PHRASES = (
    "income statement",
    "statement of income",
    "statements of operations",
    "statement of operations",
    "balance sheet",
    "cash flow",
    "p&l",
    "per share",
    "line items",
)

_STATEMENT_PAGE_PATTERNS = (
    "consolidated statements of operations",
    "consolidated statement of operations",
    "consolidated statements of income",
    "consolidated statement of income",
    "consolidated balance sheets",
    "consolidated balance sheet",
    "consolidated statements of cash flows",
    "consolidated statements of comprehensive income",
    "consolidated statements of equity",
    "consolidated statements of financial position",
    "dollars in millions",
    "in millions, except",
    "in thousands, except",
)

# Weights of the evidence layers.  They are kept in one place so the behaviour
# of the search stays reproducible and easy to tune.
_WEIGHT_TERM = 0.5
_WEIGHT_PHRASE = 2.0
_WEIGHT_ALIAS = 2.0
_WEIGHT_TITLE = 4.0
_WEIGHT_TITLE_FLAT = 6.0
_WEIGHT_HEADING = 1.0
_WEIGHT_NOTE = 4.0
_WEIGHT_FACET = 20.0
_WEIGHT_STATEMENT = 2.0

# How much of a page is treated as its heading.
_HEAD_LINES = 20
_TOP_LINES = 6
_HEAD_TOKENS = 40
_WIDE_TOKENS = 400
_TOP_TOKENS = 120
_NOTE_TOKENS = 200


# --------------------------------------------------------------------------
# Tokenisation helpers
# --------------------------------------------------------------------------


def tokenize(text: str) -> list[str]:
    """Split text into lowercase word and number tokens."""

    return _TOKEN_RE.findall(text.casefold())


def normalize(term: str) -> str:
    """Fold a word to its evidence form: ``cyclicality`` and ``cyclical`` collapse.

    The fold is deliberately crude: it removes a plural ``s`` and clips very
    long words, which is enough to unify the financial vocabulary without
    needing a full stemmer dependency.
    """

    if len(term) > 4 and term.endswith("s") and not term.endswith("ss"):
        term = term[:-1]
    if len(term) > 5:
        term = term[:5]
    return term


def phrase_form(phrase: str) -> str:
    """Normalised, space separated form of a phrase."""

    return " ".join(normalize(token) for token in phrase.split())


def _normalized_question(question: str) -> str:
    """Case-folded question with punctuation replaced by spaces."""

    return " ".join(_TOKEN_RE.findall(question.casefold()))


# --------------------------------------------------------------------------
# Page model
# --------------------------------------------------------------------------


@dataclass
class Page:
    """One physical page of a document, prepared for evidence scoring."""

    number: int
    text: str
    stemmed: list[str] = field(default_factory=list)
    stemmed_counts: Counter = field(default_factory=Counter)
    normalized: str = ""
    head_normalized: str = ""
    wide_normalized: str = ""
    top_normalized: str = ""
    note_normalized: str = ""
    numeric_ratio: float = 0.0
    is_statement: bool = False
    facets: frozenset = frozenset()


def prepare_page(number: int, text: str) -> Page:
    """Read one page into the form the scorer needs."""

    tokens = tokenize(text)
    stemmed = [normalize(token) for token in tokens]
    numeric = sum(1 for token in tokens if _NUMBER_RE.match(token))
    lowered = text.casefold()
    lines = [line for line in text.splitlines() if line.strip()]
    head_tokens = tokens[:_HEAD_TOKENS]
    wide_tokens = tokenize(" ".join(lines[:_HEAD_LINES]))[:_WIDE_TOKENS]
    top_tokens = tokenize(" ".join(lines[:_TOP_LINES]))[:_TOP_TOKENS]
    note_tokens = tokenize(" ".join(line for line in lines if _NOTE_TITLE_RE.match(line)))[:_NOTE_TOKENS]

    page = Page(number=number, text=text, stemmed=stemmed, stemmed_counts=Counter(stemmed))
    page.numeric_ratio = numeric / max(1, len(tokens))
    page.is_statement = any(pattern in lowered for pattern in _STATEMENT_PAGE_PATTERNS) or page.numeric_ratio >= 0.22
    page.normalized = " " + " ".join(stemmed) + " "
    page.head_normalized = " " + " ".join(normalize(token) for token in head_tokens) + " "
    page.wide_normalized = " " + " ".join(normalize(token) for token in wide_tokens) + " "
    page.top_normalized = " " + " ".join(normalize(token) for token in top_tokens) + " "
    page.note_normalized = " " + " ".join(normalize(token) for token in note_tokens) + " "
    page.facets = _statement_facets(page)
    return page


def _statement_facets(page: Page) -> frozenset:
    """Statement groups whose canonical title heads the page.

    A 10-K gives each statement one titled page, so the heading alone
    identifies the page that carries a statement the question names.
    """

    found: set[int] = set()
    for index, group in enumerate(_STATEMENT_GROUPS):
        for phrase in group:
            if f" {phrase_form(phrase)} " in page.top_normalized:
                found.add(index)
                break
    return frozenset(found)


# --------------------------------------------------------------------------
# Document loading
# --------------------------------------------------------------------------


class InputError(Exception):
    """Raised when the input document cannot be read."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_pdf_pages(path: Path) -> tuple[list[Page], str]:
    """Parse every physical page of a PDF.  Returns the pages and the file digest."""

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise InputError(
            "pypdf is required to read PDF files. Install it with "
            "'pip install pypdf', or use --text for a plain-text report."
        ) from exc

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read '{path}': {exc}") from exc

    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            # A PDF with an empty owner password is a legal input.
            try:
                reader.decrypt("")
            except Exception as exc:  # pragma: no cover - depends on the file
                raise InputError(f"'{path}' is encrypted and cannot be opened: {exc}") from exc
        page_objects = list(reader.pages)
    except InputError:
        raise
    except Exception as exc:
        raise InputError(f"'{path}' is not a readable PDF: {exc}") from exc

    pages: list[Page] = []
    for index, page_object in enumerate(page_objects):
        try:
            text = page_object.extract_text() or ""
        except Exception:  # pragma: no cover - depends on the file
            text = ""
        pages.append(prepare_page(index + 1, text))
    return pages, _sha256(raw)


def load_text_pages(path: Path) -> tuple[list[Page], str]:
    """Read a plain-text report.  A form feed separates pages."""

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read '{path}': {exc}") from exc
    text = raw.decode("utf-8", errors="replace")
    chunks = [chunk for chunk in text.split("\f")] if "\f" in text else [text]
    pages = [prepare_page(index + 1, chunk) for index, chunk in enumerate(chunks)]
    return pages, _sha256(raw)


# --------------------------------------------------------------------------
# Query analysis
# --------------------------------------------------------------------------


@dataclass
class Unit:
    """One piece of evidence a page can carry: a word or a phrase."""

    needle: str
    idf: float
    kind: str
    group: str = ""
    surface: str = ""


def content_terms(question: str) -> list[str]:
    """Question words that can carry evidence."""

    return [term for term in dict.fromkeys(tokenize(question)) if term not in _STOPWORDS and len(term) > 1]


def question_phrases(question: str) -> list[tuple[str, ...]]:
    """Contiguous token windows that carry at least two evidence words.

    The window must start and end on an evidence word, so instruction glue
    such as "what is the fy" never becomes a searchable phrase.
    """

    stream = tokenize(question)
    phrases: list[tuple[str, ...]] = []
    for size in (4, 3, 2):
        for start in range(0, len(stream) - size + 1):
            window = stream[start : start + size]
            if window[0] in _STOPWORDS or window[-1] in _STOPWORDS:
                continue
            if sum(1 for token in window if token not in _STOPWORDS) >= 2:
                phrases.append(tuple(window))
    return phrases


def expansion_groups(question: str) -> list[tuple[str, str, tuple[int, ...]]]:
    """Alternate wordings of the question, grouped by the concept they belong to."""

    forms = (_normalized_question(question), question.casefold())
    found: list[tuple[str, str, tuple[int, ...]]] = []
    for index, group in enumerate(_STATEMENT_GROUPS):
        if any(word in form for form in forms for word in group):
            for phrase in group:
                found.append((f"statement-{index}", phrase, (index,)))
    for trigger, alternatives, statements in _DOMAIN_ALIASES:
        if any(trigger in form for form in forms):
            for phrase in alternatives:
                found.append((trigger, phrase, statements))
    return found


def computational_intent(question: str) -> bool:
    """Whether the question asks for a number computed from reported statements."""

    raw = question.casefold()
    if any(phrase in raw for phrase in _COMPUTATIONAL_PHRASES):
        return True
    if "%" in raw:
        return True
    forms = (_normalized_question(question), raw)
    if any(trigger in form for form in forms for trigger in _COMPUTATIONAL_TRIGGERS):
        return True
    return any(term in _COMPUTATIONAL_TERMS for term in tokenize(question))


class Corpus:
    """The pages of one document, with their word statistics."""

    def __init__(self, pages: Sequence[Page]) -> None:
        self.pages = list(pages)
        self.total = len(self.pages)
        self.df: Counter = Counter()
        for page in self.pages:
            self.df.update(set(page.stemmed))
        self._idf: dict[str, float] = {}

    def idf(self, term: str) -> float:
        cached = self._idf.get(term)
        if cached is None:
            count = self.df.get(term, 0)
            cached = math.log(1 + (self.total - count + 0.5) / (count + 0.5))
            self._idf[term] = cached
        return cached


def _phrase_idf(corpus: Corpus, phrase: Sequence[str]) -> float:
    """Rarity of a phrase, measured on its evidence words only."""

    content = [token for token in phrase if token not in _STOPWORDS] or list(phrase)
    values = [corpus.idf(normalize(token)) for token in content]
    return sum(values) / len(values)


def evidence_units(corpus: Corpus, question: str) -> list[Unit]:
    """Build the list of things a page can be scored on."""

    units: list[Unit] = []
    for term in content_terms(question):
        units.append(
            Unit(
                needle=normalize(term),
                idf=corpus.idf(normalize(term)),
                kind="term",
                surface=term,
            )
        )
    for phrase in question_phrases(question):
        units.append(
            Unit(
                needle=" ".join(normalize(token) for token in phrase),
                idf=_phrase_idf(corpus, list(phrase)),
                kind="phrase",
                surface=" ".join(phrase),
            )
        )
    for group, alias, _statements in expansion_groups(question):
        units.append(
            Unit(
                needle=phrase_form(alias),
                idf=_phrase_idf(corpus, alias.split()),
                kind="alias",
                group=group,
                surface=alias,
            )
        )
    return units


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


@dataclass
class Hit:
    """One matched piece of evidence on one page."""

    kind: str
    surface: str
    idf: float


def score_page(
    page: Page,
    units: Sequence[Unit],
    triggered: set[int],
    computational: bool,
) -> tuple[float, list[Hit]]:
    """Score one page by the evidence of the question it carries."""

    score = 0.0
    hits: list[Hit] = []
    for unit in units:
        if unit.kind == "term":
            if not page.stemmed_counts.get(unit.needle):
                continue
            score += unit.idf * _WEIGHT_TERM
            if f" {unit.needle} " in page.wide_normalized:
                score += unit.idf * _WEIGHT_HEADING
            if f" {unit.needle} " in page.note_normalized:
                score += unit.idf * _WEIGHT_NOTE
            hits.append(Hit(kind="term", surface=unit.surface, idf=unit.idf))
            continue
        needle = f" {unit.needle} "
        if needle not in page.normalized:
            continue
        score += unit.idf * (_WEIGHT_ALIAS if unit.kind == "alias" else _WEIGHT_PHRASE)
        if needle in page.head_normalized:
            score += unit.idf * _WEIGHT_TITLE + _WEIGHT_TITLE_FLAT
        hits.append(Hit(kind=unit.kind, surface=unit.surface, idf=unit.idf))
    score += _WEIGHT_FACET * len(page.facets & triggered)
    if computational and page.is_statement:
        score += _WEIGHT_STATEMENT
    return score, hits


# --------------------------------------------------------------------------
# Excerpt extraction
# --------------------------------------------------------------------------

_SEPARATOR = r"[\s,;:·•\-]*"


def _literal_pattern(words: Sequence[str]) -> str:
    """Build a regex for a phrase, tolerant of the punctuation a PDF adds."""

    parts = [
        r"(?<![A-Za-z0-9])" + re.escape(word) + r"(?![A-Za-z0-9])" for word in words if word
    ]
    if not parts:
        return ""
    return _SEPARATOR.join(parts)


def _highlight_pattern(surfaces: Iterable[str]) -> re.Pattern | None:
    """One regex that marks every matched surface form in an excerpt."""

    alternatives: list[str] = []
    for surface in surfaces:
        words = [word for word in re.split(r"[^A-Za-z0-9&]+", surface) if word]
        if not words:
            continue
        pattern = _literal_pattern(words)
        if pattern and pattern not in alternatives:
            alternatives.append(pattern)
    if not alternatives:
        return None
    alternatives.sort(key=len, reverse=True)
    return re.compile("|".join(f"(?:{item})" for item in alternatives), re.IGNORECASE)


def _build_patterns(terms: Sequence[str], phrases: Sequence[str], aliases: Sequence[str]) -> dict:
    """Build the patterns used for highlighting and for picking the excerpt line.

    Word patterns, phrase patterns and alias patterns are kept apart because
    they carry a different weight when the tool chooses which line of a page
    to quote.  A bare year is the weakest evidence of all.
    """

    alpha_terms = [term for term in terms if not term.isdigit()]
    number_terms = [term for term in terms if term.isdigit()]
    highlight = _highlight_pattern(list(terms) + list(phrases) + list(aliases))
    return {
        "highlight": highlight,
        "word": _highlight_pattern(alpha_terms),
        "number": _highlight_pattern(number_terms),
        "phrase": _highlight_pattern(phrases),
        "alias": _highlight_pattern(aliases),
    }


def _count(pattern: re.Pattern | None, line: str) -> int:
    return len(pattern.findall(line)) if pattern else 0


def best_excerpt(text: str, patterns: dict, max_chars: int) -> str:
    """Return the part of a page that carries the most evidence.

    An alias or a phrase is worth more than a single word, and a single word
    is worth more than a bare year, so the line that names the metric is
    quoted rather than the header row that repeats the fiscal year.
    """

    lines = text.splitlines()
    best_index = -1
    best_score = -1
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        primary = (
            3 * _count(patterns.get("alias"), line)
            + 2 * _count(patterns.get("phrase"), line)
            + _count(patterns.get("word"), line)
        )
        numeric = min(_count(patterns.get("number"), line), 3)
        score = primary * 10 + numeric
        if score > best_score:
            best_score = score
            best_index = index
    if best_index < 0:
        for index, line in enumerate(lines):
            if line.strip():
                best_index = index
                break
    if best_index < 0:
        return ""

    chunk: list[str] = []
    size = 0
    for line in lines[best_index:]:
        if size + len(line) > max_chars and chunk:
            break
        chunk.append(line.strip())
        size += len(line) + 1
    excerpt = " ".join(part for part in chunk if part)
    pattern = patterns.get("highlight")
    if pattern:
        excerpt = pattern.sub(lambda match: f"[[{match.group(0)}]]", excerpt)
    return excerpt[:max_chars]


# --------------------------------------------------------------------------
# Result assembly
# --------------------------------------------------------------------------


def build_result(
    pages: Sequence[Page],
    corpus: Corpus,
    question: str,
    topk: int,
    statement: str,
    min_score: float,
    max_snippet: int,
) -> dict:
    """Score every page and return the best ones."""

    units = evidence_units(corpus, question)
    computational = computational_intent(question)

    triggered: set[int] = set()
    for group, _alias, statements in expansion_groups(question):
        if group.startswith("statement-"):
            triggered.add(int(group.split("-", 1)[1]))
        triggered.update(statements)
    if statement != "auto":
        triggered.add(_STATEMENT_LABELS.index(statement))

    terms = content_terms(question)
    phrases = [" ".join(phrase) for phrase in question_phrases(question)]
    aliases = [alias for _group, alias, _statements in expansion_groups(question)]

    patterns = _build_patterns(terms, phrases, aliases)

    scored: list[tuple[float, int, Page, list[Hit]]] = []
    for page in pages:
        score, hits = score_page(page, units, triggered, computational)
        scored.append((score, page.number, page, hits))
    scored.sort(key=lambda item: (-item[0], item[1]))

    results = []
    for score, number, page, hits in scored:
        if score <= min_score:
            continue
        if len(results) >= topk:
            break
        term_hits = sorted({hit.surface for hit in hits if hit.kind == "term"})
        phrase_hits = sorted({hit.surface for hit in hits if hit.kind == "phrase"})
        alias_hits = sorted({hit.surface for hit in hits if hit.kind == "alias"})
        results.append(
            {
                "rank": len(results) + 1,
                "page_number": number,
                "score": round(score, 4),
                "is_statement_page": page.is_statement,
                "statement_facets": sorted(_STATEMENT_LABELS[index] for index in page.facets),
                "matched_terms": term_hits,
                "matched_phrases": phrase_hits,
                "matched_aliases": alias_hits,
                "snippet": best_excerpt(page.text, patterns, max_snippet),
            }
        )

    return {
        "tool": "find_evidence",
        "version": TOOL_VERSION,
        "question": question,
        "query": {
            "terms": terms,
            "phrases": phrases,
            "aliases": aliases,
            "statement_hints": sorted(_STATEMENT_LABELS[index] for index in triggered),
            "computational_intent": computational,
        },
        "results": results,
        "citation_pages": [item["page_number"] for item in results],
    }


def render_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_markdown(payload: dict, document: dict) -> str:
    lines: list[str] = []
    lines.append("# 财报证据页检索结果")
    lines.append("")
    lines.append(f"- 文档：`{document['path']}`")
    lines.append(f"- SHA-256：`{document['sha256']}`")
    lines.append(f"- 物理页数：{document['page_count']}")
    lines.append(f"- 问题：{payload['question']}")
    hints = payload["query"]["statement_hints"]
    lines.append(f"- 命中的报表类型：{', '.join(hints) if hints else '（无）'}")
    lines.append("")
    if not payload["results"]:
        lines.append("没有命中任何页面。请换一个更具体的问法，或提高 `--topk`。")
        return "\n".join(lines) + "\n"
    lines.append("| 排名 | 物理页码 | 得分 | 命中词 | 片段 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in payload["results"]:
        matched = ", ".join(item["matched_terms"] + item["matched_phrases"] + item["matched_aliases"])
        snippet = item["snippet"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {item['rank']} | {item['page_number']} | {item['score']} | {matched} | {snippet} |")
    lines.append("")
    lines.append("## 引用页列表")
    lines.append("")
    for item in payload["results"]:
        lines.append(f"{item['rank']}. 第 {item['page_number']} 页（得分 {item['score']}）")
    lines.append("")
    lines.append("页码为 PDF 物理页码，从 1 开始；请用 SHA-256 确认回查的是同一份文件。")
    return "\n".join(lines) + "\n"


def render_text(payload: dict, document: dict) -> str:
    lines: list[str] = []
    lines.append(f"文档: {document['path']}")
    lines.append(f"SHA-256: {document['sha256']}")
    lines.append(f"物理页数: {document['page_count']}")
    lines.append(f"问题: {payload['question']}")
    lines.append("")
    if not payload["results"]:
        lines.append("没有命中任何页面。")
        return "\n".join(lines) + "\n"
    for item in payload["results"]:
        lines.append(f"[{item['rank']}] 第 {item['page_number']} 页  得分={item['score']}")
        matched = ", ".join(item["matched_terms"] + item["matched_phrases"] + item["matched_aliases"])
        lines.append(f"    命中: {matched}")
        lines.append(f"    片段: {item['snippet']}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------

_EPILOG = """\
示例:
  python scripts/find_evidence.py --pdf report.pdf --question "net sales in fiscal 2023"
  python scripts/find_evidence.py --pdf report.pdf --question "capital expenditures" --topk 10 --format json
  python scripts/find_evidence.py --pdf report.pdf --question "total current assets" --statement balance
  python scripts/find_evidence.py --text report.txt --question "segment revenue" --format markdown
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="find_evidence.py",
        description="在一份财报 PDF 中定位可回查的证据页（物理页码 + 命中片段）。",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--pdf", help="财报 PDF 路径")
    parser.add_argument("--text", help="纯文本财报路径，页之间用换页符（\\f）分隔")
    parser.add_argument("--question", required=True, help="自然语言财务问题")
    parser.add_argument("--topk", type=int, default=5, help="返回的证据页数量，默认 5")
    parser.add_argument(
        "--statement",
        choices=["auto", "income", "balance", "cashflow"],
        default="auto",
        help="报表类型提示：auto 自动识别，income 利润表，balance 资产负债表，cashflow 现金流量表",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "text"],
        default="markdown",
        help="输出格式，默认 markdown",
    )
    parser.add_argument("--out", help="把结果写入文件而不是标准输出")
    parser.add_argument("--min-score", type=float, default=0.0, help="低于该得分的页面不返回，默认 0")
    parser.add_argument("--max-snippet", type=int, default=320, help="片段最大字符数，默认 320")
    parser.add_argument("--version", action="version", version=f"find_evidence {TOOL_VERSION}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if bool(args.pdf) == bool(args.text):
        parser.error("必须且只能指定 --pdf 或 --text 其中之一")

    try:
        if args.pdf:
            path = Path(args.pdf)
            pages, digest = load_pdf_pages(path)
            source = "pdf"
        else:
            path = Path(args.text)
            pages, digest = load_text_pages(path)
            source = "text"
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not pages:
        print(f"error: '{path}' 没有可解析的页面", file=sys.stderr)
        return 2

    corpus = Corpus(pages)
    payload = build_result(
        pages=pages,
        corpus=corpus,
        question=args.question,
        topk=max(1, args.topk),
        statement=args.statement,
        min_score=args.min_score,
        max_snippet=max(80, args.max_snippet),
    )
    document = {
        "path": str(path),
        "sha256": digest,
        "page_count": len(pages),
        "source": source,
    }
    payload["document"] = document

    if args.format == "json":
        rendered = render_json(payload)
    elif args.format == "text":
        rendered = render_text(payload, document)
    else:
        rendered = render_markdown(payload, document)

    if args.out:
        Path(args.out).write_text(rendered, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(rendered)

    return 0 if payload["results"] else 1


if __name__ == "__main__":
    sys.exit(main())
