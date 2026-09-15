from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from excel_plotter.models import PlotConfig, PlotStyleConfig
from excel_plotter.preset_store import PresetNameConflict, PresetStore, PresetStoreError


class PresetStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "nested" / "presets.json"
        self.store = PresetStore(self.path)
        self.config = PlotConfig(
            title="材料强度对比",
            x_label="碳酸钙含量 (%)",
            y_label="抗压强度 (MPa)",
            plot_type="line",
            style=PlotStyleConfig(
                width_cm=18,
                height_cm=12,
                dpi=600,
                title_font_size=14,
                minor_divisions=4,
                show_minor_grid=False,
                show_title=False,
                use_color=False,
                markers=("s", "D"),
            ),
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_round_trip_preserves_all_text_plot_type_and_style(self) -> None:
        saved = self.store.save_config("论文双栏图", self.config)

        loaded = self.store.load()

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].name, saved.name)
        restored = loaded[0].to_config()
        self.assertEqual(restored.title, self.config.title)
        self.assertEqual(restored.x_label, self.config.x_label)
        self.assertEqual(restored.y_label, self.config.y_label)
        self.assertEqual(restored.plot_type, "line")
        self.assertEqual(restored.style, self.config.style)
        self.assertIn("论文双栏图", self.path.read_text(encoding="utf-8"))

    def test_same_name_requires_explicit_overwrite_and_moves_updated_first(self) -> None:
        self.store.save_config("Nature", self.config)
        with self.assertRaises(PresetNameConflict):
            self.store.save_config("nature", self.config)

        replacement = PlotConfig(
            title="Updated",
            x_label="x",
            y_label="y",
            plot_type="scatter",
            style=PlotStyleConfig(dpi=450),
        )
        self.store.save_config("NATURE", replacement, overwrite=True)

        presets = self.store.load()
        self.assertEqual(len(presets), 1)
        self.assertEqual(presets[0].name, "NATURE")
        self.assertEqual(presets[0].title, "Updated")
        self.assertEqual(presets[0].style.dpi, 450)

    def test_multiple_presets_are_ordered_by_most_recent_save(self) -> None:
        self.store.save_config("第一套", self.config)
        self.store.save_config("第二套", self.config)

        self.assertEqual([item.name for item in self.store.load()], ["第二套", "第一套"])

    def test_corrupt_store_reports_a_readable_error(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{broken", encoding="utf-8")

        with self.assertRaisesRegex(PresetStoreError, "无法读取设置方案"):
            self.store.load()

    def test_empty_and_overlong_names_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "不能为空"):
            self.store.save_config("   ", self.config)
        with self.assertRaisesRegex(ValueError, "80"):
            self.store.save_config("x" * 81, self.config)


if __name__ == "__main__":
    unittest.main()
