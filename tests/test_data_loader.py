from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from excel_plotter.data_loader import load_folder, read_workbook, scan_excel_files


class DataLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.folder = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_reads_header_and_skips_invalid_rows(self) -> None:
        path = self.folder / "实验组.xlsx"
        pd.DataFrame(
            {"x value": [3, 1, "bad", -2, "1e2"], "y value": [9, 1, 5, -4, "2.5e2"]}
        ).to_excel(path, index=False)

        item = read_workbook(path)

        np.testing.assert_array_equal(item.x, np.array([3.0, 1.0, -2.0, 100.0]))
        np.testing.assert_array_equal(item.y, np.array([9.0, 1.0, -4.0, 250.0]))
        self.assertEqual(item.skipped_rows, 1)
        self.assertIn("已自动识别表头", item.warnings)
        self.assertIn("跳过 1 行无效数据", item.warnings)

    def test_reads_workbook_without_header_and_preserves_order(self) -> None:
        path = self.folder / "原始顺序.xlsx"
        pd.DataFrame([[7, 70], [2, 20], [5, 50]]).to_excel(path, index=False, header=False)

        item = read_workbook(path)

        np.testing.assert_array_equal(item.x, np.array([7.0, 2.0, 5.0]))
        np.testing.assert_array_equal(item.y, np.array([70.0, 20.0, 50.0]))
        self.assertNotIn("已自动识别表头", item.warnings)

    def test_scan_ignores_temp_hidden_and_unrelated_files(self) -> None:
        pd.DataFrame([[1, 2]]).to_excel(self.folder / "有效.xlsx", index=False, header=False)
        pd.DataFrame([[1, 2]]).to_excel(self.folder / "~$临时.xlsx", index=False, header=False)
        pd.DataFrame([[1, 2]]).to_excel(self.folder / ".隐藏.xlsx", index=False, header=False)
        (self.folder / "notes.csv").write_text("1,2", encoding="utf-8")
        (self.folder / "results").mkdir()

        files = scan_excel_files(self.folder)

        self.assertEqual([path.name for path in files], ["有效.xlsx"])

    def test_folder_load_skips_bad_files_and_continues(self) -> None:
        pd.DataFrame([[1, 2], [3, 4]]).to_excel(
            self.folder / "good.xlsx", index=False, header=False
        )
        pd.DataFrame([[1], [2]]).to_excel(self.folder / "one-column.xlsx", index=False, header=False)
        (self.folder / "broken.xlsx").write_bytes(b"not an xlsx file")

        report = load_folder(self.folder)

        self.assertEqual(report.valid_file_count, 1)
        self.assertEqual(report.total_points, 2)
        self.assertEqual(len(report.issues), 2)
        self.assertEqual(report.series[0].name, "good")

    def test_duplicate_stems_receive_stable_suffixes(self) -> None:
        data = pd.DataFrame([[1, 2], [3, 4]])
        data.to_excel(self.folder / "same.xlsx", index=False, header=False)
        data.to_excel(self.folder / "same.xlsm", index=False, header=False, engine="openpyxl")

        report = load_folder(self.folder)

        self.assertEqual([item.name for item in report.series], ["same (1)", "same (2)"])


if __name__ == "__main__":
    unittest.main()
