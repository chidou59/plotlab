from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from excel_plotter.models import PlotConfig, PlotStyleConfig, SeriesData
from excel_plotter.plotting import build_figure, export_png


class PlottingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.folder = Path(self.tempdir.name)
        self.series = [
            SeriesData(
                name="Series A 数据组",
                source=self.folder / "Series A 数据组.xlsx",
                x=np.array([3.0, 1.0, 2.0]),
                y=np.array([-1.0, 4.0, 2.0]),
            )
        ]

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_default_style_matches_requested_publication_parameters(self) -> None:
        style = PlotStyleConfig()

        self.assertEqual(style.width_cm, 12)
        self.assertEqual(style.height_cm, 10)
        self.assertEqual(style.dpi, 300)
        self.assertEqual(style.title_font_size, 10.5)
        self.assertEqual(style.axis_font_size, 9)
        self.assertEqual(style.tick_font_size, 9)
        self.assertEqual(style.legend_font_size, 9)
        self.assertEqual(style.marker_size, 4)
        self.assertEqual(style.data_line_width, 1)
        self.assertEqual(style.axis_line_width, 0.85)
        self.assertEqual(style.major_grid_width, 0.65)
        self.assertEqual(style.minor_grid_width, 0.35)
        self.assertEqual(style.minor_divisions, 2)
        self.assertEqual(style.minor_tick_length, 2.2)

    def test_line_figure_preserves_source_order_and_labels(self) -> None:
        config = PlotConfig(
            title="中英 Mixed Title",
            x_label="时间 Time (s)",
            y_label="强度 Strength (MPa)",
            plot_type="line",
        )

        figure = build_figure(config, self.series)
        axes = figure.axes[0]

        np.testing.assert_array_equal(axes.lines[0].get_xdata(), np.array([3.0, 1.0, 2.0]))
        self.assertEqual(axes.get_title(), config.title)
        self.assertEqual(axes.get_xlabel(), config.x_label)
        self.assertEqual(axes.get_ylabel(), config.y_label)
        self.assertEqual(axes.title.get_fontfamily(), ["Times New Roman", "SimHei"])
        self.assertEqual(axes.title.get_fontsize(), 10.5)
        self.assertEqual(axes.xaxis.label.get_fontsize(), 9.0)
        self.assertEqual(axes.yaxis.label.get_fontsize(), 9.0)
        self.assertEqual(axes.get_xticklabels()[0].get_fontsize(), 9.0)
        self.assertIsNotNone(axes.get_legend())

    def test_scatter_figure_contains_one_collection_per_series(self) -> None:
        second = SeriesData(
            name="B",
            source=self.folder / "B.xlsx",
            x=np.array([0.0, 1.0]),
            y=np.array([1.0, 2.0]),
        )
        config = PlotConfig(title="点图", x_label="x", y_label="y", plot_type="scatter")

        figure = build_figure(config, [*self.series, second])

        axes = figure.axes[0]
        self.assertEqual(len(axes.collections), 2)
        self.assertTrue(axes.spines["top"].get_visible())
        self.assertTrue(axes.spines["right"].get_visible())

    def test_axis_endpoints_align_with_first_and_last_major_ticks(self) -> None:
        config = PlotConfig(title="论文图", x_label="x", y_label="y", plot_type="scatter")

        figure = build_figure(config, self.series)
        axes = figure.axes[0]
        x_limits = axes.get_xlim()
        y_limits = axes.get_ylim()
        x_ticks = axes.get_xticks()
        y_ticks = axes.get_yticks()

        self.assertAlmostEqual(x_limits[0], x_ticks[0])
        self.assertAlmostEqual(x_limits[1], x_ticks[-1])
        self.assertAlmostEqual(y_limits[0], y_ticks[0])
        self.assertAlmostEqual(y_limits[1], y_ticks[-1])
        self.assertLessEqual(x_limits[0], float(self.series[0].x.min()))
        self.assertGreaterEqual(x_limits[1], float(self.series[0].x.max()))
        self.assertLessEqual(y_limits[0], float(self.series[0].y.min()))
        self.assertGreaterEqual(y_limits[1], float(self.series[0].y.max()))
        self.assertEqual(axes.xaxis.majorTicks[0]._tickdir, "in")
        self.assertEqual(axes.yaxis.majorTicks[0]._tickdir, "in")
        self.assertEqual(axes.xaxis.minorTicks[0]._tickdir, "in")
        self.assertEqual(axes.yaxis.minorTicks[0]._tickdir, "in")

    def test_large_legend_uses_two_columns_inside_lower_right_with_a_frame(self) -> None:
        many_series = [
            SeriesData(
                name=f"Reference {index}",
                source=self.folder / f"Reference {index}.xlsx",
                x=np.array([1.0, 2.0]),
                y=np.array([float(index), float(index + 1)]),
            )
            for index in range(12)
        ]
        config = PlotConfig(title="多系列", x_label="x", y_label="y", plot_type="scatter")

        figure = build_figure(config, many_series)
        legend = figure.axes[0].get_legend()

        self.assertEqual(legend._ncols, 2)
        self.assertTrue(legend.get_frame_on())
        self.assertEqual(legend._loc, 4)
        self.assertEqual(legend.get_title().get_text(), "")

    def test_custom_style_is_applied_to_figure_text_lines_and_minor_grid(self) -> None:
        style = PlotStyleConfig(
            width_cm=18,
            height_cm=12,
            dpi=600,
            title_font_size=18,
            axis_font_size=13,
            tick_font_size=10,
            legend_font_size=8,
            marker_size=7,
            data_line_width=2.1,
            axis_line_width=1.2,
            major_grid_width=0.8,
            minor_grid_width=0.45,
            minor_divisions=4,
            minor_tick_length=3.1,
            show_minor_grid=True,
        )
        config = PlotConfig(
            title="自定义论文图",
            x_label="x",
            y_label="y",
            plot_type="line",
            style=style,
        )

        figure = build_figure(config, self.series)
        axes = figure.axes[0]
        expected_inches = np.array(
            [(round(18 / 2.54 * 600) + 0.01) / 600, (round(12 / 2.54 * 600) + 0.01) / 600]
        )
        np.testing.assert_allclose(figure.get_size_inches(), expected_inches)
        self.assertEqual(config.dpi, 600)
        self.assertEqual(axes.title.get_fontsize(), 18)
        self.assertEqual(axes.xaxis.label.get_fontsize(), 13)
        self.assertEqual(axes.get_xticklabels()[0].get_fontsize(), 10)
        self.assertEqual(axes.lines[0].get_linewidth(), 2.1)
        self.assertEqual(axes.lines[0].get_markersize(), 7)
        self.assertEqual(axes.spines["top"].get_linewidth(), 1.2)
        self.assertEqual(axes.get_legend().get_texts()[0].get_fontsize(), 8)
        minor_gridlines = [tick.gridline for tick in axes.xaxis.get_minor_ticks()]
        self.assertTrue(minor_gridlines)
        self.assertTrue(all(line.get_visible() for line in minor_gridlines))
        self.assertTrue(all(line.get_linewidth() == 0.45 for line in minor_gridlines))

    def test_style_validation_rejects_values_outside_safe_ranges(self) -> None:
        with self.assertRaisesRegex(ValueError, "图像宽度"):
            PlotStyleConfig(width_cm=2)
        with self.assertRaisesRegex(ValueError, "次刻度分段数"):
            PlotStyleConfig(minor_divisions=1)
        with self.assertRaisesRegex(ValueError, "至少需要保留一种"):
            PlotStyleConfig(markers=())
        with self.assertRaisesRegex(ValueError, "不支持的形状"):
            PlotStyleConfig(markers=("o", "invalid"))

    def test_title_can_be_hidden_and_monochrome_uses_selected_marker_library(self) -> None:
        series_items = [
            SeriesData(
                name=f"Series {index}",
                source=self.folder / f"Series {index}.xlsx",
                x=np.array([1.0, 2.0, 3.0]),
                y=np.array([index + 1.0, index + 2.0, index + 3.0]),
            )
            for index in range(3)
        ]
        style = PlotStyleConfig(
            show_title=False,
            use_color=False,
            markers=("s", "D"),
        )
        config = PlotConfig(
            title="这行标题不应输出",
            x_label="x",
            y_label="y",
            plot_type="line",
            style=style,
        )

        figure = build_figure(config, series_items)
        axes = figure.axes[0]

        self.assertEqual(axes.get_title(), "")
        self.assertEqual([line.get_color() for line in axes.lines], ["#202020"] * 3)
        self.assertEqual([line.get_marker() for line in axes.lines], ["s", "D", "s"])
        self.assertEqual([line.get_linestyle() for line in axes.lines], ["-", "--", "-."])

    def test_export_creates_results_png_at_300_dpi_without_overwrite(self) -> None:
        config = PlotConfig(title='测试：A/B?*', x_label="x", y_label="y", plot_type="scatter")
        figure = build_figure(config, self.series)
        now = datetime(2026, 8, 24, 12, 34, 56)

        first = export_png(figure, self.folder, config.title, 300, now)
        second = export_png(figure, self.folder, config.title, 300, now)

        self.assertTrue(first.exists())
        self.assertEqual(first.parent.name, "results")
        self.assertNotEqual(first, second)
        self.assertNotRegex(first.name, r'[<>:"/\\|?*]')
        with Image.open(first) as image:
            expected_width = round(12 / 2.54 * 300)
            expected_height = round(10 / 2.54 * 300)
            self.assertAlmostEqual(image.width, expected_width, delta=1)
            self.assertAlmostEqual(image.height, expected_height, delta=1)
            dpi = image.info.get("dpi", (0, 0))
            self.assertAlmostEqual(dpi[0], 300, delta=1)
            self.assertAlmostEqual(dpi[1], 300, delta=1)


if __name__ == "__main__":
    unittest.main()
