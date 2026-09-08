"""Unit tests for citation parsing and answer-status evaluation."""

from app.db.models.enums import AnswerStatus
from app.services.answers import (
    INSUFFICIENT_MARKER,
    Evidence,
    build_prompt,
    evaluate_answer,
)


def test_valid_citations_accepted():
    status, cited = evaluate_answer("Clears on read [C1] and [C3].", num_labels=3)
    assert status == AnswerStatus.answered
    assert cited == [1, 3]


def test_repeated_citations_deduplicated():
    status, cited = evaluate_answer("See [C2], and again [C2].", num_labels=3)
    assert status == AnswerStatus.answered
    assert cited == [2]


def test_missing_citations_fail_closed():
    status, cited = evaluate_answer("The flag clears on read.", num_labels=3)
    assert status == AnswerStatus.insufficient_evidence
    assert cited == []


def test_invented_citation_rejected():
    status, cited = evaluate_answer("Per [C9] the flag clears.", num_labels=3)
    assert status == AnswerStatus.insufficient_evidence
    assert cited == []


def test_insufficient_marker_detected():
    status, cited = evaluate_answer(INSUFFICIENT_MARKER, num_labels=3)
    assert status == AnswerStatus.insufficient_evidence
    assert cited == []


def test_build_prompt_labels_evidence():
    evidence = [
        Evidence(label="C1", chunk_id="x", content="alpha"),
        Evidence(label="C2", chunk_id="y", content="beta"),
    ]
    messages = build_prompt("why?", evidence)
    assert messages[0]["role"] == "system"
    assert "[C1] alpha" in messages[1]["content"]
    assert "[C2] beta" in messages[1]["content"]
