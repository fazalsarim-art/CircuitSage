"""Evaluation run endpoints (§8.15)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AdminUser, CurrentUser
from app.core.config import Settings, get_settings
from app.core.errors import APIError
from app.db.models.benchmark import EvalResult, EvalRun
from app.db.models.enums import EvalStatus
from app.db.session import get_db
from app.evals import runner
from app.schemas.evals import (
    CompareResponse,
    EvalCaseResultOut,
    EvalRunCreate,
    EvalRunDetail,
    EvalRunListResponse,
    EvalRunOut,
)

router = APIRouter(prefix="/evals", tags=["evals"])

DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

_TERMINAL = (EvalStatus.succeeded, EvalStatus.failed, EvalStatus.cancelled)


def _run_out(run: EvalRun) -> EvalRunOut:
    return EvalRunOut(
        id=run.id,
        benchmark_version_id=run.benchmark_version_id,
        status=run.status.value,
        retrieval_mode=run.retrieval_mode.value,
        top_k=run.top_k,
        candidate_k=run.candidate_k,
        rrf_k=run.rrf_k,
        reranker_model=run.reranker_model,
        embedding_model=run.embedding_model,
        corpus_fingerprint=run.corpus_fingerprint,
        metrics=run.metrics,
        error_code=run.error_code,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.post("/runs", status_code=202, response_model=EvalRunOut)
def create_run(
    payload: EvalRunCreate, admin: AdminUser, db: DbDep, settings: SettingsDep
) -> EvalRunOut:
    run = runner.create_run(db, settings, admin, payload)
    return _run_out(run)


@router.get("/runs", response_model=EvalRunListResponse)
def list_runs(
    user: CurrentUser,
    db: DbDep,
    benchmark_version_id: uuid.UUID | None = None,
    status: str | None = None,
) -> EvalRunListResponse:
    stmt = select(EvalRun).order_by(EvalRun.created_at.desc())
    if benchmark_version_id:
        stmt = stmt.where(EvalRun.benchmark_version_id == benchmark_version_id)
    if status:
        try:
            stmt = stmt.where(EvalRun.status == EvalStatus(status))
        except ValueError as exc:
            raise APIError(422, "invalid_status", "Unknown eval status.") from exc
    return EvalRunListResponse(items=[_run_out(r) for r in db.scalars(stmt)])


def _get_run(db: Session, run_id: uuid.UUID) -> EvalRun:
    run = db.get(EvalRun, run_id)
    if run is None:
        raise APIError(404, "not_found", "Evaluation run not found.")
    return run


@router.get("/runs/compare", response_model=CompareResponse)
def compare_runs(
    left_id: uuid.UUID, right_id: uuid.UUID, user: CurrentUser, db: DbDep
) -> CompareResponse:
    left = _get_run(db, left_id)
    right = _get_run(db, right_id)
    if left.benchmark_version_id != right.benchmark_version_id:
        raise APIError(400, "incomparable_benchmark", "Runs use different benchmark versions.")
    equivalent, deltas = runner.compare_runs(left, right)
    return CompareResponse(
        left=_run_out(left), right=_run_out(right), equivalent=equivalent, metric_deltas=deltas
    )


@router.get("/runs/{run_id}", response_model=EvalRunDetail)
def get_run(run_id: uuid.UUID, user: CurrentUser, db: DbDep) -> EvalRunDetail:
    run = _get_run(db, run_id)
    results = db.scalars(
        select(EvalResult).where(EvalResult.eval_run_id == run.id).order_by(EvalResult.created_at)
    )
    return EvalRunDetail(
        run=_run_out(run),
        results=[
            EvalCaseResultOut(
                benchmark_case_id=r.benchmark_case_id,
                hit_at_5=r.hit_at_5,
                recall_at_5=r.recall_at_5,
                reciprocal_rank=r.reciprocal_rank,
                ndcg_at_10=r.ndcg_at_10,
                latency_ms=r.latency_ms,
                error_code=r.error_code,
            )
            for r in results
        ],
    )


@router.post("/runs/{run_id}/cancel", status_code=202, response_model=EvalRunOut)
def cancel_run(run_id: uuid.UUID, admin: AdminUser, db: DbDep) -> EvalRunOut:
    run = _get_run(db, run_id)
    if run.status in _TERMINAL:
        raise APIError(409, "terminal_run", "Run has already finished.")
    run.status = EvalStatus.cancelled
    db.commit()
    db.refresh(run)
    return _run_out(run)


@router.get("/runs/{run_id}/export")
def export_run(run_id: uuid.UUID, user: CurrentUser, db: DbDep) -> dict:
    run = _get_run(db, run_id)
    if run.status != EvalStatus.succeeded:
        raise APIError(409, "run_incomplete", "Only succeeded runs can be exported.")
    results = db.scalars(select(EvalResult).where(EvalResult.eval_run_id == run.id))
    return {
        "run": _run_out(run).model_dump(mode="json"),
        "results": [
            {
                "benchmark_case_id": str(r.benchmark_case_id),
                "hit_at_5": r.hit_at_5,
                "recall_at_5": r.recall_at_5,
                "reciprocal_rank": r.reciprocal_rank,
                "ndcg_at_10": r.ndcg_at_10,
                "latency_ms": r.latency_ms,
                "error_code": r.error_code,
            }
            for r in results
        ],
    }
