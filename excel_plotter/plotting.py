from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

import matplotlib as mpl
import numpy as np
from matplotlib import font_manager
from matplotlib.figure import Figure
from matplotlib.ticker import AutoMinorLocator, MaxNLocator

from .models import PlotConfig, SeriesData


COLORS = (
    "#2357A5",
    "#D55238",
    "#2A8C78",
    "#8A5CB5",
    "#D99A2B",
    "#397FB3",
    "#B84272",
    "#6C7A3D",
    "#C5682C",
    "#4D6478",
    "#9B4F45",
    "#527F86",
)
MONOCHROME_LINE_STYLES = ("-", "--", "-.", ":")


class FontConfigurationError(RuntimeError):
    pass


def configure_plot_fonts() -> None:
    """Configure glyph-level fallback: Latin first, then Simplified Chinese."""

    missing: list[str] = []
    for family in ("Times New Roman", "SimHei"):
        try:
            font_manager.findfont(family, fallback_to_default=False)
        except ValueError:
            missing.append(family)
    allow_fallback = os.getenv("PLOTLAB_ALLOW_FONT_FALLBACK") == "1"
    if missing and not allow_fallback:
        raise FontConfigurationError(
            "系统缺少出图字体：" + "、".join(missing) + "。请安装字体后重试。"
        )

    mpl.rcParams["font.family"] = ["Times New Roman", "SimHei"]
    mpl.rcParams["axes.unicode_minus"] = False
    mpl.rcParams["svg.fonttype"] = "none"


def _academic_ticks(values: np.ndarray, nbins: int) -> np.ndarray:
    """Return publication-style ticks whose first/last values are the axis ends."""

    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        raise ValueError("数据中没有有限数值")

    data_min = float(finite.min())
    data_max = float(finite.max())
    if np.isclose(data_min, data_max):
        padding = max(abs(data_min) * 0.08, 1.0)
        data_min -= padding
        data_max += padding

    span = data_max - data_min
    padded_min = data_min - span * 0.025
    padded_max = data_max + span * 0.025

    # Include a meaningful zero baseline without compressing tightly clustered data.
    if data_min >= 0 and data_min <= span * 0.18:
        padded_min = 0.0
    if data_max <= 0 and abs(data_max) <= span * 0.18:
        padded_max = 0.0

    locator = MaxNLocator(
        nbins=nbins,
        steps=[1, 2, 2.5, 5, 10],
        min_n_ticks=4,
    )
    ticks = locator.tick_values(padded_min, padded_max)
    return np.asarray(ticks, dtype=float)


def _apply_academic_axes(
    axes: object,
    series_items: list[SeriesData],
    minor_divisions: int,
) -> None:
    x_values = np.concatenate([item.x for item in series_items])
    y_values = np.concatenate([item.y for item in series_items])
    x_ticks = _academic_ticks(x_values, nbins=8)
    y_ticks = _academic_ticks(y_values, nbins=7)

    axes.set_xlim(float(x_ticks[0]), float(x_ticks[-1]))
    axes.set_ylim(float(y_ticks[0]), float(y_ticks[-1]))
    axes.set_xticks(x_ticks)
    axes.set_yticks(y_ticks)
    axes.xaxis.set_minor_locator(AutoMinorLocator(minor_divisions))
    axes.yaxis.set_minor_locator(AutoMinorLocator(minor_divisions))


