from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from excel_plotter.editable_data import EditableDataModel
from excel_plotter.models import LoadReport, SeriesData


class EditableDataModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        folder = Path(self.tempdir.name)
        self.report = LoadReport(
            folder=folder,
            scanned_files=[folder / "A.xlsx", folder / "B.xlsx"],
            series=[
                SeriesData("A", folder / "A.xlsx", np.array([1.0, 2.0]), np.array([3.0, 4.0])),
                SeriesData("B", folder / "B.xlsx", np.array([5.0]), np.array([6.0])),
            ],
            issues=[],
        )
        self.model = EditableDataModel(self.report)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_rows_are_a_single_long_table_in_series_order(self) -> None:
        rows = self.model.rows()

        self.assertEqual([(row.series_name, row.row_index) for row in rows], [("A", 0), ("A", 1), ("B", 0)])
        self.assertEqual(rows[0].source_name, "A.xlsx")
        self.assertEqual(self.model.total_points, 3)

    def test_numeric_edit_updates_backing_series_without_reordering(self) -> None:
        self.model.edit_number(0, 1, "x", "9.25")
        self.model.edit_number(0, 1, "y", -2)

        np.testing.assert_array_equal(self.report.series[0].x, np.array([1.0, 9.25]))
        np.testing.assert_array_equal(self.report.series[0].y, np.array([3.0, -2.0]))
        self.assertEqual(self.model.revision, 2)

    def test_rename_updates_legend_name_and_rejects_duplicates(self) -> None:
        self.model.rename_series(0, "实验组")
        self.assertEqual(self.report.series[0].name, "实验组")

        with self.assertRaisesRegex(ValueError, "已经存在"):
            self.model.rename_series(0, "B")

    def test_add_and_delete_rows_keep_x_y_lengths_synchronized(self) -> None:
        self.model.add_row(1, 7, 8)
        np.testing.assert_array_equal(self.report.series[1].x, np.array([5.0, 7.0]))
        np.testing.assert_array_equal(self.report.series[1].y, np.array([6.0, 8.0]))

        self.model.delete_row(1, 0)
        np.testing.assert_array_equal(self.report.series[1].x, np.array([7.0]))
        np.testing.assert_array_equal(self.report.series[1].y, np.array([8.0]))
        with self.assertRaisesRegex(ValueError, "至少需要保留"):
            self.model.delete_row(1, 0)

    def test_invalid_edits_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "有效数值"):
            self.model.edit_number(0, 0, "x", "bad")
        with self.assertRaisesRegex(ValueError, "有限数字"):
            self.model.edit_number(0, 0, "y", "nan")
        with self.assertRaisesRegex(ValueError, "只能编辑"):
            self.model.edit_number(0, 0, "source", 1)

    def test_dataframe_keeps_numbers_numeric_and_records_source(self) -> None:
        frame = self.model.to_dataframe()

        self.assertEqual(list(frame.columns), ["数据系列", "源文件", "系列内行号", "X", "Y"])
        self.assertEqual(frame.shape, (3, 5))
        self.assertTrue(np.issubdtype(frame["X"].dtype, np.number))
        self.assertTrue(np.issubdtype(frame["Y"].dtype, np.number))
        self.assertEqual(frame.iloc[2]["源文件"], "B.xlsx")


if __name__ == "__main__":
    unittest.main()
