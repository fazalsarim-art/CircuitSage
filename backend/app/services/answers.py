"""Grounded answer generation with strict citation validation.

Evidence chunks are labelled C1..Cn. The model must cite claims as ``[Cn]`` and return the
INSUFFICIENT marker when the evidence does not support an answer. Citations are parsed and
validated server-side; unknown labels fail closed to an insufficient-evidence result.
"""

import re
from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings
from app.db.models.enums import AnswerStatus

ANSWER_PROMPT_VERSION = "grounded-v1"
INSUFFICIENT_MARKER = "INSUFFICIENT_EVIDENCE"
_INSUFFICIENT_TEXT = (
    "There is not enough evidence in the available documents to answer this question. "
    "The closest passages are shown below."
)
_GENERATION_FAILED_TEXT = (
    "Answer generation is currently unavailable. The retrieved evidence is shown below."
)
_CITATION_RE = re.compile(r"\[C(\d+)\]")

_SYSTEM_PROMPT = (
    "You are CircuitSage, an embedded-systems documentation assistant. Answer ONLY using "
    "the numbered evidence passages provided. Cite every material claim with its label in "
    "square brackets, e.g. [C1]. If the evidence is insufficient, reply with exactly "
    f"{INSUFFICIENT_MARKER} and nothing else. Never invent citation labels or facts."
)


@dataclass(frozen=True)
class Evidence:
    label: str
    chunk_id: object
    content: str


@dataclass(frozen=True)
class AnswerResult:
    text: str
    input_tokens: int | None
    output_tokens: int | None


@dataclass(frozen=True)
class AnswerOutcome:
    text: str
    status: AnswerStatus
    cited_labels: list[int]
    input_tokens: int | None
    output_tokens: int | None


class AnswerClient(Protocol):
    def generate(self, messages: list[dict], model: str) -> AnswerResult: ...


class OpenAIAnswerClient:
    def __init__(self, settings: Settings) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.openai_api_key)

    def generate(self, messages: list[dict], model: str) -> AnswerResult:
        response = self._client.chat.completions.create(model=model, messages=messages)
        usage = getattr(response, "usage", None)
        return AnswerResult(
            text=response.choices[0].message.content or "",
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
        )


def build_answer_client(settings: Settings) -> AnswerClient:
    return OpenAIAnswerClient(settings)


def build_prompt(query: str, evidence: list[Evidence]) -> list[dict]:
    passages = "\n\n".join(f"[{item.label}] {item.content}" for item in evidence)
    user_content = (
        f"Question:\n{query}\n\n"
        f"Evidence passages:\n{passages}\n\n"
        "Answer using only the evidence above, citing each claim with its [Cn] label."
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def evaluate_answer(text: str, num_labels: int) -> tuple[AnswerStatus, list[int]]:
    """Decide the answer status and validated citation labels from raw model output."""
    if INSUFFICIENT_MARKER in text:
        return AnswerStatus.insufficient_evidence, []
    labels = [int(m) for m in _CITATION_RE.findall(text)]
    has_invalid = any(not (1 <= label <= num_labels) for label in labels)
    valid = sorted({label for label in labels if 1 <= label <= num_labels})
    if has_invalid or not valid:
        # Reject unknown labels and refuse answers that cite nothing (fail closed).
        return AnswerStatus.insufficient_evidence, []
    return AnswerStatus.answered, valid


def generate_answer(
    client: AnswerClient, settings: Settings, query: str, evidence: list[Evidence]
) -> AnswerOutcome:
    if not evidence:
        return AnswerOutcome(_INSUFFICIENT_TEXT, AnswerStatus.insufficient_evidence, [], 0, 0)

    messages = build_prompt(query, evidence)
    try:
        result = client.generate(messages, settings.openai_chat_model)
    except Exception:
        return AnswerOutcome(
            _GENERATION_FAILED_TEXT, AnswerStatus.generation_failed, [], None, None
        )

    status, cited = evaluate_answer(result.text, len(evidence))
    if status == AnswerStatus.insufficient_evidence:
        return AnswerOutcome(
            _INSUFFICIENT_TEXT, status, [], result.input_tokens, result.output_tokens
        )
    return AnswerOutcome(result.text, status, cited, result.input_tokens, result.output_tokens)
