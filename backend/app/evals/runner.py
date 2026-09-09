"""Evaluation runner.

Executes a queued eval run over a published benchmark: for every case it runs retrieval,
maps retrieved chunks to graded relevance, computes deterministic metrics, stores per-case
rows, and aggregates run-level metrics. Aggregate Hit/Recall/MRR/nDCG are averaged over
answerable cases only (cases with at least one relevant judgment).
"""

import hashlib
import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import APIError
from app.db.models.benchmark import (
    BenchmarkVersion,
    EvalResult,
    EvalRun,
    RelevanceJudgment,
)
from app.db.models.document import Chunk
from app.db.models.enums import BenchmarkStatus, EvalStatus, RetrievalMode
from app.db.models.user import User
from app.evals import metrics as metric_fns
from app.retrieval.pipeline import run_retrieval
from app.services import benchmark as benchmark_service

_ACTIVE_EVAL_STATUSES = (EvalStatus.queued, EvalStatus.running)


def corpus_fingerprint(db: Session) -> str:
    digest = hashlib.sha256()
    for checksum in db.scalars(select(Chunk.checksum).order_by(Chunk.checksum)):
        digest.update(checksum.encode("utf-8"))
    return digest.hexdigest()


def create_run(db: Session, settings: Settings, user: User, payload) -> EvalRun:
    version = db.get(BenchmarkVersion, payload.benchmark_version_id)
    if version is None:
        raise APIError(404, "not_found", "Benchmark version not found.")
    if version.status != BenchmarkStatus.published:
        raise APIError(
            409, "benchmark_not_published", "Only published benchmarks can be evaluated."
        )

    mode = payload.retrieval_mode
    if payload.reranker_enabled and mode == "hybrid":
        mode = "reranked_hybrid"
    if mode not in {m.value for m in RetrievalMode}:
        raise APIError(422, "invalid_mode", "Unknown retrieval mode.")

    duplicate = db.scalar(
        select(EvalRun.id).where(
            EvalRun.benchmark_version_id == version.id,
            EvalRun.retrieval_mode == RetrievalMode(mode),
            EvalRun.status.in_(_ACTIVE_EVAL_STATUSES),
        )
    )
    if duplicate is not None:
        raise APIError(
            409, "duplicate_active_run", "An identical run is already queued or running."
        )

    run = EvalRun(
        benchmark_version_id=version.id,
        created_by=user.id,
        status=EvalStatus.queued,
        retrieval_mode=RetrievalMode(mode),
        top_k=payload.top_k,
        candidate_k=payload.candidate_k,
        rrf_k=payload.rrf_k,
        reranker_model=settings.reranker_model if mode == "reranked_hybrid" else None,
        embedding_model=settings.openai_embedding_model,
        corpus_fingerprint=corpus_fingerprint(db),
        config={
            "retrieval_mode": mode,
            "top_k": payload.top_k,
            "candidate_k": payload.candidate_k,
            "rrf_k": payload.rrf_k,
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def claim_queued_run(db: Session) -> EvalRun | None:
    run = db.scalar(
        select(EvalRun)
        .where(EvalRun.status == EvalStatus.queued)
        .order_by(EvalRun.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if run is None:
        return None
    run.status = EvalStatus.running
    run.started_at = datetime.now(UTC)
    db.commit()
    return run


def _percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(pct * (len(ordered) - 1))))
    return float(ordered[index])


def execute_run(
    db: Session, settings: Settings, run: EvalRun, embedder, vector_store, reranker
) -> None:
    if run.status != EvalStatus.running:
        run.status = EvalStatus.running
        run.started_at = datetime.now(UTC)
        db.flush()

    user = db.get(User, run.created_by)  # admin -> retrieval sees the whole corpus
    cases = benchmark_service.list_cases(db, run.benchmark_version_id)
    mode = run.retrieval_mode.value

    hits: list[float] = []
    recalls: list[float] = []
    rrs: list[float] = []
    ndcgs: list[float] = []
    latencies: list[int] = []
    per_category: dict[str, list[float]] = {}
    errored = 0

    try:
        db.execute(EvalResult.__table__.delete().where(EvalResult.eval_run_id == run.id))
        for case in cases:
            judgments = {
                chunk_id: rel
                for chunk_id, rel in db.execute(
                    select(RelevanceJudgment.chunk_id, RelevanceJudgment.relevance).where(
                        RelevanceJudgment.benchmark_case_id == case.id
                    )
                ).all()
            }
            ideal = list(judgments.values())
            total_relevant = sum(1 for rel in ideal if rel >= 1)

            started = time.perf_counter()
            try:
                outcome = run_retrieval(
                    db,
                    user,
                    case.question,
                    mode,
                    run.top_k,
                    embedder=embedder,
                    vector_store=vector_store,
                    reranker=reranker,
                )
            except Exception as exc:  # noqa: BLE001 - record per-case failure, keep going
                errored += 1
                db.add(
                    EvalResult(
                        eval_run_id=run.id,
                        benchmark_case_id=case.id,
                        error_code="retrieval_error",
                        trace={"error": str(exc)[:500]},
                    )
                )
                continue
            latency_ms = int((time.perf_counter() - started) * 1000)

            ranked_ids = [c.chunk_id for c in outcome.candidates]
            ranked_rel = [judgments.get(cid, 0) for cid in ranked_ids]

            hit = metric_fns.hit_at_k(ranked_rel, 5)
            recall = metric_fns.recall_at_k(ranked_rel, total_relevant, 5)
            rr = metric_fns.reciprocal_rank(ranked_rel, 10)
            ndcg = metric_fns.ndcg_at_k(ranked_rel, ideal, 10)

            db.add(
                EvalResult(
                    eval_run_id=run.id,
                    benchmark_case_id=case.id,
                    ranked_chunk_ids=ranked_ids,
                    ranked_relevances=ranked_rel,
                    hit_at_5=hit,
                    recall_at_5=recall,
                    reciprocal_rank=rr,
                    ndcg_at_10=ndcg,
                    latency_ms=latency_ms,
                )
            )
            latencies.append(latency_ms)
            if total_relevant > 0:  # aggregate ranking metrics over answerable cases only
                hits.append(hit)
                recalls.append(recall)
                rrs.append(rr)
                ndcgs.append(ndcg)
                per_category.setdefault(case.category, []).append(ndcg)

        def mean(values: list[float]) -> float:
            return round(sum(values) / len(values), 4) if values else 0.0

        run.metrics = {
            "hit_at_5": mean(hits),
            "recall_at_5": mean(recalls),
            "mrr_at_10": mean(rrs),
            "ndcg_at_10": mean(ndcgs),
            "p95_latency_ms": _percentile(latencies, 0.95),
            "case_count": len(cases),
            "answerable_case_count": len(hits),
            "errored_case_count": errored,
            "ndcg_by_category": {cat: mean(vals) for cat, vals in per_category.items()},
        }
        run.status = EvalStatus.succeeded
        run.error_code = None
        run.finished_at = datetime.now(UTC)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        failed = db.get(EvalRun, run.id)
        if failed is not None:
            failed.status = EvalStatus.failed
            failed.error_code = "eval_failed"
            failed.finished_at = datetime.now(UTC)
            db.commit()
        raise exc


_METRIC_KEYS = ("hit_at_5", "recall_at_5", "mrr_at_10", "ndcg_at_10", "p95_latency_ms")


def compare_runs(left: EvalRun, right: EvalRun) -> tuple[bool, dict[str, float]]:
    equivalent = (
        left.benchmark_version_id == right.benchmark_version_id
        and left.corpus_fingerprint == right.corpus_fingerprint
    )
    left_metrics = left.metrics or {}
    right_metrics = right.metrics or {}
    deltas = {
        key: round(float(right_metrics.get(key, 0.0)) - float(left_metrics.get(key, 0.0)), 4)
        for key in _METRIC_KEYS
    }
    return equivalent, deltas
