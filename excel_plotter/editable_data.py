from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .models import LoadReport


@dataclass(frozen=True, slots=True)
class EditableRow:
    series_index: int
    row_index: int
    series_name: str
    source_name: str
    x: float
    y: float


class EditableDataModel:
    """Editable long-table view backed directly by a LoadReport."""

    def __init__(self, report: LoadReport) -> None:
        self.report = report
        self.revision = 0

    def rows(self, series_name: str | None = None) -> list[EditableRow]:
        output: list[EditableRow] = []
        for series_index, series in enumerate(self.report.series):
            if series_name is not None and series.name != series_name:
                continue
            for row_index, (x_value, y_value) in enumerate(zip(series.x, series.y, strict=True)):
                output.append(
                    EditableRow(
                        series_index=series_index,
                        row_index=row_index,
                        series_name=series.name,
                        source_name=series.source.name,
                        x=float(x_value),
                        y=float(y_value),
                    )
                )
        return output

    @property
    def series_names(self) -> list[str]:
        return [series.name for series in self.report.series]

    @property
    def total_points(self) -> int:
        return sum(series.valid_count for series in self.report.series)

    def edit_number(self, series_index: int, row_index: int, field: str, value: object) -> None:
        if field not in {"x", "y"}:
            raise ValueError("只能编辑 X 或 Y 数值")
        try:
            number = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError("请输入有效数值") from error
        if not np.isfinite(number):
            raise ValueError("数值必须是有限数字")

        series = self._series(series_index)
        self._validate_row_index(series_index, row_index)
        target = series.x if field == "x" else series.y
        target[row_index] = number
        self.revision += 1

    def rename_series(self, series_index: int, name: str) -> None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("系列名称不能为空")
        if len(cleaned) > 120:
            raise ValueError("系列名称不能超过 120 个字符")
        duplicate = any(
            index != series_index and series.name.casefold() == cleaned.casefold()
            for index, series in enumerate(self.report.series)
        )
        if duplicate:
            raise ValueError(f"系列名称“{cleaned}”已经存在")
        self._series(series_index).name = cleaned
        self.revision += 1

    def delete_row(self, series_index: int, row_index: int) -> None:
        series = self._series(series_index)
        self._validate_row_index(series_index, row_index)
        if series.valid_count <= 1:
            raise ValueError("每个数据系列至少需要保留一个数据点")
        series.x = np.delete(series.x, row_index)
        series.y = np.delete(series.y, row_index)
        self.revision += 1

    def add_row(self, series_index: int, x_value: object, y_value: object) -> None:
        x_number = self._finite_number(x_value, "X")
        y_number = self._finite_number(y_value, "Y")
        series = self._series(series_index)
        series.x = np.append(series.x, x_number)
        series.y = np.append(series.y, y_number)
        self.revision += 1

    def to_dataframe(self) -> pd.DataFrame:
        records = [
            {
                "数据系列": row.series_name,
                "源文件": row.source_name,
                "系列内行号": row.row_index + 1,
                "X": row.x,
                "Y": row.y,
            }
            for row in self.rows()
        ]
        return pd.DataFrame.from_records(
            records,
            columns=["数据系列", "源文件", "系列内行号", "X", "Y"],
        )

    def _series(self, series_index: int):
        try:
            return self.report.series[series_index]
        except IndexError as error:
            raise ValueError("数据系列不存在") from error

    def _validate_row_index(self, series_index: int, row_index: int) -> None:
        series = self._series(series_index)
        if not 0 <= row_index < series.valid_count:
            raise ValueError("数据行不存在")

    @staticmethod
    def _finite_number(value: object, label: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{label} 必须是有效数值") from error
        if not np.isfinite(number):
            raise ValueError(f"{label} 必须是有限数字")
        return number
