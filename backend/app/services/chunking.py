"""Deterministic, page-aware chunking.

The same input always produces identical chunk boundaries, page ranges, and checksums.
Token counts use tiktoken (``cl100k_base``) when available, falling back to a deterministic
word/punctuation count so chunking never depends on the network at runtime.
"""

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, replace

CHUNKER_VERSION = "heading-window-v1"
TARGET_TOKENS = 700
OVERLAP_TOKENS = 100

_WORD_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_encoder = None
_encoder_unavailable = False


def count_tokens(text: str) -> int:
    global _encoder, _encoder_unavailable
    if not _encoder_unavailable:
        try:
            if _encoder is None:
                import tiktoken

                _encoder = tiktoken.get_encoding("cl100k_base")
            return len(_encoder.encode(text))
        except Exception:
            _encoder_unavailable = True
    return len(_WORD_RE.findall(text))


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


@dataclass(frozen=True)
class ChunkDraft:
    ordinal: int
    heading: str | None
    content: str
    page_start: int
    page_end: int
    token_count: int
    checksum: str


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    collapsed = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return collapsed.strip()


def _is_heading(text: str) -> bool:
    if "\n" in text or not (3 <= len(text) <= 80):
        return False
    if text.endswith((".", ",", ";", ":")):
        return False
    if re.match(r"^\d+(\.\d+)*\s+\S", text):
        return True
    return text.istitle() or text.isupper()


@dataclass(frozen=True)
class _Segment:
    page_number: int
    text: str
    is_heading: bool
    tokens: int


def remove_repeated_lines(pages: list[PageText]) -> list[PageText]:
    """Remove short lines (headers/footers) that repeat across most pages."""
    if len(pages) < 3:
        return pages
    per_page_lines: list[list[str]] = []
    counts: Counter[str] = Counter()
    for page in pages:
        lines = [ln for ln in normalize_whitespace(page.text).split("\n") if ln]
        per_page_lines.append(lines)
        for line in set(lines):
            counts[line] += 1
    threshold = max(3, int(len(pages) * 0.6))
    repeated = {ln for ln, c in counts.items() if c >= threshold and len(ln) <= 80}
    return [
        PageText(page.page_number, "\n".join(ln for ln in lines if ln not in repeated))
        for page, lines in zip(pages, per_page_lines, strict=True)
    ]


def _segment_pages(pages: list[PageText]) -> list[_Segment]:
    segments: list[_Segment] = []
    for page in pages:
        normalized = normalize_whitespace(page.text)
        for paragraph in re.split(r"\n{2,}", normalized):
            paragraph = paragraph.strip()
            if paragraph:
                segments.append(
                    _Segment(
                        page.page_number, paragraph, _is_heading(paragraph), count_tokens(paragraph)
                    )
                )
    return segments


def chunk_pages(pages: list[PageText]) -> list[ChunkDraft]:
    segments = _segment_pages(remove_repeated_lines(list(pages)))
    if not segments:
        return []

    heading_at: list[str | None] = []
    current_heading: str | None = None
    for segment in segments:
        if segment.is_heading:
            current_heading = segment.text
        heading_at.append(current_heading)

    drafts: list[ChunkDraft] = []
    n = len(segments)
    i = 0
    ordinal = 0
    while i < n:
        j = i
        tokens = 0
        while j < n and (tokens < TARGET_TOKENS or j == i):
            tokens += segments[j].tokens
            j += 1
        window = segments[i:j]
        content = "\n\n".join(s.text for s in window)
        drafts.append(
            ChunkDraft(
                ordinal=ordinal,
                heading=heading_at[i],
                content=content,
                page_start=min(s.page_number for s in window),
                page_end=max(s.page_number for s in window),
                token_count=count_tokens(content),
                checksum=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            )
        )
        ordinal += 1
        if j >= n:
            break
        overlap = 0
        k = j
        while k > i + 1 and overlap < OVERLAP_TOKENS:
            k -= 1
            overlap += segments[k].tokens
        i = max(k, i + 1)

    # Enforce the unique (document_id, checksum) constraint: drop duplicate-content chunks.
    seen: set[str] = set()
    deduped: list[ChunkDraft] = []
    for draft in drafts:
        if draft.checksum in seen:
            continue
        seen.add(draft.checksum)
        deduped.append(replace(draft, ordinal=len(deduped)))
    return deduped