def build_figure(config: PlotConfig, series_items: list[SeriesData]) -> Figure:
    if not series_items:
        raise ValueError("没有可绘制的数据系列")
    if config.plot_type not in {"scatter", "line"}:
        raise ValueError(f"不支持的图表类型：{config.plot_type}")

    configure_plot_fonts()
    style = config.style
    # Snap physical dimensions to the nearest output pixel so 5.3 cm at
    # 300 DPI becomes exactly 626 px instead of being truncated to 625 px.
    width_pixels = round(style.width_cm / 2.54 * style.dpi)
    height_pixels = round(style.height_cm / 2.54 * style.dpi)
    # A hundredth of a pixel prevents the raster backend from truncating an
    # exact integer target because of binary floating-point representation.
    width_inches = (width_pixels + 0.01) / style.dpi
    height_inches = (height_pixels + 0.01) / style.dpi
    figure = Figure(
        figsize=(width_inches, height_inches),
        facecolor="white",
        constrained_layout=False,
    )
    axes = figure.add_subplot(111)
    legend_columns = 2 if len(series_items) >= 9 else 1
    compact_figure = style.width_cm <= 8.0 or style.height_cm <= 8.0
    if compact_figure:
        figure.subplots_adjust(
            left=0.29,
            right=0.96,
            bottom=0.22,
            top=0.84 if style.show_title else 0.95,
        )
    else:
        figure.subplots_adjust(
            left=0.12,
            right=0.96,
            bottom=0.14,
            top=0.88 if style.show_title else 0.96,
        )

    for index, item in enumerate(series_items):
        color = COLORS[index % len(COLORS)] if style.use_color else "#202020"
        marker = style.markers[index % len(style.markers)]
        line_style = "-" if style.use_color else MONOCHROME_LINE_STYLES[index % len(MONOCHROME_LINE_STYLES)]
        if config.plot_type == "scatter":
            axes.scatter(
                item.x,
                item.y,
                label=item.name,
                color=color,
                marker=marker,
                s=style.marker_size**2,
                alpha=0.92,
                edgecolors=color,
                linewidths=0.5,
                zorder=3,
            )
        else:
            axes.plot(
                item.x,
                item.y,
                label=item.name,
                color=color,
                marker=marker,
                linestyle=line_style,
                linewidth=style.data_line_width,
                markersize=style.marker_size,
                markeredgecolor=color,
                markeredgewidth=0.5,
                alpha=0.94,
                zorder=3,
            )

    _apply_academic_axes(axes, series_items, style.minor_divisions)
    if style.show_title:
        axes.set_title(
            config.title,
            fontsize=style.title_font_size,
            fontweight="bold",
            pad=max(10, style.title_font_size),
            wrap=True,
        )
    axes.set_xlabel(
        config.x_label,
        fontsize=style.axis_font_size,
        fontweight="bold",
        labelpad=8,
    )
    axes.set_ylabel(
        config.y_label,
        fontsize=style.axis_font_size,
        fontweight="bold",
        labelpad=8,
    )
    axes.tick_params(
        axis="both",
        which="major",
        direction="in",
        labelsize=style.tick_font_size,
        colors="#262626",
        length=4,
        width=0.8,
        top=False,
        right=False,
    )
    axes.tick_params(
        axis="both",
        which="minor",
        direction="in",
        colors="#4F4F4F",
        length=style.minor_tick_length,
        width=0.6,
        top=False,
        right=False,
    )
    axes.grid(
        True,
        which="major",
        color="#D2D2D2",
        linestyle=(0, (2.2, 2.2)),
        linewidth=style.major_grid_width,
        alpha=0.82,
        zorder=0,
    )
    axes.grid(
        style.show_minor_grid,
        which="minor",
        color="#E8E8E8",
        linestyle=(0, (1.4, 2.4)),
        linewidth=style.minor_grid_width,
        alpha=0.9,
        zorder=0,
    )
    axes.set_axisbelow(True)
    axes.set_facecolor("#FFFFFF")

    # A complete rectangular frame matches conventional journal figures and
    # makes the plot boundary meet cleanly at all four axis endpoints.
    for side in ("left", "bottom", "top", "right"):
        axes.spines[side].set_visible(True)
        axes.spines[side].set_color("#4A4A4A")
        axes.spines[side].set_linewidth(style.axis_line_width)

    legend = axes.legend(
        loc="lower right",
        borderaxespad=0.65,
        frameon=True,
        fancybox=False,
        framealpha=1.0,
        ncol=legend_columns,
        fontsize=max(5.0, style.legend_font_size - 0.4) if legend_columns == 2 else style.legend_font_size,
        labelspacing=0.4,
        handletextpad=0.5,
        handlelength=1.8,
        columnspacing=1.0,
        borderpad=0.55,
    )
    legend.get_frame().set_facecolor("white")
    legend.get_frame().set_edgecolor("#4A4A4A")
    legend.get_frame().set_linewidth(max(0.6, style.axis_line_width * 0.85))
    return figure


def _safe_filename(title: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned[:80] or "plot").rstrip(" .")


def export_png(
    figure: Figure,
    data_folder: Path | str,
    title: str,
    dpi: int = 300,
    now: datetime | None = None,
) -> Path:
    output_folder = Path(data_folder) / "results"
    output_folder.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    stem = f"{_safe_filename(title)}_{stamp}"
    destination = output_folder / f"{stem}.png"
    counter = 2
    while destination.exists():
        destination = output_folder / f"{stem}_{counter}.png"
        counter += 1

    figure.savefig(
        destination,
        dpi=dpi,
        format="png",
        facecolor="white",
    )
    return destination
