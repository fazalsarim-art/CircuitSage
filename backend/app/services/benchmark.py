"""Benchmark authoring service: versions, cases, relevance judgments, import/export, publish.

Published versions are immutable. Publication enforces the corpus-quality rules: a minimum
case count, at least one relevance-2/3 judgment per answerable case, and no relevant
judgments for cases in the ``unanswerable`` category.
"""

import io
import json
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.benchmark import BenchmarkCase, BenchmarkVersion, RelevanceJudgment
from app.db.models.document import Chunk
from app.db.models.enums import BenchmarkStatus, DatasetSplit, Difficulty
from app.db.models.user import User
from app.schemas.benchmark import (
    BenchmarkCaseIn,
    BenchmarkCaseUpdate,
    CaseOut,
    ImportResult,
    JudgmentIn,
    JudgmentOut,
    VersionOut,
)

MIN_CASES_FOR_PUBLISH = 100
UNANSWERABLE_CATEGORY = "unanswerable"


def _validate_enums(difficulty: str, split: str) -> None:
    if difficulty not in {d.value for d in Difficulty}:
        raise APIError(422, "invalid_difficulty", "difficulty must be easy, medium, or hard.")
    if split not in {s.value for s in DatasetSplit}:
        raise APIError(422, "invalid_split", "split must be train, validation, or test.")


def _ensure_draft(version: BenchmarkVersion) -> None:
    if version.status != BenchmarkStatus.draft:
        raise APIError(409, "published_immutable", "Published benchmark versions are immutable.")


