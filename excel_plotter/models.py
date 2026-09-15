from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np


PlotType = Literal["scatter", "line"]

MARKER_OPTIONS: tuple[tuple[str, str], ...] = (
    ("o", "圆形"),
    ("s", "方形"),
    ("^", "上三角"),
    ("D", "菱形"),
    ("v", "下三角"),
    ("P", "加号"),
    ("X", "叉号"),
    ("<", "左三角"),
    (">", "右三角"),
    ("h", "六边形"),
    ("*", "星形"),
    ("p", "五边形"),
)
DEFAULT_MARKERS: tuple[str, ...] = tuple(code for code, _label in MARKER_OPTIONS)


@dataclass(frozen=True, slots=True)
class PlotStyleConfig:
    """User-adjustable publication figure parameters."""

    width_cm: float = 12.0
    height_cm: float = 10.0
    dpi: int = 300
    title_font_size: float = 10.5
    axis_font_size: float = 9.0
    tick_font_size: float = 9.0
    legend_font_size: float = 9.0
    marker_size: float = 4.0
    data_line_width: float = 1.0
    axis_line_width: float = 0.85
    major_grid_width: float = 0.65
    minor_grid_width: float = 0.35
    minor_divisions: int = 2
    minor_tick_length: float = 2.2
    show_minor_grid: bool = True
    show_title: bool = True
    use_color: bool = True
    markers: tuple[str, ...] = DEFAULT_MARKERS

    def __post_init__(self) -> None:
        ranges: tuple[tuple[str, float, float, float], ...] = (
            ("图像宽度", self.width_cm, 3.0, 60.0),
            ("图像高度", self.height_cm, 3.0, 45.0),
            ("DPI", float(self.dpi), 100.0, 1200.0),
            ("标题字号", self.title_font_size, 6.0, 36.0),
            ("坐标轴标题字号", self.axis_font_size, 6.0, 30.0),
            ("刻度字号", self.tick_font_size, 5.0, 24.0),
            ("图例字号", self.legend_font_size, 5.0, 24.0),
            ("数据点大小", self.marker_size, 1.0, 20.0),
            ("数据线宽", self.data_line_width, 0.2, 5.0),
            ("坐标框线宽", self.axis_line_width, 0.2, 3.0),
            ("主网格线宽", self.major_grid_width, 0.1, 3.0),
            ("次网格线宽", self.minor_grid_width, 0.1, 2.0),
            ("次刻度长度", self.minor_tick_length, 0.5, 10.0),
        )
        for label, value, minimum, maximum in ranges:
            if not minimum <= value <= maximum:
                raise ValueError(f"{label}应在 {minimum:g}–{maximum:g} 之间")
        if not 2 <= self.minor_divisions <= 10:
            raise ValueError("次刻度分段数应在 2–10 之间")
        marker_codes = tuple(self.markers)
        available = set(DEFAULT_MARKERS)
        if not marker_codes:
            raise ValueError("数据点形状库至少需要保留一种形状")
        if len(set(marker_codes)) != len(marker_codes):
            raise ValueError("数据点形状库中不能包含重复形状")
        invalid = [marker for marker in marker_codes if marker not in available]
        if invalid:
            raise ValueError("数据点形状库包含不支持的形状：" + "、".join(invalid))
        object.__setattr__(self, "markers", marker_codes)


@dataclass(slots=True)
class SeriesData:
    """A validated x/y data series loaded from one workbook."""

    name: str
    source: Path
    x: np.ndarray
    y: np.ndarray
    skipped_rows: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def valid_count(self) -> int:
        return int(self.x.size)


@dataclass(slots=True)
class FileIssue:
    source: Path
    reason: str


@dataclass(slots=True)
class LoadReport:
    folder: Path
    scanned_files: list[Path]
    series: list[SeriesData]
    issues: list[FileIssue]

    @property
    def valid_file_count(self) -> int:
        return len(self.series)

    @property
    def total_points(self) -> int:
        return sum(item.valid_count for item in self.series)


@dataclass(frozen=True, slots=True)
class PlotConfig:
    title: str
    x_label: str
    y_label: str
    plot_type: PlotType
    style: PlotStyleConfig = field(default_factory=PlotStyleConfig)

    @property
    def dpi(self) -> int:
        return self.style.dpi
