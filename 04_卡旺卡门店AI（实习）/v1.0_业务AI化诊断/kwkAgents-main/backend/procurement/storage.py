from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from backend.env import PROJECT_ROOT

PROCUREMENT_DIR = PROJECT_ROOT / "data" / "procurement"
MAX_XLSX_BYTES = 100 * 1024 * 1024


def create_storage_directory(category: str) -> Path:
    directory = PROCUREMENT_DIR / category / uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    return directory


async def save_xlsx_upload(upload: UploadFile, directory: Path, filename: str = "source.xlsx") -> tuple[Path, str]:
    original_name = Path(upload.filename or "").name
    if not original_name.lower().endswith(".xlsx"):
        raise ValueError("仅支持 .xlsx 文件")

    temporary_path = directory / f".{filename}.uploading"
    final_path = directory / filename
    digest = hashlib.sha256()
    size = 0
    try:
        with temporary_path.open("wb") as output:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_XLSX_BYTES:
                    raise ValueError("Excel 文件不能超过 100 MB")
                digest.update(chunk)
                output.write(chunk)
        if size < 4:
            raise ValueError("Excel 文件为空或已损坏")
        with temporary_path.open("rb") as source:
            if source.read(2) != b"PK":
                raise ValueError("上传内容不是有效的 .xlsx 文件")
        os.replace(temporary_path, final_path)
        return final_path, digest.hexdigest()
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def remove_storage_directory(directory: Path) -> None:
    shutil.rmtree(directory, ignore_errors=True)