def create_version(db: Session, user: User, name: str, description: str | None) -> BenchmarkVersion:
    highest = db.scalar(
        select(func.max(BenchmarkVersion.version)).where(BenchmarkVersion.name == name)
    )
    version = BenchmarkVersion(
        name=name,
        version=(highest or 0) + 1,
        status=BenchmarkStatus.draft,
        description=description,
        created_by=user.id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def case_count(db: Session, version_id) -> int:
    return (
        db.scalar(
            select(func.count(BenchmarkCase.id)).where(
                BenchmarkCase.benchmark_version_id == version_id
            )
        )
        or 0
    )


def version_out(db: Session, version: BenchmarkVersion) -> VersionOut:
    return VersionOut(
        id=version.id,
        name=version.name,
        version=version.version,
        status=version.status.value,
        description=version.description,
        published_at=version.published_at,
        source_commit=version.source_commit,
        created_at=version.created_at,
        case_count=case_count(db, version.id),
    )


def get_version(db: Session, version_id) -> BenchmarkVersion:
    version = db.get(BenchmarkVersion, version_id)
    if version is None:
        raise APIError(404, "not_found", "Benchmark version not found.")
    return version


def get_case(db: Session, case_id) -> BenchmarkCase:
    case = db.get(BenchmarkCase, case_id)
    if case is None:
        raise APIError(404, "not_found", "Benchmark case not found.")
    return case


def _judgments_for(db: Session, case_id) -> list[JudgmentOut]:
    rows = db.execute(
        select(
            RelevanceJudgment.chunk_id,
            RelevanceJudgment.relevance,
            RelevanceJudgment.rationale,
        ).where(RelevanceJudgment.benchmark_case_id == case_id)
    ).all()
    return [JudgmentOut(chunk_id=r[0], relevance=r[1], rationale=r[2]) for r in rows]


def case_out(db: Session, case: BenchmarkCase) -> CaseOut:
    return CaseOut(
        id=case.id,
        external_id=case.external_id,
        question=case.question,
        category=case.category,
        difficulty=case.difficulty.value,
        split=case.split.value,
        expected_answer=case.expected_answer,
        notes=case.notes,
        judgments=_judgments_for(db, case.id),
    )


def list_cases(db: Session, version_id) -> list[BenchmarkCase]:
    return list(
        db.scalars(
            select(BenchmarkCase)
            .where(BenchmarkCase.benchmark_version_id == version_id)
            .order_by(BenchmarkCase.external_id)
        )
    )


def _replace_judgments(db: Session, user: User, case_id, judgments: list[JudgmentIn]) -> None:
    db.execute(delete(RelevanceJudgment).where(RelevanceJudgment.benchmark_case_id == case_id))
    for judgment in judgments:
        if db.get(Chunk, judgment.chunk_id) is None:
            raise APIError(422, "invalid_judgment", f"Chunk {judgment.chunk_id} does not exist.")
        db.add(
            RelevanceJudgment(
                benchmark_case_id=case_id,
                chunk_id=judgment.chunk_id,
                relevance=judgment.relevance,
                rationale=judgment.rationale,
                judged_by=user.id,
            )
        )


def add_case(
    db: Session, user: User, version: BenchmarkVersion, case_in: BenchmarkCaseIn
) -> BenchmarkCase:
    _ensure_draft(version)
    _validate_enums(case_in.difficulty, case_in.split)
    duplicate = db.scalar(
        select(BenchmarkCase.id).where(
            BenchmarkCase.benchmark_version_id == version.id,
            BenchmarkCase.external_id == case_in.external_id,
        )
    )
    if duplicate is not None:
        raise APIError(409, "duplicate", f"Case '{case_in.external_id}' already exists.")

    case = BenchmarkCase(
        benchmark_version_id=version.id,
        external_id=case_in.external_id,
        question=case_in.question,
        category=case_in.category,
        difficulty=Difficulty(case_in.difficulty),
        split=DatasetSplit(case_in.split),
        expected_answer=case_in.expected_answer,
        notes=case_in.notes,
    )
    db.add(case)
    db.flush()
    _replace_judgments(db, user, case.id, case_in.judgments)
    db.commit()
    db.refresh(case)
    return case


def update_case(
    db: Session,
    user: User,
    version: BenchmarkVersion,
    case: BenchmarkCase,
    update: BenchmarkCaseUpdate,
) -> BenchmarkCase:
    _ensure_draft(version)
    if update.difficulty is not None:
        _validate_enums(update.difficulty, update.split or case.split.value)
        case.difficulty = Difficulty(update.difficulty)
    if update.split is not None:
        _validate_enums(update.difficulty or case.difficulty.value, update.split)
        case.split = DatasetSplit(update.split)
    if update.question is not None:
        case.question = update.question
    if update.category is not None:
        case.category = update.category
    if update.expected_answer is not None:
        case.expected_answer = update.expected_answer
    if update.notes is not None:
        case.notes = update.notes
    if update.judgments is not None:
        _replace_judgments(db, user, case.id, update.judgments)
    db.commit()
    db.refresh(case)
    return case


def delete_case(db: Session, version: BenchmarkVersion, case: BenchmarkCase) -> None:
    _ensure_draft(version)
    db.delete(case)
    db.commit()


def import_cases(
    db: Session, user: User, version: BenchmarkVersion, cases: list[BenchmarkCaseIn], replace: bool
) -> ImportResult:
    _ensure_draft(version)
    if replace:
        db.execute(delete(BenchmarkCase).where(BenchmarkCase.benchmark_version_id == version.id))
        db.flush()

    imported = 0
    judgment_count = 0
    for case_in in cases:
        _validate_enums(case_in.difficulty, case_in.split)
        case = BenchmarkCase(
            benchmark_version_id=version.id,
            external_id=case_in.external_id,
            question=case_in.question,
            category=case_in.category,
            difficulty=Difficulty(case_in.difficulty),
            split=DatasetSplit(case_in.split),
            expected_answer=case_in.expected_answer,
            notes=case_in.notes,
        )
        db.add(case)
        db.flush()
        _replace_judgments(db, user, case.id, case_in.judgments)
        imported += 1
        judgment_count += len(case_in.judgments)
    db.commit()
    return ImportResult(imported=imported, judgments=judgment_count)


def parse_jsonl(text: str) -> list[BenchmarkCaseIn]:
    cases: list[BenchmarkCaseIn] = []
    for line_number, raw in enumerate(io.StringIO(text), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            cases.append(BenchmarkCaseIn.model_validate(json.loads(line)))
        except Exception as exc:
            raise APIError(400, "malformed_jsonl", f"Line {line_number}: {exc}") from exc
    return cases


def export_jsonl(db: Session, version: BenchmarkVersion) -> str:
    lines = []
    for case in list_cases(db, version.id):
        judgments = _judgments_for(db, case.id)
        payload = {
            "external_id": case.external_id,
            "question": case.question,
            "category": case.category,
            "difficulty": case.difficulty.value,
            "split": case.split.value,
            "expected_answer": case.expected_answer,
            "notes": case.notes,
            "judgments": [
                {"chunk_id": str(j.chunk_id), "relevance": j.relevance, "rationale": j.rationale}
                for j in judgments
            ],
        }
        lines.append(json.dumps(payload))
    return "\n".join(lines) + ("\n" if lines else "")


def publish_version(
    db: Session, version: BenchmarkVersion, source_commit: str | None
) -> BenchmarkVersion:
    _ensure_draft(version)
    cases = list_cases(db, version.id)
    if len(cases) < MIN_CASES_FOR_PUBLISH:
        raise APIError(
            422, "incomplete", f"At least {MIN_CASES_FOR_PUBLISH} cases are required to publish."
        )
    for case in cases:
        relevances = list(
            db.scalars(
                select(RelevanceJudgment.relevance).where(
                    RelevanceJudgment.benchmark_case_id == case.id
                )
            )
        )
        if case.category == UNANSWERABLE_CATEGORY:
            if any(rel >= 1 for rel in relevances):
                raise APIError(
                    422,
                    "invalid_case",
                    f"Unanswerable case '{case.external_id}' has relevant judgments.",
                )
        elif not any(rel >= 2 for rel in relevances):
            raise APIError(
                422, "invalid_case", f"Case '{case.external_id}' needs a relevance 2 or 3 judgment."
            )

    version.status = BenchmarkStatus.published
    version.published_at = datetime.now(UTC)
    version.source_commit = source_commit
    db.commit()
    db.refresh(version)
    return version
