from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .editable_data import EditableDataModel
from .models import LoadReport, PlotConfig
from .plotting import build_figure


class DataEditorWindow(tk.Toplevel):
    """Spreadsheet-like long table with a debounced live plot preview."""

    BG = "#EEF1EE"
    SURFACE = "#FFFFFF"
    INK = "#14231F"
    MUTED = "#66736E"
    BORDER = "#D8DFDA"
    ACCENT = "#1C6654"
    ACCENT_SOFT = "#E4F1EC"
    ERROR = "#B8403A"

    ALL_SERIES = "全部系列"
    EDITABLE_COLUMNS = {"#1": "series", "#4": "x", "#5": "y"}

    def __init__(
        self,
        parent: tk.Misc,
        report: LoadReport,
        get_plot_config: Callable[[], PlotConfig],
        on_data_changed: Callable[[EditableDataModel], None],
        on_close: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title("数据汇总与实时预览 · PlotLab")
        self.geometry("1220x730")
        self.minsize(1000, 620)
        self.configure(bg=self.BG)
        self.transient(parent)

        self.report = report
        self.model = EditableDataModel(report)
        self.get_plot_config = get_plot_config
        self.on_data_changed = on_data_changed
        self.on_close_callback = on_close
        self.filter_var = tk.StringVar(value=self.ALL_SERIES)
        self.status_var = tk.StringVar()
        self.preview_status_var = tk.StringVar(value="准备实时预览")
        self.cell_editor: ttk.Entry | None = None
        self.preview_after_id: str | None = None
        self.preview_canvas: FigureCanvasTkAgg | None = None
        self.figure = None

        self._build_ui()
        self._refresh_table()
        self._schedule_preview(delay_ms=30)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<F5>", lambda _event: self._schedule_preview(delay_ms=0))

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg=self.BG, padx=24, pady=17)
        header.pack(fill="x")
        copy = tk.Frame(header, bg=self.BG)
        copy.pack(side="left")
        tk.Label(
            copy,
            text="数据汇总与实时预览",
            bg=self.BG,
            fg=self.INK,
            font=("Microsoft YaHei UI", 17, "bold"),
        ).pack(anchor="w")
        tk.Label(
            copy,
            text="双击系列名称、X 或 Y 单元格即可编辑；修改仅作用于当前会话，不覆盖源 Excel。",
            bg=self.BG,
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", pady=(3, 0))
        self.live_pill = tk.Label(
            header,
            text="  ●  LIVE  ",
            bg=self.ACCENT_SOFT,
            fg=self.ACCENT,
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=6,
        )
        self.live_pill.pack(side="right", anchor="n", pady=4)

        content = tk.PanedWindow(
            self,
            orient="horizontal",
            bg=self.BG,
            sashwidth=8,
            sashrelief="flat",
            bd=0,
        )
        content.pack(fill="both", expand=True, padx=24, pady=(0, 12))

        table_panel = tk.Frame(
            content,
            bg=self.SURFACE,
            highlightthickness=1,
            highlightbackground=self.BORDER,
        )
        preview_panel = tk.Frame(
            content,
            bg=self.SURFACE,
            highlightthickness=1,
            highlightbackground=self.BORDER,
        )
        content.add(table_panel, minsize=430, width=520)
        content.add(preview_panel, minsize=440)
        self._build_table_panel(table_panel)
        self._build_preview_panel(preview_panel)

        footer = tk.Frame(self, bg=self.BG, padx=24)
        footer.pack(fill="x", pady=(0, 12))
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=self.BG,
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        tk.Label(
            footer,
            text="Enter 保存单元格 · Esc 取消编辑 · Delete 删除行 · F5 刷新预览",
            bg=self.BG,
            fg="#89958F",
            font=("Microsoft YaHei UI", 8),
        ).pack(side="right")

    def _build_table_panel(self, parent: tk.Frame) -> None:
        toolbar = tk.Frame(parent, bg=self.SURFACE, padx=14, pady=12)
        toolbar.pack(fill="x")
        tk.Label(
            toolbar,
            text="汇总表",
            bg=self.SURFACE,
            fg=self.INK,
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(side="left")

        self.series_filter = ttk.Combobox(
            toolbar,
            textvariable=self.filter_var,
            state="readonly",
            width=18,
        )
        self.series_filter.pack(side="left", padx=(12, 0))
        self.series_filter.bind("<<ComboboxSelected>>", lambda _event: self._refresh_table())

        ttk.Button(
            toolbar,
            text="导出汇总表",
            style="Quiet.TButton",
            command=self._export_summary,
        ).pack(side="right")

        actions = tk.Frame(parent, bg="#F6F8F6", padx=12, pady=8)
        actions.pack(fill="x", padx=14, pady=(0, 9))
        ttk.Button(
            actions,
            text="新增数据行",
            style="Quiet.TButton",
            command=self._add_row,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="删除所选行",
            style="Quiet.TButton",
            command=self._delete_selected_row,
        ).pack(side="left", padx=(7, 0))
        tk.Label(
            actions,
            text="原文件安全：不会自动回写",
            bg="#F6F8F6",
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 8),
        ).pack(side="right")

        tree_frame = tk.Frame(parent, bg=self.BORDER)
        tree_frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("series", "source", "row", "x", "y"),
            show="headings",
            style="Data.Treeview",
            selectmode="browse",
        )
        headings = {
            "series": "数据系列",
            "source": "源文件",
            "row": "行号",
            "x": "X",
            "y": "Y",
        }
        for key, label in headings.items():
            self.tree.heading(key, text=label)
        self.tree.column("series", width=125, minwidth=90, stretch=True)
        self.tree.column("source", width=130, minwidth=90, stretch=True)
        self.tree.column("row", width=48, minwidth=42, anchor="center", stretch=False)
        self.tree.column("x", width=88, minwidth=65, anchor="e", stretch=True)
        self.tree.column("y", width=88, minwidth=65, anchor="e", stretch=True)
        y_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<Double-1>", self._begin_cell_edit)
        self.tree.bind("<Delete>", lambda _event: self._delete_selected_row())

    def _build_preview_panel(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg=self.SURFACE, padx=14, pady=12)
        header.pack(fill="x")
        tk.Label(
            header,
            text="实时图像",
            bg=self.SURFACE,
            fg=self.INK,
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            textvariable=self.preview_status_var,
            bg=self.SURFACE,
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 8),
        ).pack(side="left", padx=(10, 0))
        ttk.Button(
            header,
            text="同步当前图像参数",
            style="Quiet.TButton",
            command=lambda: self._schedule_preview(delay_ms=0),
        ).pack(side="right")

        self.preview_host = tk.Frame(parent, bg="#F6F8F7", padx=12, pady=12)
        self.preview_host.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    @staticmethod
    def _format_number(value: float) -> str:
        return f"{value:.12g}"

    def _refresh_table(self) -> None:
        selected_filter = self.filter_var.get()
        names = self.model.series_names
        if selected_filter not in names and selected_filter != self.ALL_SERIES:
            selected_filter = self.ALL_SERIES
            self.filter_var.set(selected_filter)
        self.series_filter.configure(values=[self.ALL_SERIES, *names])

        for item in self.tree.get_children():
            self.tree.delete(item)
        filter_name = None if selected_filter == self.ALL_SERIES else selected_filter
        for row in self.model.rows(filter_name):
            self.tree.insert(
                "",
                "end",
                iid=f"s{row.series_index}:r{row.row_index}",
                values=(
                    row.series_name,
                    row.source_name,
                    row.row_index + 1,
                    self._format_number(row.x),
                    self._format_number(row.y),
                ),
            )
        self.status_var.set(
            f"{len(names)} 个数据系列 · {self.model.total_points} 个数据点 · 当前显示 {len(self.tree.get_children())} 行"
        )

    @staticmethod
    def _decode_iid(iid: str) -> tuple[int, int]:
        series_part, row_part = iid.split(":")
        return int(series_part[1:]), int(row_part[1:])

    def _begin_cell_edit(self, event: tk.Event) -> None:
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        column = self.tree.identify_column(event.x)
        field = self.EDITABLE_COLUMNS.get(column)
        iid = self.tree.identify_row(event.y)
        if field is None or not iid:
            self.status_var.set("源文件和行号为只读字段。")
            return

        bbox = self.tree.bbox(iid, column)
        if not bbox:
            return
        x, y, width, height = bbox
        column_index = int(column[1:]) - 1
        current_value = str(self.tree.item(iid, "values")[column_index])
        if self.cell_editor is not None:
            self.cell_editor.destroy()
        editor = ttk.Entry(self.tree, style="PlotLab.TEntry")
        editor.insert(0, current_value)
        editor.select_range(0, "end")
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        self.cell_editor = editor
        editor.bind("<Return>", lambda _event: self._commit_cell_edit(iid, field, editor))
        editor.bind("<Escape>", lambda _event: self._cancel_cell_edit())
        editor.bind("<FocusOut>", lambda _event: self._commit_cell_edit(iid, field, editor))

    def _commit_cell_edit(self, iid: str, field: str, editor: ttk.Entry) -> None:
        if self.cell_editor is not editor or not editor.winfo_exists():
            return
        value = editor.get()
        self.cell_editor = None
        editor.destroy()
        series_index, row_index = self._decode_iid(iid)
        try:
            if field == "series":
                old_filter = self.filter_var.get()
                old_name = self.report.series[series_index].name
                self.model.rename_series(series_index, value)
                if old_filter == old_name:
                    self.filter_var.set(self.report.series[series_index].name)
            else:
                self.model.edit_number(series_index, row_index, field, value)
        except ValueError as error:
            self.status_var.set(f"修改未保存：{error}")
            self.bell()
            self._refresh_table()
            return
        self._after_data_change("数据已修改，图像正在刷新…")

    def _cancel_cell_edit(self) -> None:
        if self.cell_editor is not None:
            self.cell_editor.destroy()
            self.cell_editor = None

    def _selected_location(self) -> tuple[int, int] | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self._decode_iid(selection[0])

    def _add_row(self) -> None:
        location = self._selected_location()
        if location is not None:
            series_index = location[0]
        elif self.filter_var.get() in self.model.series_names:
            series_index = self.model.series_names.index(self.filter_var.get())
        else:
            self.status_var.set("请先选择目标系列中的任意一行。")
            self.bell()
            return

        x_value = simpledialog.askfloat("新增数据行", "输入 X 值：", parent=self)
        if x_value is None:
            return
        y_value = simpledialog.askfloat("新增数据行", "输入 Y 值：", parent=self)
        if y_value is None:
            return
        try:
            self.model.add_row(series_index, x_value, y_value)
        except ValueError as error:
            self.status_var.set(str(error))
            return
        self._after_data_change("已新增数据行，图像正在刷新…")

    def _delete_selected_row(self) -> None:
        location = self._selected_location()
        if location is None:
            self.status_var.set("请选择需要删除的数据行。")
            self.bell()
            return
        if not messagebox.askyesno(
            "删除数据行",
            "确定从当前绘图会话中删除所选数据行吗？源 Excel 不会被修改。",
            parent=self,
        ):
            return
        try:
            self.model.delete_row(*location)
        except ValueError as error:
            self.status_var.set(str(error))
            self.bell()
            return
        self._after_data_change("已删除数据行，图像正在刷新…")

    def _after_data_change(self, status: str) -> None:
        self._refresh_table()
        self.status_var.set(status)
        self.on_data_changed(self.model)
        self._schedule_preview()

    def _schedule_preview(self, delay_ms: int = 250) -> None:
        if self.preview_after_id is not None:
            self.after_cancel(self.preview_after_id)
        self.preview_status_var.set("等待刷新…")
        self.live_pill.configure(text="  ●  UPDATING  ", bg="#FFF3D9", fg="#A56A16")
        self.preview_after_id = self.after(delay_ms, self._refresh_preview)

    def _refresh_preview(self) -> None:
        self.preview_after_id = None
        try:
            config = self.get_plot_config()
            figure = build_figure(config, self.report.series)
            if self.preview_canvas is not None:
                self.preview_canvas.get_tk_widget().destroy()
            if self.figure is not None:
                self.figure.clear()
            self.figure = figure
            self.preview_canvas = FigureCanvasTkAgg(figure, master=self.preview_host)
            self.preview_canvas.draw()
            self.preview_canvas.get_tk_widget().pack(fill="both", expand=True)
            self.preview_status_var.set(f"修订 {self.model.revision} · 已同步")
            self.live_pill.configure(text="  ●  LIVE  ", bg=self.ACCENT_SOFT, fg=self.ACCENT)
        except Exception as error:
            self.preview_status_var.set(f"预览失败：{error}")
            self.live_pill.configure(text="  ●  ERROR  ", bg="#FBECEA", fg=self.ERROR)

    def _export_summary(self) -> None:
        results_folder = self.report.folder / "results"
        results_folder.mkdir(parents=True, exist_ok=True)
        default_name = f"汇总数据_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        destination = filedialog.asksaveasfilename(
            parent=self,
            title="导出修改后的汇总表",
            initialdir=results_folder,
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=[("Excel 工作簿", "*.xlsx")],
        )
        if not destination:
            return
        try:
            frame = self.model.to_dataframe()
            frame.to_excel(Path(destination), index=False, engine="openpyxl")
        except Exception as error:
            messagebox.showerror("导出失败", str(error), parent=self)
            return
        self.status_var.set(f"汇总表已导出：{destination}")

    def _close(self) -> None:
        if self.preview_after_id is not None:
            self.after_cancel(self.preview_after_id)
        if self.figure is not None:
            self.figure.clear()
        if self.on_close_callback is not None:
            self.on_close_callback()
        self.destroy()
