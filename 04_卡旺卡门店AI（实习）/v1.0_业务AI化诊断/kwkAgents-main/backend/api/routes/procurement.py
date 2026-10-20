from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.db.models import QuoteComparison, StandardListVersion, User
from backend.env import PROJECT_ROOT
from backend.infra.auth import get_current_user, get_db, require_admin
from backend.procurement import (
    compare_quote_workbook,
    create_standard_snapshot,
    write_comparison_report,
)
from backend.procurement.excel_compare import WorkbookValidationError
from backend.procurement.storage import (
    create_storage_directory,
    remove_storage_directory,
    save_xlsx_upload,
)
from backend.schemas.procurement import (
    ComparisonSummary,
    QuoteComparisonListItem,
    QuoteComparisonResponse,
    StandardListVersionResponse,
)

router = APIRouter(prefix="/procurement", tags=["procurement"])


def _relative_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def _stored_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if PROJECT_ROOT.resolve() not in path.parents:
        raise HTTPException(status_code=500, detail="采购文件存储路径无效")
    return path


def _standard_response(record: StandardListVersion) -> StandardListVersionResponse:
    return StandardListVersionResponse(
        id=record.id,
        version_name=record.version_name,
        original_filename=record.original_filename,
        file_hash=record.file_hash,
        item_count=len((record.snapshot_json or {}).get("items", [])),
        created_at=record.created_at,
    )


def _comparison_list_response(
    record: QuoteComparison,
    standard: StandardListVersion,
) -> QuoteComparisonListItem:
    return QuoteComparisonListItem(
        id=record.id,
        standard_version_id=record.standard_version_id,
        standard_version_name=standard.version_name,
        original_filename=record.original_filename,
        summary=ComparisonSummary(**(record.summary_json or {})),
        created_at=record.created_at,
    )


def _comparison_response(
    record: QuoteComparison,
    standard: StandardListVersion,
) -> QuoteComparisonResponse:
    payload = _comparison_list_response(record, standard).model_dump()
    payload["items"] = (record.result_json or {}).get("items", [])
    return QuoteComparisonResponse(**payload)


def _get_accessible_comparison(
    comparison_id: int,
    current_user: User,
    db: Session,
) -> QuoteComparison:
    record = db.query(QuoteComparison).filter(QuoteComparison.id == comparison_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="报价对比记录不存在")
    if current_user.role != "admin" and record.uploaded_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该报价对比记录")
    return record


@router.get("/standards", response_model=list[StandardListVersionResponse])
async def list_standard_versions(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = db.query(StandardListVersion).order_by(StandardListVersion.created_at.desc()).all()
    return [_standard_response(record) for record in records]


@router.post("/standards", response_model=StandardListVersionResponse)
async def create_standard_version(
    version_name: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    normalized_name = version_name.strip()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="标准清单版本名称不能为空")
    if len(normalized_name) > 120:
        raise HTTPException(status_code=400, detail="标准清单版本名称不能超过 120 个字符")

    directory = create_storage_directory("standards")
    try:
        source_path, file_hash = await save_xlsx_upload(file, directory)
        snapshot = await run_in_threadpool(create_standard_snapshot, source_path)
        record = StandardListVersion(
            version_name=normalized_name,
            original_filename=Path(file.filename or "source.xlsx").name,
            file_path=_relative_path(source_path),
            file_hash=file_hash,
            snapshot_json=snapshot,
            uploaded_by_id=current_user.id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return _standard_response(record)
    except IntegrityError:
        db.rollback()
        remove_storage_directory(directory)
        raise HTTPException(status_code=409, detail="标准清单版本名称已存在")
    except (ValueError, WorkbookValidationError) as exc:
        db.rollback()
        remove_storage_directory(directory)
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        db.rollback()
        remove_storage_directory(directory)
        raise
    except Exception as exc:
        db.rollback()
        remove_storage_directory(directory)
        raise HTTPException(status_code=500, detail=f"创建标准清单版本失败：{exc}")


@router.get("/comparisons", response_model=list[QuoteComparisonListItem])
async def list_quote_comparisons(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(QuoteComparison)
    if current_user.role != "admin":
        query = query.filter(QuoteComparison.uploaded_by_id == current_user.id)
    records = query.order_by(QuoteComparison.created_at.desc()).all()
    standards = {
        standard.id: standard
        for standard in db.query(StandardListVersion).filter(
            StandardListVersion.id.in_({record.standard_version_id for record in records})
        ).all()
    } if records else {}
    return [
        _comparison_list_response(record, standards[record.standard_version_id])
        for record in records
        if record.standard_version_id in standards
    ]


@router.post("/comparisons", response_model=QuoteComparisonResponse)
async def create_quote_comparison(
    standard_version_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    standard = db.query(StandardListVersion).filter(StandardListVersion.id == standard_version_id).first()
    if not standard:
        raise HTTPException(status_code=404, detail="所选标准清单版本不存在")

    directory = create_storage_directory("comparisons")
    try:
        source_path, _ = await save_xlsx_upload(file, directory)
        result = await run_in_threadpool(compare_quote_workbook, source_path, standard.snapshot_json)
        report_path = directory / "report.xlsx"
        await run_in_threadpool(write_comparison_report, result, report_path)
        record = QuoteComparison(
            standard_version_id=standard.id,
            original_filename=Path(file.filename or "source.xlsx").name,
            source_path=_relative_path(source_path),
            report_path=_relative_path(report_path),
            result_json={"format_version": result["format_version"], "items": result["items"]},
            summary_json=result["summary"],
            uploaded_by_id=current_user.id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return _comparison_response(record, standard)
    except (ValueError, WorkbookValidationError) as exc:
        db.rollback()
        remove_storage_directory(directory)
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        db.rollback()
        remove_storage_directory(directory)
        raise
    except Exception as exc:
        db.rollback()
        remove_storage_directory(directory)
        raise HTTPException(status_code=500, detail=f"生成报价对比失败：{exc}")


@router.get("/comparisons/{comparison_id}", response_model=QuoteComparisonResponse)
async def get_quote_comparison(
    comparison_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = _get_accessible_comparison(comparison_id, current_user, db)
    standard = db.query(StandardListVersion).filter(StandardListVersion.id == record.standard_version_id).first()
    if not standard:
        raise HTTPException(status_code=500, detail="报价对比关联的标准清单版本不存在")
    return _comparison_response(record, standard)


@router.get("/comparisons/{comparison_id}/report")
async def download_quote_comparison_report(
    comparison_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = _get_accessible_comparison(comparison_id, current_user, db)
    report_path = _stored_path(record.report_path)
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="报价对比报告文件不存在")
    filename = f"报价对比报告-{record.id}.xlsx"
    return FileResponse(
        path=report_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
