"""Unit tests for the deterministic chunker."""

from app.services.chunking import (
    PageText,
    chunk_pages,
    count_tokens,
    normalize_whitespace,
    remove_repeated_lines,
)


def _long_page(n_paragraphs: int = 40) -> str:
    paragraphs = [
        f"Paragraph {i} discusses the SPI status register and the UART overrun flag "
        f"behaviour in considerable detail across several registers and modes. " * 3
        for i in range(n_paragraphs)
    ]
    return "\n\n".join(paragraphs)


def test_chunking_is_deterministic():
    pages = [PageText(1, _long_page())]
    first = chunk_pages(pages)
    second = chunk_pages(pages)
    assert [c.checksum for c in first] == [c.checksum for c in second]
    assert [(c.ordinal, c.page_start, c.page_end) for c in first] == [
        (c.ordinal, c.page_start, c.page_end) for c in second
    ]


def test_short_text_yields_single_chunk():
    chunks = chunk_pages([PageText(1, "A short paragraph about the UART peripheral.")])
    assert len(chunks) == 1
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 1
    assert chunks[0].ordinal == 0


def test_long_text_yields_multiple_ordered_chunks():
    chunks = chunk_pages([PageText(1, _long_page(80))])
    assert len(chunks) >= 2
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    assert all(c.token_count > 0 for c in chunks)
    assert len({c.checksum for c in chunks}) == len(chunks)


def test_page_ranges_span_pages():
    pages = [PageText(1, _long_page(2)), PageText(2, _long_page(2)), PageText(3, _long_page(2))]
    chunks = chunk_pages(pages)
    assert min(c.page_start for c in chunks) == 1
    assert max(c.page_end for c in chunks) == 3


def test_normalize_whitespace():
    assert normalize_whitespace("a   b\t c\r\n\r\n\r\nd") == "a b c\n\nd"


def test_repeated_headers_removed():
    header = "CIRCUITSAGE CONFIDENTIAL"
    pages = [
        PageText(i + 1, f"{header}\n\nUnique body {i + 1} about the timer registers here.")
        for i in range(5)
    ]
    cleaned = remove_repeated_lines(pages)
    assert all(header not in page.text for page in cleaned)
    assert all(f"Unique body {i + 1}" in cleaned[i].text for i in range(5))


def test_empty_input_yields_no_chunks():
    assert chunk_pages([PageText(1, "   \n\n  ")]) == []


def test_count_tokens_positive():
    assert count_tokens("SPI clock polarity register") > 0
