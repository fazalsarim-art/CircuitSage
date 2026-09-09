"""Benchmark authoring endpoints (§8.14)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AdminUser, CurrentUser
from app.core.errors import APIError
from app.db.models.benchmark import BenchmarkVersion
from app.db.session import get_db
from app.schemas.benchmark import (
    BenchmarkCaseIn,
    BenchmarkCaseUpdate,
    CaseListResponse,
    CaseOut,
    ImportResult,
    PublishRequest,
    VersionCreate,
    VersionListResponse,
    VersionOut,
)
from app.services import benchmark as bench

router = APIRouter(prefix="/benchmark", tags=["benchmark"])

DbDep = Annotated[Session, Depends(get_db)]


@router.get("/versions", response_model=VersionListResponse)
def list_versions(user: CurrentUser, db: DbDep) -> VersionListResponse:
    versions = db.scalars(select(BenchmarkVersion).order_by(BenchmarkVersion.created_at.desc()))
    return VersionListResponse(items=[bench.version_out(db, v) for v in versions])


@router.post("/versions", status_code=201, response_model=VersionOut)
def create_version(payload: VersionCreate, admin: AdminUser, db: DbDep) -> VersionOut:
    version = bench.create_version(db, admin, payload.name, payload.description)
    return bench.version_out(db, version)


@router.get("/versions/{version_id}/cases", response_model=CaseListResponse)
def list_cases(version_id: uuid.UUID, user: CurrentUser, db: DbDep) -> CaseListResponse:
    bench.get_version(db, version_id)
    cases = bench.list_cases(db, version_id)
    return CaseListResponse(items=[bench.case_out(db, c) for c in cases])


@router.post("/versions/{version_id}/cases", status_code=201, response_model=CaseOut)
def create_case(
    version_id: uuid.UUID, payload: BenchmarkCaseIn, admin: AdminUser, db: DbDep
) -> CaseOut:
    version = bench.get_version(db, version_id)
    case = bench.add_case(db, admin, version, payload)
    return bench.case_out(db, case)


@router.patch("/cases/{case_id}", response_model=CaseOut)
def update_case(
    case_id: uuid.UUID, payload: BenchmarkCaseUpdate, admin: AdminUser, db: DbDep
) -> CaseOut:
    case = bench.get_case(db, case_id)
    version = bench.get_version(db, case.benchmark_version_id)
    updated = bench.update_case(db, admin, version, case, payload)
    return bench.case_out(db, updated)


@router.delete("/cases/{case_id}", status_code=204)
def delete_case(case_id: uuid.UUID, admin: AdminUser, db: DbDep):
    case = bench.get_case(db, case_id)
    version = bench.get_version(db, case.benchmark_version_id)
    bench.delete_case(db, version, case)


@router.post("/versions/{version_id}/import", response_model=ImportResult)
async def import_cases(
    version_id: uuid.UUID,
    admin: AdminUser,
    db: DbDep,
    file: UploadFile,
    replace: Annotated[bool, Form()] = False,
) -> ImportResult:
    version = bench.get_version(db, version_id)
    text = (await file.read()).decode("utf-8")
    cases = bench.parse_jsonl(text)
    return bench.import_cases(db, admin, version, cases, replace)


@router.get("/versions/{version_id}/export", response_class=PlainTextResponse)
def export_cases(version_id: uuid.UUID, admin: AdminUser, db: DbDep) -> PlainTextResponse:
    version = bench.get_version(db, version_id)
    return PlainTextResponse(bench.export_jsonl(db, version), media_type="application/x-ndjson")


@router.post("/versions/{version_id}/publish", response_model=VersionOut)
def publish_version(
    version_id: uuid.UUID,
    payload: PublishRequest,
    admin: AdminUser,
    db: DbDep,
) -> VersionOut:
    version = bench.get_version(db, version_id)
    if payload.confirmation != version.name:
        raise APIError(422, "confirmation_mismatch", "Confirmation must equal the benchmark name.")
    published = bench.publish_version(db, version, payload.source_commit)
    return bench.version_out(db, published)
