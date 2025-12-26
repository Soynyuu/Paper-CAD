import os
import shutil
import tempfile
import uuid
from typing import Optional, Union

from fastapi import HTTPException, UploadFile


async def save_upload_to_tmpdir(
    upload_file: UploadFile,
    suffix: str,
    chunk_size: int = 1024 * 1024,
) -> tuple[str, str, int]:
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, f"{uuid.uuid4()}.{suffix}")
    total = 0
    with open(path, "wb") as dst:
        while True:
            chunk = await upload_file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            dst.write(chunk)
    return tmpdir, path, total


def cleanup_temp_dir(tmpdir: Optional[str], label: str = "tmpdir") -> None:
    if tmpdir and os.path.exists(tmpdir):
        try:
            shutil.rmtree(tmpdir)
        except Exception as e:
            print(f"[CLEANUP] Failed to remove {label} {tmpdir}: {e}")


def parse_csv_ids(value: Optional[str]) -> Optional[list[str]]:
    if value and value.strip():
        parsed_ids = [item.strip() for item in value.split(",") if item.strip()]
        return parsed_ids or None
    return None


def normalize_limit_param(value: Union[int, str, None], param_name: str = "limit") -> Optional[int]:
    if value is None:
        return None

    if isinstance(value, str):
        if value.strip() == "" or value == "0":
            return None
        try:
            parsed = int(value)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"{param_name} must be a valid integer, got: {value}",
            )
        return parsed if parsed > 0 else None

    if isinstance(value, int):
        return value if value > 0 else None

    return None
