from __future__ import annotations

import stat
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from .models import FileIssue, LoadReport, SeriesData


SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}


class WorkbookReadError(RuntimeError):
    """Raised when a workbook cannot produce a valid two-column series."""


def _is_hidden(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    try:
        attributes = getattr(path.stat(), "st_file_attributes", 0)
        hidden_flag = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0)
        return bool(attributes & hidden_flag)
    except OSError:
        return False


def scan_excel_files(folder: Path | str) -> list[Path]:
    """Return supported, visible Excel files from the selected folder."""

    directory = Path(folder)
    if not directory.is_dir():
        raise NotADirectoryError(f"文件夹不存在：{directory}")

    files = [
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not path.name.startswith("~$")
        and not _is_hidden(path)
    ]
    return sorted(files, key=lambda path: path.name.casefold())


def _engine_hint(path: Path, error: ImportError) -> str:
    if path.suffix.lower() == ".xls":
        return "缺少读取 .xls 所需的 xlrd，请运行：pip install -r requirements.txt"
    return "缺少 Excel 读取组件，请运行：pip install -r requirements.txt"


def read_workbook(path: Path | str) -> SeriesData:
    """Read the first worksheet and validate its first two non-empty columns."""

    workbook = Path(path)
    try:
        raw = pd.read_excel(workbook, sheet_name=0, header=None)
    except ImportError as error:
        raise WorkbookReadError(_engine_hint(workbook, error)) from error
    except Exception as error:  # pandas exposes several engine-specific exceptions
        raise WorkbookReadError(f"无法读取工作簿：{error}") from error

    raw = raw.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if raw.empty:
        raise WorkbookReadError("工作表为空")
    if raw.shape[1] < 2:
        raise WorkbookReadError("有效列不足两列")

    frame = raw.iloc[:, :2].copy()
    first_pair = pd.to_numeric(frame.iloc[0], errors="coerce")
    rest = frame.iloc[1:]
    rest_x = pd.to_numeric(rest.iloc[:, 0], errors="coerce")
    rest_y = pd.to_numeric(rest.iloc[:, 1], errors="coerce")
    rest_has_pair = bool((rest_x.notna() & rest_y.notna()).any())
    header_detected = bool(first_pair.isna().any() and rest_has_pair)

    if header_detected:
        frame = frame.iloc[1:]

    numeric_x = pd.to_numeric(frame.iloc[:, 0], errors="coerce")
    numeric_y = pd.to_numeric(frame.iloc[:, 1], errors="coerce")
    finite = np.isfinite(numeric_x.to_numpy(dtype=float, na_value=np.nan)) & np.isfinite(
        numeric_y.to_numpy(dtype=float, na_value=np.nan)
    )
    valid_mask = numeric_x.notna().to_numpy() & numeric_y.notna().to_numpy() & finite
    skipped_rows = int(len(frame) - int(valid_mask.sum()))

    if not valid_mask.any():
        raise WorkbookReadError("前两列中没有有效的 x/y 数值对")

    warnings: list[str] = []
    if header_detected:
        warnings.append("已自动识别表头")
    if skipped_rows:
        warnings.append(f"跳过 {skipped_rows} 行无效数据")

    return SeriesData(
        name=workbook.stem,
        source=workbook,
        x=numeric_x.to_numpy(dtype=float)[valid_mask],
        y=numeric_y.to_numpy(dtype=float)[valid_mask],
        skipped_rows=skipped_rows,
        warnings=warnings,
    )


def _deduplicate_names(series_items: list[SeriesData]) -> None:
    totals = Counter(item.name.casefold() for item in series_items)
    seen: Counter[str] = Counter()
    for item in series_items:
        key = item.name.casefold()
        if totals[key] > 1:
            seen[key] += 1
            item.name = f"{item.name} ({seen[key]})"


def load_folder(folder: Path | str) -> LoadReport:
    """Load every supported workbook, collecting failures instead of stopping."""

    directory = Path(folder)
    files = scan_excel_files(directory)
    series_items: list[SeriesData] = []
    issues: list[FileIssue] = []

    for path in files:
        try:
            series_items.append(read_workbook(path))
        except WorkbookReadError as error:
            issues.append(FileIssue(source=path, reason=str(error)))

    _deduplicate_names(series_items)
    return LoadReport(
        folder=directory,
        scanned_files=files,
        series=series_items,
        issues=issues,
    )
